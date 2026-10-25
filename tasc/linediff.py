"""First differing source line between TASC's object and the predictor's.

    python -m tasc.linediff <family> <job> [more jobs...]

Compares per line, with code rendered symbolically and addresses normalised
(routine entries by op number only, line/label targets dropped).
"""

from __future__ import annotations

import re
import sys

from tasc.batch import EXPERIMENTS, load_result
from tasc.compiler.assemble import compile_program
from tasc.objfile import CodeItem, parse
from tasc.predict_check import options_of


KEEP = ("JSR", "JMP", "LDA", "ORA", "BNE", "BEQ", "RTS", "STR")


def norm(t: str) -> str:
    if not t.startswith(KEEP):
        return "?"  # data bytes decoded as code: address-dependent
    t = re.sub(r"\b(V[0-9A-F]{4}|[A-Z][A-Z0-9]?)[%$]?(\(\))?\.op", "V.op", t)
    t = re.sub(r"K\([^)]*\)\.op", "K.op", t)
    t = re.sub(r"\$[0-9A-F]{4}|@\+-?\d+", "$", t)
    return t


def by_line(code: list[CodeItem], table: dict[int, int]) -> dict[int, list[str]]:
    starts = sorted(table.items(), key=lambda kv: (kv[1], kv[0]))
    out: dict[int, list[str]] = {}
    for i, (ln, a) in enumerate(starts):
        nxt = next((b for _, b in starts[i + 1 :] if b > a), 1 << 20)
        out[ln] = [norm(c.text) for c in code if a <= c.addr < nxt] if all(b != a for _, b in starts[i + 1 :]) else []
    return out


def first_diff(family: str, job: str) -> str:
    r = load_result(family, job)
    res = compile_program((EXPERIMENTS / family / job / "source.bas").read_bytes(), options_of(r.options))
    real = r.obj(family)
    if res.data == real and res.load == r.obj_addr:
        return f"{job}: identical"
    a = parse(real, r.obj_addr)
    b = parse(res.data, res.load)
    ta = {e.line: e.addr for e in r.line_table}
    tb = {n: v for n, v in res.line_addr.items() if n >= 0}
    la, lb = by_line(a.code, ta), by_line(b.code, tb)
    src = {int(l.split()[0]): l for l in r.source.splitlines() if l.strip()}
    for ln in sorted(ta):
        if la.get(ln) != lb.get(ln):
            return (f"{job}: first differing line {ln}: {src.get(ln, '')[:150]}\n"
                    f"   TASC: {' | '.join(la.get(ln, []))}\n   PRED: {' | '.join(lb.get(ln, []))}")
    return f"{job}: code lines equal; difference in pools/routines/locals (len {len(res.data)} vs {len(real)})"


if __name__ == "__main__":
    fam = sys.argv[1]
    for j in sys.argv[2:]:
        print(first_diff(fam, j))
