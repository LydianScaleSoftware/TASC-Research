"""Decompile a TASC object file to tokenized Applesoft and verify it by recompiling.

    python -m tasc.decomp.decompile <family> <job>      (a recorded experiment)
    python -m tasc.decomp.decompile --file <OBJ> <load> (any object file)
    python -m tasc.decomp.decompile --corpus [prefix]   (round-trip every recorded compile)
"""

from __future__ import annotations

import sys
from collections import Counter
from dataclasses import dataclass, field

from tasc.compiler.assemble import compile_program
from tasc.compiler.codegen import Compiler
from tasc.decomp import names as N
from tasc.decomp.lift import Lifted, Stmt, lift
from tasc.decomp.render import Line, Renderer, layout, listing, program_bytes
from tasc.decomp.walk import Sym, walk
from tasc.harness import Options

DECL_WIDTH = 200


@dataclass
class Decompiled:
    lifted: Lifted
    lines: list[Line]
    names: dict[Sym, str]
    program: bytes = b""
    text: str = ""
    decl_lines: list[tuple[int, bytes]] = field(default_factory=list)
    body_lines: list[tuple[int, bytes]] = field(default_factory=list)
    line_addr: dict[int, int] = field(default_factory=dict)  # line number -> original address


class DecompileError(Exception):
    pass


def _named(lf: Lifted) -> list[Sym]:
    return [s for s in lf.walk.syms.values()
            if s.region in ("local", "common") and s.kind == "var" and s not in lf.temps]


def _decl_int(lf: Lifted) -> set[Sym]:
    out: set[Sym] = set()
    for o in lf.walk.ops:
        if o.kind == "rt" and o.name == "IFOR.INIT" and o.sym is not None:
            out.add(o.sym)
    return out


