"""Decompile TASC object files to tokenized Applesoft and verify by recompiling.

    python -m tasc.decomp.decompile <family> <job>       (a recorded experiment)
    python -m tasc.decomp.decompile --file <OBJ> <load>  (any object file)
    python -m tasc.decomp.decompile --pass               (PASS0/1/2 together, shared COMMON)
    python -m tasc.decomp.decompile --corpus [prefix]    (round-trip every recorded compile)

Declarations come first: `REM! INTEGER` for every integer scalar and integer
array (so integers are entered into the symbol table in an order we choose),
then the COMMON declaration (address order), then DIM for the other local
arrays.  Several object files that share COMMON (TASC's three passes) are
named jointly, so a COMMON variable has one name everywhere.
"""

from __future__ import annotations

import re
import sys
from collections import Counter
from collections.abc import Iterator
from dataclasses import dataclass, field

from tasc.compiler.assemble import compile_program
from tasc.compiler.parse import TOK
from tasc.decomp import names as N
from tasc.decomp.lift import BinN, FnDef, Leaf, Lifted, lift
from tasc.decomp.lift import Node as ExprNode
from tasc.decomp.render import Line, Renderer, layout, listing, program_bytes
from tasc.decomp.walk import Sym, walk
from tasc.harness import Options

DECL_WIDTH = 200
REM, DIM = bytes([TOK["REM"]]), bytes([TOK["DIM"]])


class DecompileError(Exception):
    pass


@dataclass
class Unit:
    """One object file being decompiled."""
    data: bytes
    load: int
    opts: Options
    name: str = ""
    lf: Lifted | None = None
    named: list[Sym] = field(default_factory=list)
    ints: list[Sym] = field(default_factory=list)  # REM! INTEGER, in declaration order
    dims: list[Sym] = field(default_factory=list)  # DIM, in declaration order
    names: dict[Sym, str] = field(default_factory=dict)
    lines: list[Line] = field(default_factory=list)
    decl_lines: list[tuple[int, bytes]] = field(default_factory=list)
    body_lines: list[tuple[int, bytes]] = field(default_factory=list)
    line_addr: dict[int, int] = field(default_factory=dict)  # line number -> original address
    program: bytes = b""
    text: str = ""

    @property
    def lifted(self) -> Lifted:
        assert self.lf is not None
        return self.lf


Decompiled = Unit


# ---------------------------------------------------------------- symbols and declarations

def _named(lf: Lifted) -> list[Sym]:
    return [s for s in lf.walk.syms.values()
            if s.region in ("local", "common") and s.kind == "var" and s not in lf.temps]


def _commons(u: Unit) -> list[Sym]:
    return sorted((s for s in u.lifted.walk.syms.values() if s.region == "common"), key=lambda s: s.addr)


def _seq_class(s: Sym) -> int:
    """Insertion class: 0 REM! INTEGER (free order), 1 COMMON declaration (address order),
    2 DIM (free order), 3 first scan in the code."""
    if s.vtype == "int":
        return 0
    if s.region == "common":
        return 1
    if s.array:
        return 2
    return 3


def _decl_text(u: Unit, names: dict[Sym, str]) -> list[bytes]:
    out: list[bytes] = []

    def dimtxt(s: Sym) -> bytes:
        return b"(" + b",".join(str(x).encode() for x in s.dims) + b")"

    if u.ints:
        _chunked(out, REM + b"! INTEGER ", [names[s].encode() + (dimtxt(s) if s.array else b"") for s in u.ints])
    common = _commons(u)
    if common:
        kw = b"USECOMMON " if u.lifted.walk.obj.header.flag == 0xFF else b"DEFCOMMON "
        _chunked(out, REM + b"! " + kw, [names[s].encode() + (dimtxt(s) if s.array else b"") for s in common])
    if u.dims:
        _chunked(out, DIM, [names[s].encode() + dimtxt(s) for s in u.dims])
    return out


