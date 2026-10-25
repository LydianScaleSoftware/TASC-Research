"""Phase 0 regression tests.

Fast tests use cp2 and saved results; the emulator test is marked `emu`
(run with `pytest -m emu`; about 10 s).
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from tasc import disk
from tasc.harness import parse_line_table

ROOT = Path(__file__).resolve().parent.parent
ORIG = ROOT / "images" / "original"
GOLDEN = ROOT / "tests" / "golden"
BALL_OBJ_SHA = "7a37f0610faa84698ab9786e9113bfc5f7c31d618a07d36de3a65ded1a911f5b"


def test_inventory_hashes_match_images() -> None:
    inv = json.loads((ROOT / "extracted" / "inventory.json").read_text())
    files = disk.extract_all(ORIG / "TASC 2.01 (Microsoft 1981).dsk")
    for row in inv["tasc201"]:
        assert hashlib.sha256(files[row["name"]].data).hexdigest() == row["sha256"], row["name"]


def test_catalog_types_and_addresses() -> None:
    cat = {e.name: e for e in disk.catalog(ORIG / "TASC 2.01 (Microsoft 1981).dsk")}
    for name in ("PASS0", "PASS1", "PASS2"):
        assert cat[name].ftype == "B" and cat[name].aux == 0x41F2
    assert cat["RUNTIME"].aux == 0x0803 and cat["RUNTIME"].length == 4013


def test_line_table_parse() -> None:
    entries, info = parse_line_table((GOLDEN / "ball_transcript.txt").read_text())
    assert len(entries) == 40
    assert (entries[0].line, entries[0].addr) == (10, 6084)
    assert (entries[-1].line, entries[-1].addr) == (400, 7042)
    assert info["PROGRAM"] == "6064 - 7548"
    assert info["LIBRARY"] == "2051 - 6063"


def test_golden_ball_obj() -> None:
    data = (GOLDEN / "BALL.OBJ").read_bytes()
    assert hashlib.sha256(data).hexdigest() == BALL_OBJ_SHA
    # JSR $0803, 17-byte inline block, then line 10 at 6084
    assert data[:3] == bytes([0x20, 0x03, 0x08])
    assert data[6084 - 6064 : 6084 - 6064 + 3] == bytes([0x20, 0x58, 0xFC])  # JSR HOME


@pytest.mark.emu
def test_compile_ball_matches_golden(tmp_path: Path) -> None:
    from tasc.harness import compile_file

    r = compile_file(ROOT / "images" / "work" / "tasc201.dsk", "BALL", tmp_path)
    assert r.obj_sha256 == BALL_OBJ_SHA
    assert r.obj_addr == 0x17B0
    golden, _ = parse_line_table((GOLDEN / "ball_transcript.txt").read_text())
    assert r.line_table == golden
