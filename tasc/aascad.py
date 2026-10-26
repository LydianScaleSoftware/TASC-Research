"""AASCAD: Another AppleSoft Compiler And Decompiler.

A Python reimplementation of Microsoft's TASC 2.01 Applesoft compiler (1981) that
produces the same object files byte for byte, and a decompiler that turns a TASC
object file back into an Applesoft program which compiles to the same bytes.

Copyright (c) 2026 Lydian Scale Software (https://lydianscale.com). Portions are the
work of Microsoft: the code sequences and object file layout AASCAD reproduces and the
RUNTIME library entry points it calls are those of TASC (copyright 1981 Microsoft), and
its number conversion follows the Applesoft ROM (Applesoft, Microsoft and Apple). AASCAD
is not a Microsoft product.

    aascad compile SOURCE [-o OBJECT] [options]
        SOURCE is a text listing (numbered lines) or a tokenized Applesoft program
        (as saved by DOS, without the 2-byte length). Writes the object file as TASC
        does (the contents of the binary file; its load address is printed).
          --library ADDR --program ADDR|HGR1|HGR2 --variables ADDR   memory layout
          --no-int-arith --no-int-const --resume                     code options
          --compare OBJECT   check the result against an existing object file
          --map              print the line number table (line, address)

    aascad decompile OBJECT [-o LISTING] [--bas PROGRAM] [--load ADDR]
        Reads a TASC object file, works out its load address and memory layout from
        its header, finds the code options by trying them, and writes the Applesoft
        program (a text listing, and with --bas the tokenized program). The result
        is checked by compiling it again: it is reported only if the bytes match.

Files are read from and written to the local filesystem. A file inside a disk image
is named IMAGE::NAME (for example "TASC.dsk::BALL" or -o "WORK.dsk::BALL.OBJ"); disk
images are read and written with CiderPress II's command-line program, found through
--cp2 PATH, the CP2PATH environment variable, or cp2 on the PATH. A binary file read
from an image brings its load address; an object written to an image is a binary file
at its load address, a program (--bas) an Applesoft file. --replace lets a write
replace a file already on the image.

Addresses may be decimal, $hex or 0xhex. Requires Python 3.9 or later (tested on 3.9.6
and 3.14); standard library only.
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import os
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

from tasc.applesoft import tokenize_program
from tasc.compiler.assemble import compile_program
from tasc.options import Options

LIBRARY = 0x0803
LIBRARY_LEN = 4013


# ---------------------------------------------------------------- files: local or inside a disk image

CP2 = "cp2"
TYPES = {"A": 0xFC, "B": 0x06}


@dataclass
class File:
    data: bytes
    load: int | None = None  # a binary file's address, when it came from a disk image


def _image(spec: str) -> tuple[str, str] | None:
    if "::" in spec:
        image, name = spec.split("::", 1)
        return image, name
    return None


def _cp2(*args: str, cwd: str | None = None) -> str:
    try:
        p = subprocess.run([CP2, *args], cwd=cwd, capture_output=True, text=True, check=False)
    except FileNotFoundError:
        raise SystemExit(f"aascad: CiderPress II not found as {CP2!r}; give --cp2 PATH or set CP2PATH") from None
    if p.returncode != 0:
        raise SystemExit(f"aascad: cp2 {' '.join(args)} failed:\n{p.stderr}{p.stdout}")
    return p.stdout


def read_file(spec: str) -> File:
    img = _image(spec)
    if img is None:
        return File(Path(spec).read_bytes())
    image, name = img
    with tempfile.TemporaryDirectory() as td:
        _cp2("extract", "--preserve=naps", "--overwrite", str(Path(image).resolve()), name, cwd=td)
        files = [f for f in Path(td).rglob("*") if f.is_file()]
        if len(files) != 1:
            raise SystemExit(f"aascad: {name} not found on {image}")
        m = re.search(r"#([0-9a-fA-F]{2})([0-9a-fA-F]{4})$", files[0].name)
        load = int(m.group(2), 16) if m and int(m.group(1), 16) == 0x06 else None
        return File(files[0].read_bytes(), load)


def write_file(spec: str, data: bytes, kind: str, load: int = 0x0801, replace: bool = False) -> None:
    """Write data locally, or to a disk image as a file of the given kind (A or B)."""
    img = _image(spec)
    if img is None:
        Path(spec).write_bytes(data)
        return
    image, name = img
    path = str(Path(image).resolve())
    # cp2 add skips a name that is already there without saying so: check first
    on_disk = any(re.search(r"[ *]" + re.escape(name) + r"$", line.rstrip())
                  for line in _cp2("catalog", path).splitlines())
    if on_disk and not replace:
        raise SystemExit(f"aascad: {name} is already on {image}; give --replace to replace it")
    with tempfile.TemporaryDirectory() as td:
        host = Path(td) / f"{name}#{TYPES[kind]:02x}{load:04x}"
        host.write_bytes(data)
        _cp2("add", "--overwrite", path, host.name, cwd=td) if on_disk else _cp2("add", path, host.name, cwd=td)


def _addr(text: str) -> int:
    t = text.strip()
    if t.startswith("$"):
        return int(t[1:], 16)
    return int(t, 0)


def read_source(spec: str) -> bytes:
    """A text listing is tokenized; anything else is taken as a tokenized program."""
    raw = read_file(spec).data
    try:
        text = raw.decode("ascii")
        first = next(line for line in text.splitlines() if line.strip())
        if first.strip()[:1].isdigit():
            return tokenize_program(text)
    except (UnicodeDecodeError, StopIteration):
        pass
    return raw


def _word(data: bytes, i: int) -> int:
    return data[i] | data[i + 1] << 8


def header(data: bytes) -> dict[str, int]:
    """The object's JSR to the library and the header INIT copies to page zero."""
    if len(data) < 20 or data[0] != 0x20:
        raise ValueError("not a TASC object file (it must start with JSR to the library)")
    w = [_word(data, 3 + 2 * k) for k in range(8)]
    return {"library": _word(data, 1), "data": w[0], "highest": w[1], "common": w[2] + 1,
            "load": w[4] + 1, "locals": w[5] + 1, "flag": data[19]}


