"""Compile the decompiled PASS sources with the real TASC and compare with the originals.

    python -m tasc.selfcompile [PASS0 PASS1 PASS2]

For each pass: generate the Phase 5 source (tasc.sourcegen: names, numbering,
documentation; src/PASSn.bas), add the source to a copy of the TASC disk, compile it
with default options in a fresh Pandowdy, and compare the object with the
original PASS file.  Results go to experiments/p3_selfcompile/<pass>/.
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

from tasc import disk
from tasc.sourcegen import generate
from tasc.harness import compile_file, sha256

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "experiments" / "p3_selfcompile"
GEN = ROOT / "src" / "generated"
BASE = ROOT / "images" / "work" / "tasc201.dsk"
SRC_NAME = {"PASS0": "SRC0", "PASS1": "SRC1", "PASS2": "SRC2"}


def main() -> None:
    want = sys.argv[1:] or ["PASS0", "PASS1", "PASS2"]
    units = generate()  # the Phase 5 sources: src/PASSn.bas (+ listing, DOC, VARS)
    for u in units:
        if u.name not in want:
            continue
        d = OUT / u.name
        d.mkdir(parents=True, exist_ok=True)
        base = d / "base.dsk"
        shutil.copyfile(BASE, base)
        name = SRC_NAME[u.name]
        disk.add_file(base, name, u.program, 0xFC, 0x0801)
        res = compile_file(base, name, d)
        obj = (d / (name + ".OBJ")).read_bytes()
        same = obj == u.data and res.obj_addr == u.load
        off = next((i for i in range(min(len(obj), len(u.data))) if obj[i] != u.data[i]), None)
        summary = {"pass": u.name, "identical": same, "len": len(obj), "orig_len": len(u.data),
                   "load": res.obj_addr, "sha256": sha256(obj), "orig_sha256": sha256(u.data),
                   "first_diff": off, "cycles": res.cycles, "lines": len(res.line_table)}
        (d / "summary.json").write_text(json.dumps(summary, indent=1) + "\n")
        print(json.dumps(summary))


if __name__ == "__main__":
    main()
