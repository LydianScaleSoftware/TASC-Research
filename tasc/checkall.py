"""Re-parse every Phase 1 result and report allocation-rule mismatches."""

from __future__ import annotations

import os

from tasc.batch import EXPERIMENTS, load_result
from tasc.objfile import parse


def main() -> None:
    tot = bad = 0
    for fam in sorted(os.listdir(EXPERIMENTS)):
        if not fam.startswith("p1_") or not (EXPERIMENTS / fam).is_dir():
            continue
        for j in sorted(os.listdir(EXPERIMENTS / fam)):
            if not (EXPERIMENTS / fam / j / "result.json").exists():
                continue
            r = load_result(fam, j)
            if not r.ok:
                continue
            o = parse(r.obj(fam), r.obj_addr, r.source)
            tot += 1
            notes = [n for n in o.notes if "ALLOC" in n]
            if notes:
                bad += 1
                print(fam, j, repr(r.source[:60]), notes)
    print(f"{tot} checked, {bad} allocation mismatches")


if __name__ == "__main__":
    main()
