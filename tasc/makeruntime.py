"""MAKE RUNTIME: rebuild the RUNTIME library file from Applesoft DATA statements.

    python -m tasc.makeruntime          write src/MAKE_RUNTIME.txt, run it in Pandowdy,
                                         compare the BSAVEd RUNTIME with the original

RUNTIME is hand-written machine language (H6), so it has no Applesoft source; this
program is the build step for it (decided 2026-10-25): it POKEs the 4,013 bytes from
DATA into $0803-$17AF and does BSAVE RUNTIME,A$803,L4013.  The bytes go where an
Applesoft program normally lives ($0801), so line 10 first moves the program start
to $4001 (TXTTAB $67/$68, with a 0 byte before it) and re-runs the program from
disk.  Results: experiments/p5_makeruntime/.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from tasc import disk
from tasc.emu import Pandowdy
from tasc.harness import sha256

ROOT = Path(__file__).resolve().parents[1]
ORIGINAL = ROOT / "extracted" / "tasc201" / "RUNTIME#060803"
BASE = ROOT / "images" / "work" / "tasc201.dsk"
OUT = ROOT / "experiments" / "p5_makeruntime"
SOURCE = ROOT / "src" / "MAKE_RUNTIME.txt"
NAME = "MAKE RUNTIME"
LOAD = 0x0803
PER_LINE = 25


def listing(data: bytes) -> str:
    """The program text: code at 10-40, DATA from 100 in steps of 10."""
    end = LOAD + len(data) - 1
    lines = [
        f'10 IF PEEK(104) < 64 THEN POKE 103,1: POKE 104,64: POKE 16384,0: PRINT CHR$(4);"RUN {NAME}"',
        f"20 FOR AD = {LOAD} TO {end}: READ BY: POKE AD,BY: NEXT AD",
        f'30 PRINT CHR$(4);"BSAVE RUNTIME,A${LOAD:X},L{len(data)}"',
        "40 END",
    ]
    for i in range(0, len(data), PER_LINE):
        lines.append(f"{100 + 10 * (i // PER_LINE)} DATA " + ",".join(str(b) for b in data[i : i + PER_LINE]))
    return "\n".join(lines) + "\n"


def documentation(data: bytes) -> tuple[str, str]:
    """MAKE_RUNTIME.DOC.TXT (one REM line per source line, same numbers) and
    MAKE_RUNTIME.VARS.TXT (variable compendium), per handoff section 6b."""
    # Standalone, period documentation: it must read as written on the original Apple II
    # and never refer to this project's files or tools (decided 2026-10-25).
    doc = [
        "10 REM RUNTIME LOADS AT $0803-$17AF, WHERE AN APPLESOFT PROGRAM NORMALLY LIVES. IF THIS "
        "PROGRAM IS STILL THERE (HIGH BYTE OF THE PROGRAM START, LOCATION 104, BELOW 64), MOVE THE "
        "PROGRAM START TO $4001 (POINTER AT 103-104, ZERO BYTE AT $4000) AND RUN IT AGAIN FROM DISK",
        f"20 REM COPY THE {len(data)} BYTES OF THE LIBRARY FROM THE DATA STATEMENTS INTO "
        f"${LOAD:04X}-${LOAD + len(data) - 1:04X}",
        f"30 REM SAVE THEM AS THE BINARY FILE RUNTIME, LOAD ADDRESS ${LOAD:04X}, LENGTH {len(data)}",
        "40 REM",
    ]
    for i in range(0, len(data), PER_LINE):
        a = LOAD + i
        b = min(LOAD + len(data), a + PER_LINE) - 1
        doc.append(f"{100 + 10 * (i // PER_LINE)} REM RUNTIME BYTES ${a:04X}-${b:04X}")
    vars_ = ("AD  REAL  address being filled, $0803-$17AF (line 20)\n"
             "BY  REAL  byte value read from DATA (line 20)\n")
    return "\n".join(doc) + "\n", vars_


def main() -> None:
    original = ORIGINAL.read_bytes()
    SOURCE.write_text(listing(original))
    doc, vars_ = documentation(original)
    SOURCE.with_name("MAKE_RUNTIME.DOC.TXT").write_text(doc)
    SOURCE.with_name("MAKE_RUNTIME.VARS.TXT").write_text(vars_)
    OUT.mkdir(parents=True, exist_ok=True)
    work = OUT / "work.dsk"
    shutil.copyfile(BASE, work)
    disk.delete_file(work, "RUNTIME")  # the program must create it
    disk.import_basic(work, SOURCE, NAME)
    with Pandowdy() as emu:
        emu.boot(work)
        # HELLO does BLOAD RUNTIME / BRUN PASS0; with RUNTIME deleted it stops at FILE NOT
        # FOUND and the ] prompt, before TASC runs (so DOS is unpatched)
        emu.wait_key(40_000_000)
        emu.type(f"RUN {NAME}\n")
        r = emu.wait_key(2_000_000_000)
        screen = emu.screen_rows()
        emu.call("save_disk", path=str((OUT / "after.dsk").resolve()))
    files = disk.extract_all(OUT / "after.dsk")
    made = files.get("RUNTIME")
    summary: dict[str, object] = {
        "cycles_to_prompt": r.get("total_cycles"),
        "screen_tail": [row for row in screen if row.strip()][-6:],
        "made": made is not None,
    }
    if made is not None:
        (OUT / "RUNTIME.bin").write_bytes(made.data)
        summary.update({
            "identical": made.data == original and made.aux == LOAD,
            "load": f"${made.aux:04X}", "len": len(made.data), "orig_len": len(original),
            "sha256": sha256(made.data), "orig_sha256": sha256(original),
            "first_diff": next((i for i in range(min(len(made.data), len(original)))
                                if made.data[i] != original[i]), None),
        })
    (OUT / "summary.json").write_text(json.dumps(summary, indent=1) + "\n")
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
