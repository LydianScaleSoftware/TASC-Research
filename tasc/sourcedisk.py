"""Phase 5: the TASC source disk, a bootable DOS 3.3 disk with the recovered programs.

    python -m tasc.sourcedisk               write images/source/TASC 2.01 SOURCE.dsk
    python -m tasc.sourcedisk --compile P   also compile pass P from the disk with the real TASC
                                            (TASC disk in drive 1, source disk in drive 2) and
                                            compare the object with the original pass

The disk holds the tokenized Applesoft sources exactly as tasc.sourcegen wrote them
(src/PASS0.bas, PASS1.bas, PASS2.bas: the files the self-compile proof compiles),
MAKE RUNTIME (tokenized from src/MAKE_RUNTIME.txt; its line 10 re-runs it by that
name), RUNTIME.S1-RUNTIME.S6 (the library's 6502 source for EDASM as text files of at
most 12K, chained with CHN; assemble RUNTIME.S1) and a HELLO that catalogs the disk at boot.  cp2 writes the standard DOS 3.3
image to tracks 0-2.  The image is rebuilt from scratch each time and checked by
extracting every file again.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import json
import shutil
import sys

from tasc import disk, rtsource

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
IMAGE = ROOT / "images" / "source" / "TASC 2.01 SOURCE.dsk"
TASC_DISK = ROOT / "images" / "work" / "tasc201.dsk"
OUT = ROOT / "experiments" / "p5_sourcedisk"

HELLO = """10 TEXT : HOME
20 PRINT "TASC 2.01 SOURCE DISK"
30 PRINT
40 PRINT "PASS0, PASS1, PASS2: THE COMPILER PASSES"
50 PRINT "MAKE RUNTIME: BUILDS THE RUNTIME LIBRARY"
60 PRINT "RUNTIME.S1-S6: SOURCE OF THE LIBRARY"
70 PRINT
80 PRINT CHR$ (4);"CATALOG"
"""

A_TYPE, A_AUX = 0xFC, 0x0801


def build(image: Path = IMAGE) -> dict[str, bytes]:
    """Create the image; return the program files it holds, by name."""
    image.parent.mkdir(parents=True, exist_ok=True)
    if image.exists():
        image.unlink()
    # cp2 wants .do to know the sector order; .dsk images here are DOS order too
    blank = image.with_suffix(".do")
    disk.run_cp2("create-disk-image", str(blank.resolve()), "35trk", "dos")
    blank.rename(image)
    files: dict[str, bytes] = {}
    with tempfile.TemporaryDirectory() as td:
        hello = Path(td) / "hello.txt"
        hello.write_text(HELLO)
        disk.import_basic(image, hello, "HELLO")
        disk.import_basic(image, SRC / "MAKE_RUNTIME.txt", "MAKE RUNTIME")
        for part in sorted(rtsource.PART_DIR.glob("RUNTIME.S*"), key=lambda q: int(q.name[9:])):
            shutil.copyfile(part, Path(td) / part.name)
            disk.run_cp2("import", str(image.resolve()), "text", part.name, cwd=Path(td))
    for p in ("PASS0", "PASS1", "PASS2"):
        data = (SRC / f"{p}.bas").read_bytes()
        disk.add_file(image, p, data, A_TYPE, A_AUX)
        files[p] = data
    return files


def text_file(image: Path, name: str) -> str:
    """A text file as read back from the disk: DOS text (bit 7 set, carriage returns) to plain text."""
    raw = disk.extract(image, name).data
    return bytes(b & 0x7F for b in raw).decode("ascii").replace("\r", "\n")


def check(image: Path, files: dict[str, bytes]) -> list[str]:
    """Each pass's file on the disk must be byte for byte the generated program, and
    RUNTIME.S1 and the files it chains to, read back from the disk, must assemble to RUNTIME."""
    problems = [f"RUNTIME.S1-S6: {p}" for p in rtsource.check(text_file(image, "RUNTIME.S1"),
                                                              lambda name: text_file(image, name))]
    for name, data in files.items():
        got = disk.extract(image, name).data
        if got != data:
            problems.append(f"{name}: {len(got)} bytes on disk, {len(data)} generated")
    return problems


def compile_from_disk(name: str) -> dict[str, object]:
    """Real TASC in drive 1 compiles NAME from the source disk in drive 2 (copies of both);
    the object goes to drive 1 as NAME.OBJ (the source disk has no room for it) and is
    compared with the original pass."""
    from tasc.emu import Pandowdy
    from tasc.harness import DEFAULT_ANSWERS, Session, compile_in_session, sha256

    d = OUT / name
    d.mkdir(parents=True, exist_ok=True)
    tasc, src = d / "tasc.dsk", d / "source.dsk"
    shutil.copyfile(TASC_DISK, tasc)
    shutil.copyfile(IMAGE, src)
    with Pandowdy() as emu:
        emu.boot(tasc, drive2=src)
        s = Session(emu)
        s.run_to_key(40_000_000)
        answers = [("(DEFAULT", f"{name}.OBJ,D1")] + DEFAULT_ANSWERS[1:]
        cycles = compile_in_session(s, f"{name},D2", answers)
        s.finish_transcript()
        emu.call("save_disk", path=str((d / "tasc_after.dsk").resolve()), drive=1)
    (d / "transcript.txt").write_text(s.transcript.text())
    obj = disk.extract(d / "tasc_after.dsk", f"{name}.OBJ")
    orig = disk.extract(TASC_DISK, name)
    (d / f"{name}.OBJ").write_bytes(obj.data)
    summary: dict[str, object] = {
        "pass": name, "identical": obj.data == orig.data and obj.aux == orig.aux,
        "len": len(obj.data), "orig_len": len(orig.data), "load": obj.aux,
        "sha256": sha256(obj.data), "orig_sha256": sha256(orig.data), "cycles": cycles}
    (d / "summary.json").write_text(json.dumps(summary, indent=1) + "\n")
    return summary


def main() -> None:
    args = sys.argv[1:]
    if args and args[0] == "--compile":
        for name in args[1:] or ["PASS0", "PASS1", "PASS2"]:
            print(json.dumps(compile_from_disk(name)))
        return
    files = build()
    problems = check(IMAGE, files)
    print(disk.run_cp2("catalog", str(IMAGE.resolve())).rstrip())
    from tasc import docview
    docview.write_index()  # the downloadable copy on the index page
    print("check:", "; ".join(problems) if problems else
          "every pass on the disk is identical to src/PASSn.bas; RUNTIME.S1 and its chain, read back, assemble to RUNTIME")


if __name__ == "__main__":
    main()
