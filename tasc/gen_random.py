"""Seeded random Applesoft program generator for differential testing.

Programs are syntactically valid for TASC (compile-only: they are never run),
mix most statement kinds and expression shapes, and use random options.

    python -m tasc.gen_random <family> <count> [seed]
"""

from __future__ import annotations

import random
import sys
from dataclasses import dataclass

from tasc.applesoft import strip_keywords
from tasc.harness import Options

PRIO = {"OR": 1, "AND": 2, "=": 3, "<": 3, ">": 3, "<=": 3, ">=": 3, "<>": 3, "+": 4, "-": 4, "*": 5, "/": 5, "^": 6}


def ok_name(n: str) -> bool:
    return strip_keywords(n).replace(" ", "") == n


@dataclass
class Ctx:
    r: random.Random
    reals: list[str]
    ints: list[str]
    strs: list[str]
    arrays: dict[str, int]  # name with suffix -> number of subscripts
    fns: list[str]
    depth: int = 0


def num_lit(r: random.Random) -> str:
    k = r.random()
    if k < 0.55:
        return str(r.choice([0, 1, 2, 3, 5, 7, 10, 20, 24, 39, 40, 100, 127, 255, 256, 1000, 32767]))
    if k < 0.75:
        return str(r.randint(0, 999))
    if k < 0.9:
        return r.choice(["1.5", ".5", "3.14159", "0.1", "2.25", ".001", "1E3", "40000", "65535", "49152"])
    return str(r.randint(0, 50000))


def wrap(s: str, prio: int, parent: int) -> str:
    return f"({s})" if prio < parent else s


def nexpr(c: Ctx, parent: int = 0, want_int: bool = False) -> tuple[str, int]:
    """Numeric expression text and its top priority."""
    r = c.r
    if c.depth > 2 or r.random() < 0.4:
        k = r.random()
        if k < 0.3:
            return num_lit(r), 9
        if k < 0.55 or want_int:
            return r.choice(c.ints), 9
        if k < 0.8:
            return r.choice(c.reals), 9
        if k < 0.9 and c.arrays:
            nums = [a for a in c.arrays if not a.endswith("$()")]
            if nums:
                a = r.choice(nums)
                c.depth += 1
                subs = ",".join(nexpr(c, 0, True)[0] for _ in range(c.arrays[a]))
                c.depth -= 1
                return f"{a[:-2] if a.endswith('()') else a}({subs})", 9
        return r.choice(c.reals + c.ints), 9
    c.depth += 1
    k = r.random()
    try:
        if k < 0.6:
            op = r.choice(["+", "-", "*", "/", "+", "-", "*", "^", "=", "<", ">", "<=", ">=", "<>", "AND", "OR"])
            p = PRIO[op]
            a, pa = nexpr(c, p)
            b, pb = nexpr(c, p + 1)
            s = f"{wrap(a, pa, p)}{op if op.isalpha() is False else ' ' + op + ' '}{wrap(b, pb, p + 1)}"
            return wrap(s, p, parent), p
        if k < 0.7:
            a, pa = nexpr(c, 8)
            return wrap("-" + wrap(a, pa, 8), 7, parent), 7
        if k < 0.75:
            a, pa = nexpr(c, 8)
            return wrap("NOT " + wrap(a, pa, 8), 7, parent), 7
        if k < 0.9:
            f = r.choice(["ABS", "INT", "SGN", "SQR", "PEEK", "RND", "SIN", "COS", "ATN", "EXP", "LOG", "TAN"])
            return f"{f}({nexpr(c)[0]})", 9
        if k < 0.95:
            f = r.choice(["LEN", "ASC", "VAL"])
            return f"{f}({sexpr(c)})", 9
        if c.fns:
            return f"FN {r.choice(c.fns)}({nexpr(c)[0]})", 9
        return f"({nexpr(c)[0]})", 9
    finally:
        c.depth -= 1


def sexpr(c: Ctx) -> str:
    r = c.r
    if c.depth > 2 or r.random() < 0.5:
        k = r.random()
        if k < 0.35:
            return '"' + r.choice(["", "A", "HI", "TASC", "X Y", "123"]) + '"'
        if k < 0.85 or not any(a.endswith("$()") for a in c.arrays):
            return r.choice(c.strs)
        a = r.choice([a for a in c.arrays if a.endswith("$()")])
        c.depth += 1
        subs = ",".join(nexpr(c, 0, True)[0] for _ in range(c.arrays[a]))
        c.depth -= 1
        return f"{a[:-2]}({subs})"
    c.depth += 1
    try:
        k = r.random()
        if k < 0.4:
            return f"{sexpr(c)}+{sexpr(c)}"
        if k < 0.55:
            return f"LEFT$({sexpr(c)},{nexpr(c)[0]})"
        if k < 0.65:
            return f"RIGHT$({sexpr(c)},{nexpr(c)[0]})"
        if k < 0.75:
            return f"MID$({sexpr(c)},{nexpr(c)[0]})"
        if k < 0.82:
            return f"MID$({sexpr(c)},{nexpr(c)[0]},{nexpr(c)[0]})"
        if k < 0.9:
            return f"STR$({nexpr(c)[0]})"
        return f"CHR$({nexpr(c)[0]})"
    finally:
        c.depth -= 1


def target(c: Ctx) -> tuple[str, str]:
    r = c.r
    k = r.random()
    arrs = list(c.arrays)
    if k < 0.15 and arrs:
        a = r.choice(arrs)
        subs = ",".join(nexpr(c, 0, True)[0] for _ in range(c.arrays[a]))
        return f"{a[:-2]}({subs})", ("str" if a.endswith("$()") else "num")
    if k < 0.4:
        return r.choice(c.ints), "num"
    if k < 0.75:
        return r.choice(c.reals), "num"
    return r.choice(c.strs), "str"


