"""Python predictor/compiler regression tests (no emulator)."""

from __future__ import annotations

import glob
import json
from pathlib import Path

from tasc.compiler.assemble import compile_program
from tasc.batch import EXPERIMENTS, load_result
from tasc.predict_check import options_of

ROOT = Path(__file__).resolve().parent.parent


def test_ball_byte_exact() -> None:
    src = Path(glob.glob(str(ROOT / "extracted/tasc201/BALL#*"))[0]).read_bytes()
    res = compile_program(src)
    assert res.load == 0x17B0
    assert res.data == (ROOT / "tests/golden/BALL.OBJ").read_bytes()
    table = json.loads((ROOT / "experiments/phase0/A_fresh/result.json").read_text())["line_table"]
    assert {e["line"]: e["addr"] for e in table} == {n: a for n, a in res.line_addr.items() if n >= 0}


def test_all_recorded_compiles() -> None:
    bad = []
    n = 0
    for d in sorted(EXPERIMENTS.glob("p1_*/*")):
        if not (d / "source.bas").exists() or not (d / "result.json").exists():
            continue
        r = load_result(d.parent.name, d.name)
        if not r.ok:
            continue
        n += 1
        res = compile_program((d / "source.bas").read_bytes(), options_of(r.options))
        if res.load != r.obj_addr or res.data != r.obj(d.parent.name):
            bad.append(f"{d.parent.name}/{d.name}")
    assert n > 600
    assert not bad, bad[:20]
