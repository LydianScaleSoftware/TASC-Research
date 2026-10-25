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