def _render_all(d: Decompiled, names: dict[Sym, str], decl_int: set[Sym]) -> None:
    lf = d.lifted
    w = lf.walk
    h = w.header
    # declarations: COMMON (declaration order = address order, numeric then string), INTEGER, DIM
    decl: list[bytes] = []
    common = sorted((s for s in w.syms.values() if s.region == "common"), key=lambda s: s.addr)
    if common:
        kw = b"USECOMMON " if w.obj.header.flag == 0xFF else b"DEFCOMMON "
        parts = [names[s].encode() + (b"(" + b",".join(str(x).encode() for x in s.dims) + b")" if s.array else b"")
                 for s in common]
        _chunked(decl, b"\xb2! " + kw, parts)
    ints = sorted(decl_int, key=lambda s: s.addr)
    if ints:
        _chunked(decl, b"\xb2! INTEGER ", [names[s].encode() for s in ints])
    arrays = sorted((s for s in _named(lf) if s.array and s.region == "local"), key=lambda s: s.addr)
    if arrays:
        parts = [names[s].encode() + b"(" + b",".join(str(x).encode() for x in s.dims) + b")" for s in arrays]
        _chunked(decl, b"\x86", parts)
    first = 5 * (len(decl) + 1) if decl else 10
    first = ((first + 9) // 10) * 10
    lines = layout(lf, 5, first)
    d.lines = lines
    line_of = {ln.addr: ln.number for ln in lines}
    if decl and common:
        # manual 8.2.4: lines up to the last COMMON declaration keep program start + 20
        line_of.setdefault(h["COMBEG1"] + 1 + 20, 5 * len(decl))
    final_end = _final_end(lf)
    if final_end is not None:
        line_of.setdefault(final_end, -1)
    fn_names: dict[int, str] = {}
    pool = N.NamePool({(n.rstrip("%$"), n[-1] if n[-1] in "%$" else "", s.array) for s, n in names.items()})
    params: dict[Sym, str] = {}
    for f in sorted(lf.fns.values(), key=lambda f: f.addr):
        fn_names[f.addr] = pool.take(None, 0, "fn", False)
        params[f.param] = pool.take(None, 0, "", False, prefer="")
    r = Renderer(names, line_of, fn_names, params)
    d.decl_lines = [(5 * (i + 1), b) for i, b in enumerate(decl)]
    body: list[tuple[int, bytes]] = []
    for ln in lines:
        parts = [r.stmt(st) for st in ln.stmts if not (st is lf.stmts[-1] and st.kind == "END" and final_end is not None)]
        if not parts:
            continue
        body.append((ln.number, b":".join(parts)))
        d.line_addr[ln.number] = ln.addr
    d.body_lines = body
    d.program = program_bytes(d.decl_lines + body)
    d.text = listing(d.decl_lines + body)


def _final_end(lf: Lifted) -> int | None:
    last = lf.stmts[-1] if lf.stmts else None
    if last is not None and last.kind == "END" and last.end == lf.walk.obj.code_end:
        return last.addr
    return None


def _chunked(out: list[bytes], head: bytes, parts: list[bytes]) -> None:
    cur = b""
    for p in parts:
        if cur and len(head) + len(cur) + 1 + len(p) > DECL_WIDTH:
            out.append(head + cur)
            cur = b""
        cur = cur + b"," + p if cur else p
    if cur:
        out.append(head + cur)


def _compile(program: bytes, opts: Options) -> tuple[bytes, Compiler, dict[int, int]]:
    res = compile_program(program, opts)
    return res.data, res.compiler, res.line_addr


def decompile(data: bytes, load: int, opts: Options | None = None) -> Decompiled:
    opts = opts or Options()
    w = walk(data, load)
    lf = lift(w)
    # the appended final JMP END is not a source statement
    d = Decompiled(lf, [], {})
    decl_int = _decl_int(lf)
    named = _named(lf)
    # pass 1: provisional names, to learn insertion order
    pool = N.NamePool(set())
    prov: dict[Sym, str] = {}
    for s in sorted(named, key=lambda s: s.addr):
        suf = N.suffix(s, s in decl_int)
        prov[s] = pool.take(None, 0, suf, s.array) + suf
    _render_all(d, prov, decl_int)
    _, c, _ = _compile(d.program, opts)
    seq: dict[Sym, int] = {}
    for s, n in prov.items():
        key = (n.rstrip("%$"), n[-1] if n[-1] in "%$" else "", s.array)
        ps = c.syms.get(key)
        if ps is None:
            raise DecompileError(f"provisional {n} not in the compiler's symbol table")
        seq[s] = ps.seq
    # pass 2: names from the hash order
    final: dict[Sym, str] = {}
    pool = N.NamePool(set())
    routine_pos = {r.target: i for i, r in enumerate(w.obj.routines)}
    groups = [
        [s for s in named if not s.array and s.vtype != "str"],
        [s for s in named if s.array and s.vtype != "str"],
        [s for s in named if s.vtype == "str"],
    ]
    for g in groups:
        if not g:
            continue
        by_addr = sorted((s for s in g if s.region == "local"), key=lambda s: s.addr)
        by_rtn = sorted((s for s in g if s.addr in routine_pos and s.routine is not None), key=lambda s: routine_pos[s.addr])
        order = N.merge_orders(g, [by_addr, by_rtn], seq)
        bk = N.buckets_for(order, seq)
        for s in order:
            di = s in decl_int
            suf = N.suffix(s, di)
            final[s] = pool.take(bk[s], N.type_hash(s, di), suf, s.array) + suf
    d.names = final
    _render_all(d, final, decl_int)
    return d


def compare(d: Decompiled, data: bytes, load: int, opts: Options) -> str:
    try:
        res = compile_program(d.program, opts)
    except Exception as exc:  # noqa: BLE001
        return f"recompile failed: {type(exc).__name__}: {exc}"
    if res.data == data and res.load == load:
        return "identical"
    if res.load != load:
        return f"load ${res.load:04X} != ${load:04X}"
    # first differing line by address
    ours = sorted((a, n) for n, a in res.line_addr.items() if n >= 0)
    off = next((i for i in range(min(len(data), len(res.data))) if data[i] != res.data[i]), min(len(data), len(res.data)))
    addr = load + off
    ln = max((n for a, n in ours if a <= addr), default=None)
    return f"differs at ${addr:04X} (+{off}), line {ln}; len {len(res.data)} vs {len(data)}"


def _corpus(prefix: str) -> None:
    from tasc.batch import EXPERIMENTS, load_result
    from tasc.predict_check import options_of
    stats: Counter[str] = Counter()
    fails: list[str] = []
    for dd in sorted(EXPERIMENTS.glob(f"{prefix}*/*")):
        if not (dd / "result.json").exists() or not (dd / "OBJ.bin").exists():
            continue
        r = load_result(dd.parent.name, dd.name)
        if not r.ok:
            continue
        data = r.obj(dd.parent.name)
        opts = options_of(r.options)
        try:
            d = decompile(data, r.obj_addr, opts)
            res = compare(d, data, r.obj_addr, opts)
        except Exception as exc:  # noqa: BLE001
            res = f"error {type(exc).__name__}: {str(exc)[:90]}"
        key = res if res == "identical" else res.split(":")[0].split(" at ")[0][:60]
        stats[key] += 1
        if res != "identical":
            fails.append(f"{dd.parent.name}/{dd.name}: {res}")
    for k, n in stats.most_common():
        print(f"{n:5d}  {k}")
    for f in fails[:60]:
        print("  ", f)


def main() -> None:
    a = sys.argv[1:]
    if a and a[0] == "--corpus":
        _corpus(a[1] if len(a) > 1 else "p")
        return
    if a and a[0] == "--file":
        data = open(a[1], "rb").read()
        load = int(a[2], 0)
        opts = Options()
    else:
        from tasc.batch import load_result
        from tasc.predict_check import options_of
        r = load_result(a[0], a[1])
        data, load, opts = r.obj(a[0]), r.obj_addr, options_of(r.options)
        print(r.source)
        print("-----")
    d = decompile(data, load, opts)
    print(d.text)
    print(compare(d, data, load, opts))


if __name__ == "__main__":
    main()


def explain(data: bytes, load: int, opts: Options, ctx: int = 4) -> str:
    """First differing op between the original and the recompiled decompilation."""
    d = decompile(data, load, opts)
    res = compile_program(d.program, opts)
    a = walk(data, load).ops
    b = walk(res.data, res.load).ops

    def key(o: object) -> str:
        r = repr(o).split(" ", 1)[1]
        import re
        r = re.sub(r"[lcm][0-9A-F]{4}", "v", r)
        return re.sub(r"\$[0-9A-F]{4}|0x[0-9a-f]+", "$", r)

    i = next((k for k in range(min(len(a), len(b))) if key(a[k]) != key(b[k])), min(len(a), len(b)))
    out = [d.text, f"first differing op #{i}"]
    for k in range(max(0, i - ctx), min(max(len(a), len(b)), i + ctx)):
        oa = repr(a[k]) if k < len(a) else ""
        ob = repr(b[k]) if k < len(b) else ""
        out.append(f"{'>' if k == i else ' '} {oa:<44} | {ob}")
    return "\n".join(out)