def _chunked(out: list[bytes], head: bytes, parts: list[bytes]) -> None:
    cur = b""
    for p in parts:
        if cur and len(head) + len(cur) + 1 + len(p) > DECL_WIDTH:
            out.append(head + cur)
            cur = b""
        cur = cur + b"," + p if cur else p
    if cur:
        out.append(head + cur)


def _final_end(lf: Lifted) -> int | None:
    last = lf.stmts[-1] if lf.stmts else None
    if last is not None and last.kind == "END" and last.end == lf.walk.obj.code_end:
        return last.addr
    return None


def _render(u: Unit, names: dict[Sym, str]) -> None:
    lf = u.lifted
    h = lf.walk.header
    decl = _decl_text(u, names)
    first = ((5 * (len(decl) + 1) + 9) // 10) * 10 if decl else 10
    u.lines = layout(lf, 5, first)
    line_of = {ln.addr: ln.number for ln in u.lines}
    if decl and _commons(u):
        # manual 8.2.4: lines up to the last COMMON declaration keep program start + 20
        last_common = max(i for i, b in enumerate(decl) if b"COMMON" in b[:12]) + 1
        line_of.setdefault(h["COMBEG1"] + 1 + 20, 5 * last_common)
    final_end = _final_end(lf)
    if final_end is not None:
        line_of.setdefault(final_end, -1)
    pool = N.NamePool({(n.rstrip("%$"), n[-1] if n[-1] in "%$" else "", s.array) for s, n in names.items()})
    fn_names: dict[int, str] = {}
    params: dict[Sym, str] = {}
    for f in sorted(lf.fns.values(), key=lambda f: f.addr):
        fn_names[f.addr] = pool.take(None, 0, "fn", False)
        params[f.param] = pool.take(None, 0, "", False)
    r = Renderer(names, line_of, fn_names, params)
    pre = [s for s in u.ints if not s.array] or [s for s in _commons(u) if not s.array]
    if pre:
        r.filler = names[pre[0]].encode()
    u.decl_lines = [(5 * (i + 1), b) for i, b in enumerate(decl)]
    u.body_lines = []
    u.line_addr = {}
    for ln in u.lines:
        sts = [st for st in ln.stmts if not (st is lf.stmts[-1] and final_end is not None)]
        if sts:
            body = r.stmt(sts[0])
            for prev, st in zip(sts, sts[1:]):
                body += (b"" if prev.kind == "IF" else b":") + r.stmt(st)  # IF c THEN stmt
            u.body_lines.append((ln.number, body))
            u.line_addr[ln.number] = ln.addr
        elif ln.addr == final_end and final_end in lf.line_starts:
            # a jump to the appended final END (e.g. to a RESUME line, no code with the
            # option off): a line that generates no code
            u.body_lines.append((ln.number, REM))
            u.line_addr[ln.number] = ln.addr
    u.program = program_bytes(u.decl_lines + u.body_lines)
    u.text = listing(u.decl_lines + u.body_lines)


# ---------------------------------------------------------------- joint naming

@dataclass(eq=False)
class Node:
    key: object
    syms: list[tuple[int, Sym]]  # (unit index, symbol)
    cls: int
    rank: int = 0  # class 1: address; class 3: provisional scan seq (per unit, see seqs)
    seqs: dict[int, int] = field(default_factory=dict)
    t: int = 0  # type hash
    suf: str = ""
    array: bool = False
    bucket: int = 0


def _weight(x: Node, y: Node, unit: int) -> int:
    """1 when y must be in a later bucket than x (y entered the symbol table earlier)."""
    if x.cls != y.cls:
        return 1 if y.cls < x.cls else 0
    if x.cls in (0, 2):
        return 0  # declared in the order we choose
    if x.cls == 1:
        return 1 if y.rank < x.rank else 0
    return 1 if y.seqs[unit] < x.seqs[unit] else 0


def _solve_group(nodes: list[Node], edges: dict[tuple[Node, Node], int]) -> list[Node]:
    """Topological order and buckets: nondecreasing along edges, +1 on weighted edges,
    spread over the 32 buckets to leave room for names."""
    succ: dict[Node, list[Node]] = {n: [] for n in nodes}
    pred: dict[Node, list[Node]] = {n: [] for n in nodes}
    for (a, b) in edges:
        succ[a].append(b)
        pred[b].append(a)
    indeg = {n: len(pred[n]) for n in nodes}
    ready = sorted((n for n in nodes if indeg[n] == 0), key=lambda n: (n.cls, n.rank))
    order: list[Node] = []
    while ready:
        n = ready.pop(0)
        order.append(n)
        for m in succ[n]:
            indeg[m] -= 1
            if indeg[m] == 0:
                ready.append(m)
                ready.sort(key=lambda n: (n.cls, n.rank))
    if len(order) != len(nodes):
        raise DecompileError("cyclic symbol-order constraints")
    tail = {n: 0 for n in nodes}
    for n in reversed(order):
        for m in succ[n]:
            tail[n] = max(tail[n], tail[m] + edges[(n, m)])
    for i, n in enumerate(order):
        lo = max((p.bucket + edges[(p, n)] for p in pred[n]), default=0)
        hi = 31 - tail[n]
        if lo > hi:
            raise DecompileError(f"symbol order needs more than 32 buckets ({lo} > {hi})")
        n.bucket = min(max(lo, i * 32 // len(order)), hi)
    return order


def _assign_names(units: list[Unit], seqs: list[dict[Sym, int]]) -> list[dict[Sym, str]]:
    nodes: dict[object, Node] = {}
    for ui, u in enumerate(units):
        for s in u.named:
            key: object = ("C", s.addr) if s.region == "common" else (ui, id(s))
            n = nodes.get(key)
            if n is None:
                cls = _seq_class(s)
                n = Node(key, [], cls, rank=s.addr if cls == 1 else 0, t=N.type_hash(s, s.vtype == "int"),
                         suf=N.suffix(s, s.vtype == "int"), array=s.array)
                nodes[key] = n
            n.syms.append((ui, s))
            if s in seqs[ui]:
                n.seqs[ui] = seqs[ui][s]
    of: dict[tuple[int, int], Node] = {(ui, id(s)): n for n in nodes.values() for ui, s in n.syms}
    groups: dict[str, list[Node]] = {"num": [], "arr": [], "str": []}

    def gname(s: Sym) -> str:
        return "str" if s.vtype == "str" else ("arr" if s.array else "num")

    for n in nodes.values():
        groups[gname(n.syms[0][1])].append(n)
    edges: dict[tuple[Node, Node], int] = {}
    for ui, u in enumerate(units):
        w = u.lifted.walk
        rpos = {r.target: i for i, r in enumerate(w.obj.routines)}
        for g in ("num", "arr", "str"):
            mine = [s for s in u.named if gname(s) == g]
            chains = [sorted((s for s in mine if s.region == "local"), key=lambda s: s.addr),
                      sorted((s for s in mine if s.routine is not None and s.addr in rpos), key=lambda s: rpos[s.addr])]
            for ch in chains:
                for a, b in zip(ch, ch[1:]):
                    na, nb = of[(ui, id(a))], of[(ui, id(b))]
                    edges[(na, nb)] = max(edges.get((na, nb), 0), _weight(na, nb, ui))
    out: list[dict[Sym, str]] = [{} for _ in units]
    pools = [N.NamePool(set()) for _ in units]
    for g, gn in groups.items():
        if not gn:
            continue
        order = _solve_group(gn, {k: v for k, v in edges.items() if k[0] in gn})
        # COMMON names first (shared), then each unit's locals
        for n in sorted(order, key=lambda n: 0 if isinstance(n.key, tuple) and n.key[0] == "C" else 1):
            uis = [ui for ui, _ in n.syms]
            name = _take_shared(pools, uis, n)
            for ui, s in n.syms:
                out[ui][s] = name + n.suf
        for ui, u in enumerate(units):
            if g == "num":
                u.ints = [s for n in order for vi, s in n.syms if vi == ui and s.vtype == "int"]
            if g == "arr":
                u.ints += [s for n in order for vi, s in n.syms if vi == ui and s.vtype == "int"]
                u.dims = [s for n in order for vi, s in n.syms if vi == ui and s.vtype != "int" and s.region == "local"]
            if g == "str":
                u.dims += [s for n in order for vi, s in n.syms if vi == ui and s.array and s.region == "local"]
    return out


def _take_shared(pools: list[N.NamePool], uis: list[int], n: Node) -> str:
    for cand in [c1 + c2 for c1 in N.LETTERS for c2 in N.SECOND]:
        if not N._ok(cand) or N.bucket(cand, n.t) != n.bucket:
            continue
        if all((cand, n.suf, n.array) not in pools[ui].used for ui in uis):
            for ui in uis:
                pools[ui].used.add((cand, n.suf, n.array))
            return cand
    raise DecompileError(f"no free name in bucket {n.bucket}")


# ---------------------------------------------------------------- driver

def complete_common(units: list[Unit]) -> None:
    """Give every unit the union of the COMMON variables seen in any unit."""
    layout_: dict[int, Sym] = {}
    for u in units:
        for s in _commons(u):
            prev = layout_.get(s.addr)
            if prev is not None and (prev.vtype, prev.array, prev.dims) != (s.vtype, s.array, s.dims):
                raise DecompileError(f"COMMON ${s.addr:04X} disagrees between units")
            layout_.setdefault(s.addr, s)
    for u in units:
        w = u.lifted.walk
        for a, s in layout_.items():
            if a not in w.syms:
                w.syms[a] = Sym(a, s.vtype, s.array, s.dims, "common")
        # COMMON slots no unit refers to: declared placeholders (an unreferenced numeric
        # COMMON variable has no routine, so only its size matters; string COMMON
        # variables always get a routine and so are never unreferenced)
        h = w.header
        for lo, hi, area in ((h["COMBEG1"] + 1, h["NUMCOMEND"] + 1, "num"),
                             (h["NUMCOMEND"] + 1, h["STRCOMEND"] + 1, "str")):
            pos = lo
            for s in [x for x in _commons(u) if lo <= x.addr < hi] + [None]:
                end = hi if s is None else s.addr
                while pos < end:
                    n = end - pos
                    size, vt = (2, "str") if area == "str" else ((5, "real") if n % 2 or n == 5 else (2, "int"))
                    if pos + size > end:
                        raise DecompileError(f"{u.name}: COMMON gap ${pos:04X}-${end - 1:04X} not fillable")
                    w.syms[pos] = Sym(pos, vt, region="common")
                    pos += size
                if s is not None:
                    pos = max(pos, s.addr + s.size())


def fill_gaps(u: Unit) -> None:
    """Local slots no code refers to (a variable that appears only as a FRE/POS argument,
    which TASC enters into the symbol table but never evaluates): create symbols for them
    (2 bytes numeric = integer, 5 = real, string area = string) and hand them to the
    FRE/POS arguments in order."""
    w = u.lifted.walk
    h = w.header
    used = sorted((s for s in w.syms.values() if s.region == "local"), key=lambda s: s.addr)
    phantoms: list[Sym] = []
    for lo, hi, area in ((h["LOCBEG1"] + 1, h["LOCNUMEND"] + 1, "num"), (h["LOCNUMEND"] + 1, h["LOCSTREND"] + 1, "str")):
        pos = lo
        for s in [x for x in used if lo <= x.addr < hi] + [None]:
            end = hi if s is None else s.addr
            while pos < end:
                if area == "str":
                    size, vt = 2, "str"
                elif (end - pos) % 5 == 0 or (end - pos) % 2:
                    size, vt = 5, "real"
                else:
                    size, vt = 2, "int"
                if pos + size > end:
                    raise DecompileError(f"{u.name}: local gap ${pos:04X}-${end - 1:04X} not fillable")
                ph = Sym(pos, vt, region="local")
                w.syms[pos] = ph
                phantoms.append(ph)
                pos += size
            if s is not None:
                pos = max(pos, s.addr + s.size())
    unk = list(u.lifted.unknowns)
    for ph in phantoms:
        if ph.vtype == "int":
            continue  # REM! INTEGER enters it
        if not unk:
            raise DecompileError(f"{u.name}: unreferenced local ${ph.addr:04X} and no FRE/POS argument for it")
        unk.pop(0).sym = ph


def decompile_many(units: list[Unit]) -> list[Unit]:
    for u in units:
        u.lf = lift(walk(u.data, u.load))
    complete_common(units)
    for u in units:
        fill_gaps(u)
        u.named = _named(u.lifted)
    decompile_names(units)
    _repair_order(units)
    return units


def decompile_names(units: list[Unit]) -> list[Unit]:
    """Choose names (from a provisional compile's insertion order) and render."""
    # provisional names: learn the insertion order of scanned symbols
    seqs: list[dict[Sym, int]] = []
    for u in units:
        pool = N.NamePool(set())
        prov = {}
        for s in sorted(u.named, key=lambda s: s.addr):
            suf = N.suffix(s, s.vtype == "int")
            prov[s] = pool.take(None, 0, suf, s.array) + suf
        u.ints = [s for s in u.named if s.vtype == "int"]
        u.dims = [s for s in u.named if s.array and s.vtype != "int" and s.region == "local"]
        _render(u, prov)
        c = compile_program(u.program, u.opts).compiler
        sq: dict[Sym, int] = {}
        for s, n in prov.items():
            ps = c.syms.get((n.rstrip("%$"), n[-1] if n[-1] in "%$" else "", s.array))
            if ps is None:
                raise DecompileError(f"provisional {n} not in the compiler's symbol table")
            sq[s] = ps.seq
        seqs.append(sq)
    finals = _assign_names(units, seqs)
    for u, nm in zip(units, finals):
        u.names = nm
        _render(u, nm)
    return units


def _nodes(x: object) -> Iterator[object]:
    """Every expression node under a statement argument (FN bodies included)."""
    if isinstance(x, (list, tuple)):
        for y in x:
            yield from _nodes(y)
    elif isinstance(x, FnDef):
        yield from _nodes(x.body)
    elif isinstance(x, ExprNode):
        yield x
        for f in ("l", "r", "e", "arg"):
            if hasattr(x, f):
                yield from _nodes(getattr(x, f))
        for f in ("subs", "args"):
            if hasattr(x, f):
                yield from _nodes(getattr(x, f))


def _pool(data: bytes, load: int) -> list[tuple[str, bytes]]:
    w = walk(data, load)
    return [(s.vtype, s.const) for s in sorted(w.syms.values(), key=lambda s: s.addr) if s.region == "const"]


def _consts_in(n: object) -> set[tuple[str, bytes]]:
    return {(x.sym.vtype, x.sym.const) for x in _nodes(n) if isinstance(x, Leaf) and x.sym.region == "const"}


def _repair_order(units: list[Unit], rounds: int = 12) -> None:
    """Operands of + * AND OR and comparisons can be written in either order with the same
    code, but the order decides when constants are first scanned, i.e. their order in the
    pool.  Flip such nodes until each unit's pool order matches the original."""

    def score(u: Unit) -> int:
        try:
            res = compile_program(u.program, u.opts)
        except Exception:  # noqa: BLE001
            return -1
        a, b = _pool(u.data, u.load), _pool(res.data, res.load)
        if a == b:
            return 1 << 30
        return next((i for i in range(min(len(a), len(b))) if a[i] != b[i]), min(len(a), len(b)))

    for u in units:
        flips = [n for st in u.lifted.stmts for n in _nodes(st.args) if isinstance(n, BinN) and n.flippable]
        if not flips:
            continue
        best = score(u)
        for _ in range(rounds):
            if best == 1 << 30 or best < 0:
                break
            res = compile_program(u.program, u.opts)
            a, b = _pool(u.data, u.load), _pool(res.data, res.load)
            want, have = a[best], b[best] if best < len(b) else None
            cands = [n for n in flips if (want in _consts_in(n.l) and have in _consts_in(n.r))
                     or (want in _consts_in(n.r) and have in _consts_in(n.l))] or \
                    [n for n in flips if want in _consts_in(n.l) | _consts_in(n.r)]
            improved = False
            for n in cands:
                n.flip = not n.flip
                decompile_names(units)
                sc = score(u)
                if sc > best:
                    best, improved = sc, True
                    break
                n.flip = not n.flip
            if not improved:
                decompile_names(units)
                break


def decompile(data: bytes, load: int, opts: Options | None = None) -> Unit:
    return decompile_many([Unit(data, load, opts or Options())])[0]


def compare(d: Unit, data: bytes | None = None, load: int | None = None, opts: Options | None = None) -> str:
    data = d.data if data is None else data
    load = d.load if load is None else load
    opts = d.opts if opts is None else opts
    try:
        res = compile_program(d.program, opts)
    except Exception as exc:  # noqa: BLE001
        return f"recompile failed: {type(exc).__name__}: {exc}"
    if res.data == data and res.load == load:
        return "identical"
    if res.load != load:
        return f"load ${res.load:04X} != ${load:04X}"
    ours = sorted((a, n) for n, a in res.line_addr.items() if n >= 0)
    off = next((i for i in range(min(len(data), len(res.data))) if data[i] != res.data[i]), min(len(data), len(res.data)))
    addr = load + off
    ln = max((n for a, n in ours if a <= addr), default=None)
    return f"differs at ${addr:04X} (+{off}), line {ln}; len {len(res.data)} vs {len(data)}"


def explain(data: bytes, load: int, opts: Options, ctx: int = 4, d: Unit | None = None) -> str:
    """First differing op between the original and the recompiled decompilation."""
    d = d or decompile(data, load, opts)
    res = compile_program(d.program, opts)
    a = walk(data, load).ops
    b = walk(res.data, res.load).ops

    def key(o: object) -> str:
        r = repr(o).split(" ", 1)[1]
        r = re.sub(r"[lcm][0-9A-F]{4}", "v", r)
        return re.sub(r"\$[0-9A-F]{4}|0x[0-9a-f]+", "$", r)

    i = next((k for k in range(min(len(a), len(b))) if key(a[k]) != key(b[k])), min(len(a), len(b)))
    out = [f"first differing op #{i}"]
    for k in range(max(0, i - ctx), min(max(len(a), len(b)), i + ctx)):
        oa = repr(a[k]) if k < len(a) else ""
        ob = repr(b[k]) if k < len(b) else ""
        out.append(f"{'>' if k == i else ' '} {oa:<44} | {ob}")
    return "\n".join(out)


PASS_FILES = ["PASS0", "PASS1", "PASS2"]


def pass_units() -> list[Unit]:
    from pathlib import Path
    root = Path(__file__).resolve().parents[2] / "extracted" / "tasc201"
    return [Unit((root / f"{p}#0641f2").read_bytes(), 0x41F2, Options(), p) for p in PASS_FILES]


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
            res = compare(d)
        except Exception as exc:  # noqa: BLE001
            res = f"error {type(exc).__name__}: {str(exc)[:90]}"
        key = res if res == "identical" else res.split(":")[0].split(" at ")[0][:60]
        stats[key] += 1
        if res != "identical":
            fails.append(f"{dd.parent.name}/{dd.name}: {res}")
    for k, n in stats.most_common():
        print(f"{n:5d}  {k}")
    for f in fails[:200]:
        print("  ", f)


def main() -> None:
    a = sys.argv[1:]
    if a and a[0] == "--corpus":
        _corpus(a[1] if len(a) > 1 else "p")
        return
    if a and a[0] == "--pass":
        for u in decompile_many(pass_units()):
            print(u.name, compare(u), f"{len(u.body_lines)} lines")
        return
    if a and a[0] == "--file":
        u = decompile(open(a[1], "rb").read(), int(a[2], 0))
    else:
        from tasc.batch import load_result
        from tasc.predict_check import options_of
        r = load_result(a[0], a[1])
        print(r.source)
        print("-----")
        u = decompile(r.obj(a[0]), r.obj_addr, options_of(r.options))
    print(u.text)
    print(compare(u))


if __name__ == "__main__":
    main()