def statement(c: Ctx, lines: list[int], cur: int, for_stack: list[str]) -> str:
    r = c.r
    k = r.random()
    later = [n for n in lines if n > cur] or [cur]
    if k < 0.35:
        t, kind = target(c)
        return f"{t}={sexpr(c) if kind == 'str' else nexpr(c)[0]}"
    if k < 0.47:
        items = []
        for _ in range(r.randint(0, 3)):
            items.append(sexpr(c) if r.random() < 0.4 else nexpr(c)[0])
            items.append(r.choice([";", ",", ";"]))
        if items and items[-1] == "":
            items.pop()
        s = "PRINT " + "".join(x if x in (";", ",") else x for x in items)
        return s.replace(";;", ";").replace(",,", ",") if not s.endswith(" ") else "PRINT"
    if k < 0.57:
        return f"IF ({nexpr(c)[0]}) THEN {r.choice(lines)}" if r.random() < 0.4 else f"IF ({nexpr(c)[0]}) THEN {statement(c, lines, cur, [])}"
    if k < 0.6:
        return f"GOTO {r.choice(lines)}"
    if k < 0.63:
        return f"GOSUB {r.choice(lines)}"
    if k < 0.66:
        return f"ON {nexpr(c)[0]} GOTO " + ",".join(str(r.choice(lines)) for _ in range(r.randint(1, 4)))
    if k < 0.72:
        v = r.choice(c.reals + [x for x in c.ints if not x.endswith("%")])
        step = f" STEP ({nexpr(c)[0]})" if r.random() < 0.3 else ""
        for_stack.append(v)
        return f"FOR {v}=({nexpr(c)[0]}) TO ({nexpr(c)[0]}){step}"
    if k < 0.76 and for_stack:
        return "NEXT " + for_stack.pop() if r.random() < 0.8 else (for_stack.pop() and "NEXT")
    if k < 0.84:
        st = r.choice(["VTAB", "HTAB", "COLOR=", "CALL", "HCOLOR=", "SPEED="])
        return f"{st}{' ' if not st.endswith('=') else ''}{nexpr(c)[0]}"
    if k < 0.88:
        return r.choice([f"PLOT {nexpr(c)[0]},{nexpr(c)[0]}", f"POKE {nexpr(c)[0]},{nexpr(c)[0]}",
                         f"HLIN {nexpr(c)[0]},({nexpr(c)[0]}) AT {nexpr(c)[0]}"])
    if k < 0.91:
        return r.choice(["HOME", "TEXT", "GR", "NORMAL", "INVERSE", "RETURN", "POP", "RESTORE", "END"])
    if k < 0.94:
        return "READ " + ",".join(r.choice(c.reals + c.ints + c.strs) for _ in range(r.randint(1, 2)))
    if k < 0.97:
        return "DATA " + ",".join(r.choice(["1", "-2.5", "HI", '"A,B"', "", "300", "X"]) for _ in range(r.randint(1, 4)))
    return f"INPUT {r.choice(c.reals + c.ints)}"


def program(seed: int) -> tuple[str, Options]:
    r = random.Random(seed)
    names = [n for n in ["A", "B", "C", "X", "Y", "Z", "AB", "XY", "Q1", "M", "N2", "W"] if ok_name(n)]
    reals = r.sample(names, 5)
    intdecl = r.sample([n for n in ["I", "J", "K"] if n not in reals], r.randint(0, 2))
    ints = r.sample([n + "%" for n in names], 4) + intdecl
    strs = r.sample([n + "$" for n in names], 3)
    arrays: dict[str, int] = {}
    head: list[str] = []
    if intdecl:
        head.append("REM! INTEGER " + ",".join(intdecl))
    dims = []
    for nm in r.sample(["A", "B", "D", "P"], r.randint(0, 3)):
        suffix = r.choice(["", "%", "$"])
        nd = r.choice([1, 1, 2])
        arrays[nm + suffix + "()"] = nd
        if r.random() < 0.6:
            dims.append(f"{nm}{suffix}({','.join(str(r.randint(1, 12)) for _ in range(nd))})")
    if dims:
        head.append("DIM " + ",".join(dims))
    c = Ctx(r, reals, ints, strs, arrays, [])
    if r.random() < 0.4:
        head.append(f"DEF FN F({r.choice(['Z', 'T', 'X'])})={nexpr(c)[0]}")
        c.fns = ["F"]
    n = r.randint(8, 30)
    lines = [10 * (i + 1) for i in range(len(head) + n)]
    out = []
    for_stack: list[str] = []
    for i, ln in enumerate(lines):
        if i < len(head):
            out.append(f"{ln} {head[i]}")
            continue
        stmts = [statement(c, lines, ln, for_stack) for _ in range(r.randint(1, 3))]
        text = ":".join(stmts)
        if len(text) > 200:
            text = stmts[0][:200]
        out.append(f"{ln} {text}")
    opts = Options(int_arith=r.random() < 0.7, int_const=r.random() < 0.7, resume=r.random() < 0.25)
    return "\n".join(out) + "\n", opts


def main() -> None:
    from tasc.batch import Job, run_family

    fam, count = sys.argv[1], int(sys.argv[2])
    seed0 = int(sys.argv[3]) if len(sys.argv) > 3 else 1000
    jobs = []
    for i in range(count):
        src, opts = program(seed0 + i)
        jobs.append(Job(f"r{seed0 + i}", src, opts))
    run_family(fam, jobs, workers=12)


if __name__ == "__main__":
    main()
