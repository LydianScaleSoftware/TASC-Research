"""Backfill experiments/*/*/source.bas (tokenized source) using cp2, in batches."""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from tasc import disk
from tasc.batch import BASE, EXPERIMENTS


def main() -> None:
    todo = [d for d in EXPERIMENTS.glob("p1_*/*") if (d / "source.txt").exists() and not (d / "source.bas").exists()]
    print(len(todo), "to tokenize")
    for i in range(0, len(todo), 60):
        chunk = todo[i : i + 60]
        with tempfile.TemporaryDirectory() as td:
            img = Path(td) / "t.dsk"
            shutil.copyfile(BASE, img)
            for j, d in enumerate(chunk):
                src = Path(td) / f"T{j:03d}.txt"
                txt = (d / "source.txt").read_text()
                src.write_text(txt if txt.endswith("\n") else txt + "\n")
                disk.import_basic(img, src, f"T{j:03d}")
            files = disk.extract_all(img)
            for j, d in enumerate(chunk):
                (d / "source.bas").write_bytes(files[f"T{j:03d}"].data)
        print(i + len(chunk), "done")


if __name__ == "__main__":
    main()