def candidate_options(h: dict[str, int]) -> list[Options]:
    """Options to try for a decompile: the memory layout from the header, the code
    options in every combination, the defaults first."""
    lib = None if h["library"] == LIBRARY else h["library"]
    prog = None if h["common"] == h["library"] + LIBRARY_LEN else h["common"]
    out = []
    for variables in (None, h["locals"]):
        for ia, ic, rd in itertools.product((True, False), (True, False), (False, True)):
            out.append(Options(library=lib, program=prog, variables=variables,
                               int_arith=ia, int_const=ic, resume=rd))
    return out


def cmd_compile(a: argparse.Namespace) -> int:
    program = read_source(a.source)
    prog: int | str | None = None
    if a.program:
        prog = a.program.upper() if a.program.upper() in ("HGR1", "HGR2") else _addr(a.program)
    opts = Options(library=_addr(a.library) if a.library else None, program=prog,
                   variables=_addr(a.variables) if a.variables else None,
                   int_arith=not a.no_int_arith, int_const=not a.no_int_const, resume=a.resume)
    res = compile_program(program, opts)
    out = a.output or (a.source + ".OBJ" if _image(a.source) else str(Path(a.source).with_suffix(".OBJ")))
    write_file(out, res.data, "B", res.load, a.replace)
    print(f"{out}: load ${res.load:04X}, {len(res.data)} bytes, sha256 {hashlib.sha256(res.data).hexdigest()}")
    if a.map:
        for n, ad in sorted(res.line_addr.items()):
            if n >= 0:
                print(f"{n:>6} ${ad:04X}")
    if a.compare:
        other = read_file(a.compare).data
        if other == res.data:
            print(f"identical to {a.compare}")
        else:
            off = next((k for k in range(min(len(other), len(res.data))) if other[k] != res.data[k]),
                       min(len(other), len(res.data)))
            print(f"differs from {a.compare} at ${res.load + off:04X} (byte {off}); "
                  f"{len(res.data)} vs {len(other)} bytes")
            return 1
    return 0


def cmd_decompile(a: argparse.Namespace) -> int:
    from tasc.decomp.decompile import compare, decompile
    obj = read_file(a.object)
    data = obj.data
    h = header(data)
    load = _addr(a.load) if a.load else obj.load or h["load"]
    for opts in candidate_options(h):
        try:
            u = decompile(data, load, opts)
        except Exception:  # noqa: BLE001  (another option set may fit)
            continue
        if compare(u) != "identical":
            continue
        listing = u.text if u.text.endswith("\n") else u.text + "\n"
        if a.output:
            write_file(a.output, listing.encode("ascii"), "A", replace=a.replace) if _image(a.output) is None \
                else write_file(a.output, u.program, "A", replace=a.replace)
        else:
            sys.stdout.write(listing)
        if a.bas:
            write_file(a.bas, u.program, "A", replace=a.replace)
        flags = [k for k, on in (("integer arithmetic", opts.int_arith), ("integer constants", opts.int_const),
                                 ("RESUME/debug code", opts.resume)) if on]
        print(f"decompiled: load ${load:04X}, library ${h['library']:04X}, options: "
              f"{', '.join(flags) or 'none'}; the program compiles back to the same {len(data)} bytes",
              file=sys.stderr)
        return 0
    print("no Applesoft program found that compiles back to these bytes", file=sys.stderr)
    return 1


def main(argv: list[str] | None = None) -> int:
    global CP2
    p = argparse.ArgumentParser(prog="aascad", description="Another AppleSoft Compiler And Decompiler (TASC 2.01)")
    p.add_argument("--cp2", help="CiderPress II command-line program, for disk images (default: $CP2PATH or cp2)")
    sub = p.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("compile", help="compile an Applesoft program as TASC 2.01 does")
    c.add_argument("source")
    c.add_argument("-o", "--output")
    c.add_argument("--library")
    c.add_argument("--program")
    c.add_argument("--variables")
    c.add_argument("--no-int-arith", action="store_true")
    c.add_argument("--no-int-const", action="store_true")
    c.add_argument("--resume", action="store_true")
    c.add_argument("--compare")
    c.add_argument("--map", action="store_true")
    c.add_argument("--replace", action="store_true")
    d = sub.add_parser("decompile", help="turn a TASC object file back into an Applesoft program")
    d.add_argument("object")
    d.add_argument("-o", "--output")
    d.add_argument("--bas")
    d.add_argument("--load")
    d.add_argument("--replace", action="store_true")
    a = p.parse_args(argv)
    CP2 = a.cp2 or os.environ.get("CP2PATH") or "cp2"
    return cmd_compile(a) if a.cmd == "compile" else cmd_decompile(a)


if __name__ == "__main__":
    raise SystemExit(main())
