"""Decompiler round trips: object -> Applesoft -> predictor -> identical object."""

from __future__ import annotations

from pathlib import Path

from tasc.decomp.decompile import compare, decompile, decompile_many, pass_units

GOLDEN = Path(__file__).parent / "golden"


def test_ball_round_trip() -> None:
    data = (GOLDEN / "BALL.OBJ").read_bytes()
    assert compare(decompile(data, 0x17B0)) == "identical"


def test_pass_files_round_trip() -> None:
    for u in decompile_many(pass_units()):
        assert compare(u) == "identical", u.name


def test_corpus_round_trip() -> None:
    """Every recorded real-TASC compile decompiles and recompiles byte for byte."""
    from tasc.batch import EXPERIMENTS, load_result
    from tasc.predict_check import options_of

    bad = []
    n = 0
    for d in sorted(EXPERIMENTS.glob("p*/*")):
        if not (d / "result.json").exists() or not (d / "OBJ.bin").exists():
            continue
        r = load_result(d.parent.name, d.name)
        if not r.ok:
            continue
        n += 1
        u = decompile(r.obj(d.parent.name), r.obj_addr, options_of(r.options))
        if compare(u) != "identical":
            bad.append(f"{d.parent.name}/{d.name}")
    assert n > 1500 and not bad, bad[:10]
