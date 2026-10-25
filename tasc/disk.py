"""Thin wrapper around the CiderPress II command line (cp2).

All disk-image access in the project goes through this module.  cp2 is taken
from the PATH unless the TASC_CP2 environment variable names another binary.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

_NAPS_RE = re.compile(r"^(?P<name>.*)#(?P<type>[0-9a-fA-F]{2})(?P<aux>[0-9a-fA-F]{4})$")


def cp2_path() -> str:
    return os.environ.get("TASC_CP2", "cp2")


class Cp2Error(RuntimeError):
    pass


def run_cp2(*args: str, cwd: Path | None = None) -> str:
    proc = subprocess.run(
        [cp2_path(), *args], cwd=cwd, capture_output=True, text=True, check=False
    )
    if proc.returncode != 0:
        raise Cp2Error(f"cp2 {' '.join(args)} failed ({proc.returncode}):\n{proc.stderr}{proc.stdout}")
    return proc.stdout


@dataclass(frozen=True)
class CatalogEntry:
    ftype: str  # DOS 3.3 type letter: A B T I ...
    aux: int  # load address for B, $0801 for A
    length: int
    locked: bool
    name: str


def catalog(image: Path) -> list[CatalogEntry]:
    out = run_cp2("catalog", str(Path(image).resolve()))
    entries: list[CatalogEntry] = []
    started = False
    for line in out.splitlines():
        if line.startswith("----"):
            started = True
            continue
        if not started or not line.strip():
            continue
        # " B   $41F2  [No Date]   7592   7936 *PASS0"
        m = re.match(
            r"^\s*(\S+)\s+\$([0-9A-Fa-f]{4})\s+\[.*?\]\s+(\d+)\s+(\d+)\s(.)(.*)$", line
        )
        if not m:
            raise Cp2Error(f"cannot parse catalog line: {line!r}")
        entries.append(
            CatalogEntry(
                ftype=m.group(1),
                aux=int(m.group(2), 16),
                length=int(m.group(3)),
                locked=m.group(5) == "*",
                name=m.group(6),
            )
        )
    return entries


@dataclass(frozen=True)
class ExtractedFile:
    name: str
    ftype: int  # ProDOS-style type byte from the NAPS suffix ($06 BIN, $FC BAS, $04 TXT)
    aux: int
    data: bytes


def extract(image: Path, name: str) -> ExtractedFile:
    """Extract one file with its exact length, type and load address."""
    with tempfile.TemporaryDirectory() as td:
        run_cp2("extract", "--preserve=naps", "--overwrite", str(Path(image).resolve()), name, cwd=Path(td))
        files = [p for p in Path(td).rglob("*") if p.is_file()]
        if len(files) != 1:
            raise Cp2Error(f"expected one file extracting {name!r}, got {files}")
        m = _NAPS_RE.match(files[0].name)
        if not m:
            raise Cp2Error(f"no NAPS suffix on {files[0].name!r}")
        return ExtractedFile(
            name=name,
            ftype=int(m.group("type"), 16),
            aux=int(m.group("aux"), 16),
            data=files[0].read_bytes(),
        )


def extract_all(image: Path) -> dict[str, ExtractedFile]:
    """Extract every file; works for names containing '/' (cp2 escapes them as %2f)."""
    from urllib.parse import unquote

    result: dict[str, ExtractedFile] = {}
    with tempfile.TemporaryDirectory() as td:
        run_cp2("extract", "--preserve=naps", "--overwrite", str(Path(image).resolve()), cwd=Path(td))
        for p in Path(td).rglob("*"):
            if not p.is_file():
                continue
            m = _NAPS_RE.match(p.name)
            if not m:
                raise Cp2Error(f"no NAPS suffix on {p.name!r}")
            name = unquote(m.group("name"))
            result[name] = ExtractedFile(
                name=name, ftype=int(m.group("type"), 16), aux=int(m.group("aux"), 16), data=p.read_bytes()
            )
    return result


def export_text(image: Path, converter: str, name: str) -> str:
    """Export with a cp2 converter (e.g. 'bas' detokenize, 'disasm') and return the text."""
    with tempfile.TemporaryDirectory() as td:
        run_cp2("export", "--overwrite", str(Path(image).resolve()), converter, name, cwd=Path(td))
        files = [p for p in Path(td).rglob("*") if p.is_file()]
        if len(files) != 1:
            raise Cp2Error(f"expected one file exporting {name!r}, got {files}")
        return files[0].read_text(errors="replace")


def import_basic(image: Path, listing: Path, name: str) -> None:
    """Tokenize a plain-text Applesoft listing into file `name` on the image."""
    with tempfile.TemporaryDirectory() as td:
        src = Path(td) / name
        shutil.copyfile(listing, src)
        run_cp2("import", str(Path(image).resolve()), "bas", src.name, cwd=Path(td))


def add_file(image: Path, name: str, data: bytes, ftype: int, aux: int) -> None:
    """Add a file using a NAPS-suffixed host file to carry type and aux."""
    with tempfile.TemporaryDirectory() as td:
        host = Path(td) / f"{name}#{ftype:02x}{aux:04x}"
        host.write_bytes(data)
        run_cp2("add", str(Path(image).resolve()), host.name, cwd=Path(td))


def delete_file(image: Path, name: str) -> None:
    run_cp2("delete", str(Path(image).resolve()), name)
