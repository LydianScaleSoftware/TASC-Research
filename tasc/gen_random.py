"""Seeded random Applesoft program generator for differential testing.

Programs are syntactically valid for TASC (compile-only: they are never run),
mix most statement kinds and expression shapes, and use random options.

    python -m tasc.gen_random <family> <count> [seed] [--v2 | --v3] [--unsup]
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
    v2: bool = False
    v3: bool = False  # session 5: RUN, FRE/POS with complex arguments, AND/OR right after a store
    unsup: bool = False  # session 5: unsupported keywords (skipped with a warning), REM! in dead code


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
            if c.v3 and r.random() < 0.3:
                f = r.choice(["FRE", "POS"])
                return f"{f}({sexpr(c) if r.random() < 0.4 else nexpr(c)[0]})", 9
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


def v3_statement(c: Ctx, lines: list[int], cur: int) -> str:
    r = c.r
    k = r.random()
    v = r.choice(c.reals + c.ints)
    o = r.choice(c.reals + c.ints)
    andor = r.choice(["AND", "OR"])
    if k < 0.12:
        return "RUN" + (f" {r.choice(lines)}" if r.random() < 0.5 else "") + (":PRINT:X=1" if r.random() < 0.3 else "")
    if k < 0.3:
        return f"{v}={nexpr(c)[0]}:{r.choice(c.reals)}={v} {andor} {v}"
    if k < 0.42:
        return f"{v}={nexpr(c)[0]}:IF ({v} {andor} {v}) THEN {r.choice(lines)}"
    if k < 0.54:
        return f"{v}={nexpr(c)[0]}:{r.choice(c.reals)}={v} {andor} {r.choice([o, nexpr(c)[0]])}"
    if k < 0.64:
        return f"READ {v}:PRINT {v} {andor} {v}"
    if k < 0.72:
        return f"GET {v}:{r.choice(c.ints)}={v} {andor} ({nexpr(c)[0]})"
    if k < 0.8:
        return f"{v}={nexpr(c)[0]}:{r.choice(c.reals)}=FRE({v})+POS({nexpr(c)[0]})"
    if k < 0.88:
        return f"{r.choice(c.reals)}=FRE({sexpr(c)}):PRINT POS({r.choice(c.strs)})"
    if k < 0.94:
        return r.choice(["REM! CLEAR COMMON", "REM! CLEAR CHAIN"])
    return f"IF ({nexpr(c)[0]}) THEN RUN" + (f" {r.choice(lines)}" if r.random() < 0.5 else "")


UNSUPPORTED = ["DEL 10,20", "SHLOAD", "TRACE", "NOTRACE", "LOMEM: 16384", "RECALL A", "STORE B,C", '& "X:Y",1',
               'LOAD "F"', "SAVE", "CONT", "LIST 10-20", "LIST", "&"]


def unsup_statement(c: Ctx, lines: list[int], cur: int) -> str:
    r = c.r
    k = r.random()
    u = r.choice(UNSUPPORTED)
    if k < 0.4:
        return u
    if k < 0.6:
        return f"IF ({nexpr(c)[0]}) THEN {u}"
    if k < 0.75:
        return f"GOTO {r.choice(lines)}:{u}"
    if k < 0.85:
        return f"GOTO {r.choice(lines)}:REM! " + r.choice(["CLEAR COMMON", "CLEAR CHAIN"])
    t = r.choice(c.reals + c.ints)
    return f"{t}={nexpr(c)[0]}:{u}:{r.choice(c.reals)}={t}"


def statement(c: Ctx, lines: list[int], cur: int, for_stack: list[str]) -> str:
    r = c.r
    if c.unsup and r.random() < 0.25:
        return unsup_statement(c, lines, cur)
    if c.v3 and r.random() < 0.3:
        return v3_statement(c, lines, cur)
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
    if not c.v2:
        return f"INPUT {r.choice(c.reals + c.ints)}"
    k2 = r.random()
    if k2 < 0.1:
        return f"ON {nexpr(c)[0]} GOSUB " + ",".join(str(r.choice(lines)) for _ in range(r.randint(1, 3)))
    if k2 < 0.18:
        return f"ONERR GOTO {r.choice(lines)}"
    if k2 < 0.22:
        return "RESUME"
    if k2 < 0.3:
        return f"GET {r.choice(c.reals + c.ints + c.strs)}"
    if k2 < 0.4:
        pts = f"{nexpr(c)[0]},({nexpr(c)[0]})"
        return "HPLOT " + ("TO " if r.random() < 0.3 else "") + pts + (f" TO {nexpr(c)[0]},({nexpr(c)[0]})" if r.random() < 0.4 else "")
    if k2 < 0.48:
        st = r.choice(["DRAW", "XDRAW"])
        return f"{st} {nexpr(c)[0]}" + (f" AT {nexpr(c)[0]},({nexpr(c)[0]})" if r.random() < 0.5 else "")
    if k2 < 0.53:
        return f"WAIT {nexpr(c)[0]},({nexpr(c)[0]})" + (f",({nexpr(c)[0]})" if r.random() < 0.5 else "")
    if k2 < 0.6:
        st = r.choice(["ROT=", "SCALE=", "HCOLOR=", "PR#", "IN#"])
        return f"{st}{nexpr(c)[0]}"
    if k2 < 0.68:
        vs = ",".join(target(c)[0] for _ in range(r.randint(1, 3)))
        return (f'INPUT "{r.choice(["Q", "NAME", ""])}";' if r.random() < 0.5 else "INPUT ") + vs
    if k2 < 0.76:
        return "READ " + ",".join(target(c)[0] for _ in range(r.randint(1, 3)))
    if k2 < 0.84:
        return f"IF ({nexpr(c)[0]}) THEN RETURN" + (f":{statement(c, lines, cur, [])}" if r.random() < 0.5 else "")
    if k2 < 0.9:
        return f"IF ({nexpr(c)[0]}) THEN IF ({nexpr(c)[0]}) THEN {statement(c, lines, cur, [])}"
    if k2 < 0.95:
        return "STOP"
    return f"GOSUB {r.choice(lines)}:{statement(c, lines, cur, [])}"


def program(seed: int, v2: bool = False, v3: bool = False, unsup: bool = False) -> tuple[str, Options]:
    v2 = v2 or v3
    r = random.Random(seed)
    names = [n for n in ["A", "B", "C", "X", "Y", "Z", "AB", "XY", "Q1", "M", "N2", "W"] if ok_name(n)]
    reals = r.sample(names, 5)
    intdecl = r.sample([n for n in ["I", "J", "K"] if n not in reals], r.randint(0, 2))
    ints = r.sample([n + "%" for n in names], 4) + intdecl
    strs = r.sample([n + "$" for n in names], 3)
    arrays: dict[str, int] = {}
    head: list[str] = []
    if v2 and r.random() < 0.1:
        head.append("REM! INTEGER *")
        ints = [n for n in ints if n.endswith("%")] + [n for n in reals[:2]]
        reals = reals[2:] or ["W"]
    elif intdecl:
        head.append("REM! INTEGER " + ",".join(intdecl))
    if v2 and r.random() < 0.15:
        head.append("REM! " + r.choice(["DEFCOMMON", "USECOMMON"]) + " " + ",".join(r.sample(reals + ints + strs, 3)))
    dims = []
    for nm in r.sample(["A", "B", "D", "P"], r.randint(0, 3)):
        suffix = r.choice(["", "%", "$"])
        nd = r.choice([1, 1, 2])
        arrays[nm + suffix + "()"] = nd
        if r.random() < 0.6:
            dims.append(f"{nm}{suffix}({','.join(str(r.randint(1, 12)) for _ in range(nd))})")
    if dims:
        head.append("DIM " + ",".join(dims))
    c = Ctx(r, reals, ints, strs, arrays, [], v2=v2, v3=v3, unsup=unsup)
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
    mem: dict[str, object] = {}
    if v2 and r.random() < 0.2:
        mem = r.choice([{"library": 0x1000}, {"program": "HGR1"}, {"program": 0x5000}, {"variables": 0x7000},
                        {"library": 0x4000, "program": 0x6000}])
    opts = Options(int_arith=r.random() < 0.7, int_const=r.random() < 0.7, resume=r.random() < 0.25, **mem)  # type: ignore[arg-type]
    return "\n".join(out) + "\n", opts


def main() -> None:
    from tasc.batch import Job, run_family

    fam, count = sys.argv[1], int(sys.argv[2])
    seed0 = int(sys.argv[3]) if len(sys.argv) > 3 else 1000
    v2 = "--v2" in sys.argv
    v3 = "--v3" in sys.argv
    unsup = "--unsup" in sys.argv
    jobs = []
    for i in range(count):
        src, opts = program(seed0 + i, v2, v3, unsup)
        jobs.append(Job(f"r{seed0 + i}", src, opts))
    run_family(fam, jobs, workers=12)


if __name__ == "__main__":
    main()
