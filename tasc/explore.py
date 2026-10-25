"""Ad-hoc helpers for Phase 1 exploration: run a family and print symbolic listings."""

from __future__ import annotations

import sys

from tasc.batch import Job, load_result, run_family
from tasc.objfile import parse


def show(family: str, ids: list[str], full: bool = False) -> None:
    for j in ids:
        r = load_result(family, j)
        if not r.ok:
            print(f"== {j}: FAILED {r.error.splitlines()[-1] if r.error else ''}")
            continue
        o = parse(r.obj(family), r.obj_addr, r.source)
        print(f"== {j}: {r.source.strip()!r}")
        if full:
            print(o.listing(), end="")
        else:
            print("   code:", " | ".join(o.symbolic()))
            print("   rtns:", ", ".join(f"{rt.name}{sorted(rt.entries.values(), reverse=True)}" for rt in o.routines))
            for n in o.notes:
                print("   NOTE", n)


def run_and_show(family: str, sources: dict[str, str], full: bool = False, workers: int = 8) -> None:
    run_family(family, [Job(k, v) for k, v in sources.items()], workers=workers)
    show(family, list(sources), full)


if __name__ == "__main__":
    show(sys.argv[1], sys.argv[2:], full=True)
