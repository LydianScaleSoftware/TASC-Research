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


def test_make_runtime_listing() -> None:
    """MAKE RUNTIME's DATA statements hold exactly RUNTIME's bytes; its DOC file mirrors its
    line numbers (the emulator run is `python -m tasc.makeruntime`)."""
    from tasc.makeruntime import ORIGINAL, documentation, listing

    data = ORIGINAL.read_bytes()
    text = listing(data)
    items = [int(x) for line in text.splitlines() if " DATA " in line for x in line.split(" DATA ")[1].split(",")]
    assert bytes(items) == data
    doc, _ = documentation(data)
    assert [ln.split()[0] for ln in doc.splitlines()] == [ln.split()[0] for ln in text.splitlines()]


def test_source_documentation_is_standalone() -> None:
    """Recovered-source documentation (DOC/VARS files) must read as written on the original
    Apple II: no references to this project's files, tools or hypotheses (Mark, 2026-10-25)."""
    import re

    src = Path(__file__).parents[1] / "src"
    banned = re.compile(r"\bml/|\brag\b|\.md\b|\.py\b|\.hex\b|\.json\b|\bH[1-7]\b|pandowdy|python|cp2|ciderpress|"
                        r"tasc-re|predictor|decompil|experiments/|github|\bgit\b|sha256|pytest|claude",
                        re.IGNORECASE)
    files = list(src.glob("*.DOC.TXT")) + list(src.glob("*.VARS.TXT"))
    assert files
    for f in files:
        for n, line in enumerate(f.read_text().splitlines(), 1):
            assert not banned.search(line), f"{f.name}:{n}: {line[:80]}"
