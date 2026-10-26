"""TASCAD, the single-script compiler and decompiler (dist/tascad.py)."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parents[1]
BUNDLE = ROOT / "dist" / "tascad.py"
EXTRACTED = ROOT / "extracted" / "tasc201"


def test_bundle_is_current() -> None:
    """dist/tascad.py is what python -m tasc.bundle builds from the current modules."""
    from tasc import bundle

    committed = BUNDLE.read_text()
    bundle.build()
    assert BUNDLE.read_text() == committed, "dist/tascad.py is stale: run python -m tasc.bundle"


def _run(tmp: Path, *args: str) -> subprocess.CompletedProcess[str]:
    # isolated mode in an empty folder: only the bundle itself can supply the modules
    return subprocess.run([sys.executable, "-I", "tascad.py", *args], cwd=tmp, capture_output=True, text=True,
                          check=False)


def test_bundle_compiles_and_decompiles(tmp_path: Path) -> None:
    shutil.copy(BUNDLE, tmp_path / "tascad.py")
    shutil.copy(EXTRACTED / "BALL#fc0801", tmp_path / "BALL.bas")
    shutil.copy(ROOT / "tests" / "golden" / "BALL.OBJ", tmp_path / "BALL.OBJ")
    r = _run(tmp_path, "compile", "BALL.bas", "-o", "OUT.OBJ", "--compare", "BALL.OBJ")
    assert r.returncode == 0 and "identical to BALL.OBJ" in r.stdout, r.stdout + r.stderr
    for p in ("PASS0", "PASS1", "PASS2"):
        shutil.copy(EXTRACTED / f"{p}#0641f2", tmp_path / f"{p}.OBJ")
        shutil.copy(ROOT / "src" / f"{p}.txt", tmp_path / f"{p}.txt")
        r = _run(tmp_path, "compile", f"{p}.txt", "-o", f"{p}.NEW", "--compare", f"{p}.OBJ")
        assert r.returncode == 0 and "identical" in r.stdout, r.stdout + r.stderr
        r = _run(tmp_path, "decompile", f"{p}.OBJ", "-o", f"{p}.dec.txt", "--bas", f"{p}.dec.bas")
        assert r.returncode == 0 and "compiles back to the same" in r.stderr, r.stdout + r.stderr
