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
from tasc.decomp.lift import BinN, FnDef, Leaf, Lifted, Unknown, lift
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
    fre_choice: dict[int, bool] = field(default_factory=dict)
    prefs: dict[int, tuple[str, int]] = field(default_factory=dict)  # storage address -> (name, group rank)
    fn_prefs: dict[int, str] = field(default_factory=dict)  # DEF FN body address -> name
    param_prefs: dict[int, str] = field(default_factory=dict)  # DEF FN body address -> parameter name
    int_groups: list[int] = field(default_factory=list)  # group rank of each u.ints entry
    numbering: str = "fives"  # "fives" (decompiler default) or "routines" (Phase 5 sources)

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
        # one run of lines per declaration group (Phase 5: related names together)
        # runs of one group; a run shorter than 3 names joins the line before it (names in
        # one hash bucket must keep their storage order, so groups interleave)
        grs = u.int_groups if len(u.int_groups) == len(u.ints) else [0] * len(u.ints)
        runs: list[list[Sym]] = []
        i = 0
        while i < len(u.ints):
            j = i
            while j < len(u.ints) and grs[j] == grs[i]:
                j += 1
            if runs and j - i < 3:
                runs[-1] += u.ints[i:j]
            else:
                runs.append(u.ints[i:j])
            i = j
        for run in runs:
            _chunked(out, REM + b"! INTEGER ", [names[s].encode() + (dimtxt(s) if s.array else b"") for s in run])
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


UNCONDITIONAL = {"GOTO", "RETURN", "END", "STOP", "NEW", "ONERR", "RESUME", "RUN"}


def routine_starts(lf: Lifted) -> set[int]:
    """Addresses that start a routine: GOSUB targets and ON GOTO / ON GOSUB targets (statement
    and operation handlers)."""
    out: set[int] = set()
    for o in lf.walk.ops:
        if o.kind == "jsr" and o.target not in lf.fns:
            out.add(o.target)
        elif o.kind == "rt" and o.name in ("ONGOTO", "ONGOSUB"):
            out.update(o.words)
    return out


def _number_routines(u: Unit, last_decl: int) -> None:
    """Phase 5 numbering (Mark, 2026-10-25): steps of 10; a routine starts at the smallest
    multiple of 100 that is not the very next number (after 90: 200; after 150: 200); a
    routine start that the previous line falls into skips one number instead (after 50: 70).
    The program body starts like a routine."""
    starts = routine_starts(u.lifted)
    num = last_decl
    prev = None
    for ln in u.lines:
        falls = prev is not None and not (prev.stmts[-1].kind in UNCONDITIONAL
                                          and not any(st.kind in ("IF", "IFGOTO", "IFRETURN") for st in prev.stmts))
        if prev is None or (ln.addr in starts and not falls):
            m = (num // 100 + 1) * 100
            if m == num + 10:
                m += 100
            num = m
        elif ln.addr in starts:
            num += 20
        else:
            num += 10
        ln.number = num
        prev = ln
    if num > 63999:
        raise DecompileError(f"{u.name}: line numbers run past 63999")


def _render(u: Unit, names: dict[Sym, str]) -> None:
    lf = u.lifted
    h = lf.walk.header
    decl = _decl_text(u, names)
    step = 10 if u.numbering == "routines" else 5
    first = ((5 * (len(decl) + 1) + 9) // 10) * 10 if decl else 10
    u.lines = layout(lf, 5, first)
    if u.numbering == "routines":
        _number_routines(u, 10 * len(decl))
    line_of = {ln.addr: ln.number for ln in u.lines}
    if decl and _commons(u):
        # manual 8.2.4: lines up to the last COMMON declaration keep program start + 20
        last_common = max(i for i, b in enumerate(decl) if b"COMMON" in b[:12]) + 1
        line_of.setdefault(h["COMBEG1"] + 1 + 20, step * last_common)
    final_end = _final_end(lf)
    if final_end is not None:
        line_of.setdefault(final_end, -1)
    pool = N.NamePool({(n.rstrip("%$"), n[-1] if n[-1] in "%$" else "", s.array) for s, n in names.items()})
    fn_names: dict[int, str] = {}
    params: dict[Sym, str] = {}
    for f in sorted(lf.fns.values(), key=lambda f: f.addr):
        fn_names[f.addr] = u.fn_prefs.get(f.addr) or pool.take(None, 0, "fn", False)
        params[f.param] = u.param_prefs.get(f.addr) or pool.take(None, 0, "", False)
    r = Renderer(names, line_of, fn_names, params)
    pre = [s for s in u.ints if not s.array] or [s for s in _commons(u) if not s.array]
    if pre:
        r.filler = names[pre[0]].encode()
    u.decl_lines = [(step * (i + 1), b) for i, b in enumerate(decl)]
    u.body_lines = []
    u.line_addr = {}
    for ln in u.lines:
        sts = [st for st in ln.stmts if not (st is lf.stmts[-1] and final_end is not None)]
        if sts:
            body = r.stmt(sts[0])
            for prev, st in zip(sts, sts[1:]):
                if st.kind == "EMPTY":
                    body += b":"  # THEN : (an empty statement)
                    continue
                # IF c THEN stmt; but THEN GOTO / THEN RETURN would compile as the short IF
                # forms, so the BNE form with these needs THEN :GOTO / THEN :RETURN
                tight = prev.kind == "IF" and st.kind not in ("GOTO", "RETURN")
                body += (b"" if tight else b":") + r.stmt(st)
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
    name: str = ""


def _weight(x: Node, y: Node, unit: int) -> int:
    """1 when y must be in a later bucket than x (y entered the symbol table earlier)."""
    if x.cls != y.cls:
        return 1 if y.cls < x.cls else 0
    if x.cls in (0, 2):
        return 0  # declared in the order we choose
    if x.cls == 1:
        return 1 if y.rank < x.rank else 0
    return 1 if y.seqs[unit] < x.seqs[unit] else 0


def _candidates(pref: str) -> list[list[str]]:
    """Fallback tiers for a preferred name (Mark, 2026-10-25): the name itself; the same
    first letter with another letter (nearest to the preferred second letter first); the
    same first letter alone or with a digit; then other first letters."""
    p1, p2 = pref[0], pref[1:2]
    near = sorted(N.LETTERS, key=lambda c: (abs(ord(c) - ord(p2)) if p2 else 0, c))
    tiers = [[pref], [p1 + c for c in near if c != p2], [p1] + [p1 + d for d in "0123456789"]]
    # last resort: the nearest other first letters, keeping the preferred second letter first
    firsts = sorted((c for c in N.LETTERS if c != p1), key=lambda c: (abs(ord(c) - ord(p1)), c))
    others = [c1 + c2 for c1 in firsts for c2 in sorted(N.SECOND, key=lambda c: (c != p2, c))]
    tiers.append(others)
    return tiers


def _solve_group(nodes: list[Node], edges: dict[tuple[Node, Node], int], pools: list[N.NamePool],
                 prefs: dict[object, tuple[str, int]]) -> list[Node]:
    """Walk the nodes in a topological order of the edges; each takes a bucket that is not
    below its predecessors' (+1 on weighted edges) and leaves room for the strict chain
    after it, and a name in that bucket: its preferred name when the bucket fits, else the
    first fitting fallback (see _candidates).  Nodes without a preference spread over the
    buckets."""
    succ: dict[Node, list[Node]] = {n: [] for n in nodes}
    pred: dict[Node, list[Node]] = {n: [] for n in nodes}
    for (a, b) in edges:
        succ[a].append(b)
        pred[b].append(a)
    indeg = {n: len(pred[n]) for n in nodes}

    def prio(n: Node) -> tuple[int, int, int]:
        return (n.cls, prefs.get(n.key, ("", 1 << 20))[1], n.rank)

    ready = sorted((n for n in nodes if indeg[n] == 0), key=prio)
    order: list[Node] = []
    while ready:
        n = ready.pop(0)
        order.append(n)
        for m in succ[n]:
            indeg[m] -= 1
            if indeg[m] == 0:
                ready.append(m)
                ready.sort(key=prio)
    if len(order) != len(nodes):
        raise DecompileError("cyclic symbol-order constraints")
    # Buckets by dynamic programming along the order: nondecreasing, +1 before a node with a
    # strict incoming edge, maximising the quality of the names that fit (Mark, 2026-10-25:
    # names that say what the variable is for; else a similar first letter with a second
    # letter or digit).
    pos = {n: i for i, n in enumerate(order)}
    step = [0] * len(order)
    for (x, y), wt in edges.items():
        if wt:
            step[pos[y]] = 1

    def free_for(n: Node, c: str) -> bool:
        return N._ok(c) and all((c, n.suf, n.array) not in pools[ui].used for ui, _ in n.syms)

    wanted: dict[str, set[Node]] = {}
    for x in nodes:
        if x.key in prefs:
            wanted.setdefault(prefs[x.key][0], set()).add(x)

    def options(n: Node) -> list[tuple[int, str]]:
        """(score, name) for every usable name, best first.  A name another variable
        prefers is a poor fallback (it would suggest that variable's meaning)."""
        pref = prefs.get(n.key)
        out: list[tuple[int, str]] = []
        if pref is not None:
            for t, tier in enumerate(_candidates(pref[0])):
                base = (100, 60, 40, 20)[t]
                out += [(base - (k // 3 if t in (1, 2) else k // 37) - (30 if wanted.get(c, {n}) - {n} else 0), c)
                        for k, c in enumerate(tier) if free_for(n, c)]
        else:
            out = [(0, c1 + c2) for c1 in N.LETTERS for c2 in N.SECOND if free_for(n, c1 + c2)]
        return out

    best: list[dict[int, tuple[int, str]]] = []
    for n in order:
        per: dict[int, tuple[int, str]] = {}
        for sc, c in options(n):
            b = N.bucket(c, n.t)
            if b not in per or sc > per[b][0]:
                per[b] = (sc, c)
        best.append(per)
    NEG = -(1 << 30)
    dp = [[NEG] * 32 for _ in order]
    back = [[0] * 32 for _ in order]
    for i in range(len(order)):
        for bk, (sc, _) in best[i].items():
            if i == 0:
                dp[0][bk] = sc
                continue
            lim = bk - step[i]
            if lim < 0:
                continue
            j = max(range(lim + 1), key=lambda x: dp[i - 1][x])
            if dp[i - 1][j] > NEG:
                dp[i][bk] = dp[i - 1][j] + sc
                back[i][bk] = j
    if not order:
        return order
    bk = max(range(32), key=lambda x: dp[-1][x])
    if dp[-1][bk] == NEG:
        raise DecompileError("symbol order needs more than 32 buckets")
    chosen_b = [0] * len(order)
    for i in range(len(order) - 1, -1, -1):
        chosen_b[i] = bk
        bk = back[i][bk]
    for i, n in enumerate(order):
        cands = [c for sc, c in sorted(options(n), key=lambda t: -t[0]) if N.bucket(c, n.t) == chosen_b[i]]
        if not cands:
            raise DecompileError(f"no free name in bucket {chosen_b[i]} for {n.key}")
        n.name = cands[0]
        n.bucket = chosen_b[i]
        for ui, _ in n.syms:
            pools[ui].used.add((n.name, n.suf, n.array))
    return order


def _decl_order(order: list[Node], edges: dict[tuple[Node, Node], int],
                prefs: dict[object, tuple[str, int]]) -> list[Node]:
    """Declaration order for names we declare (REM! INTEGER, DIM): only names in the same
    bucket must keep the order the edges give, so otherwise group related names together
    (by the annotation group, then the solver's order)."""
    pos = {n: i for i, n in enumerate(order)}
    must: dict[Node, list[Node]] = {n: [] for n in order}
    indeg = {n: 0 for n in order}
    for (a, b) in edges:
        if a in pos and b in pos and a.bucket == b.bucket:
            must[a].append(b)
            indeg[b] += 1

    def grp0(n: Node) -> int:
        return prefs.get(n.key, ("", 1 << 20))[1]

    # order the groups so that same-bucket constraints point forward as often as possible:
    # count group -> group constraints, then repeatedly take the group with the fewest
    # constraints from groups not yet placed
    gs = sorted({grp0(n) for n in order})
    cnt: dict[tuple[int, int], int] = {}
    for a, outs in must.items():
        for b in outs:
            if grp0(a) != grp0(b):
                cnt[(grp0(a), grp0(b))] = cnt.get((grp0(a), grp0(b)), 0) + 1
    rank: dict[int, int] = {}
    left = list(gs)
    while left:
        g = min(left, key=lambda g: (sum(cnt.get((h, g), 0) for h in left if h != g), g))
        rank[g] = len(rank)
        left.remove(g)

    def grp(n: Node) -> int:
        return rank[grp0(n)]

    ready = [n for n in order if indeg[n] == 0]
    out: list[Node] = []
    cur = -1
    while ready:
        # stay in the current group while one of its names is free to go, else the
        # lowest group (names in the same bucket must keep their storage order)
        same = [n for n in ready if grp(n) == cur]
        n = min(same or ready, key=lambda n: (grp(n), pos[n]))
        ready.remove(n)
        out.append(n)
        cur = grp(n)
        for m in must[n]:
            indeg[m] -= 1
            if indeg[m] == 0:
                ready.append(m)
    return out


def _assign_names(units: list[Unit], seqs: list[dict[Sym, int]]) -> list[dict[Sym, str]]:
    nodes: dict[object, Node] = {}
    prefs: dict[object, tuple[str, int]] = {}
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
            if s.addr in u.prefs and key not in prefs:
                prefs[key] = u.prefs[s.addr]
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
    for u, pool in zip(units, pools):
        pool.used |= {(nm, "fn", False) for nm in u.fn_prefs.values()}
    for g, gn in groups.items():
        if not gn:
            continue
        ge = {k: v for k, v in edges.items() if k[0] in gn}
        order = _solve_group(gn, ge, pools, prefs)
        decl = _decl_order(order, ge, prefs)
        for n in order:
            for ui, s in n.syms:
                out[ui][s] = n.name + n.suf
        for ui, u in enumerate(units):
            mine = [(s, prefs.get(n.key, ("", 1 << 20))[1]) for n in decl for vi, s in n.syms if vi == ui]
            if g == "num":
                u.ints = [s for s, _ in mine if s.vtype == "int"]
                u.int_groups = [gr for s, gr in mine if s.vtype == "int"]
            if g == "arr":
                u.ints += [s for s, _ in mine if s.vtype == "int"]
                u.int_groups += [gr for s, gr in mine if s.vtype == "int"]
                u.dims = [s for s, _ in mine if s.vtype != "int" and s.region == "local"]
            if g == "str":
                u.dims += [s for s, _ in mine if s.array and s.region == "local"]
    return out


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
    # string symbols get a routine even when unused (PASS2 1105), so an unused one is known
    # by its routine but referenced by no code
    refd = {o.sym for o in w.ops if o.sym is not None}
    phantoms += [s for s in w.syms.values() if s.region == "local" and s.routine is not None and not s.array and s not in refd
                 and s not in phantoms]
    phantoms.sort(key=lambda s: s.addr)
    # real constants nothing references (a FRE/POS literal argument, entered at scan time):
    # PASS2 keeps them in the pool
    phantoms += sorted((s for s in w.syms.values() if s.region == "const" and s.routine is None and s not in refd),
                       key=lambda s: s.addr)
    unk = list(u.lifted.unknowns)
    for lit in u.lifted.free_lits:  # each to the first FRE/POS call after its data
        nxt = next((x for x in unk if x.addr > lit.addr), None)
        if nxt is None:
            raise DecompileError(f"{u.name}: literal at ${lit.addr:04X} with no FRE/POS argument for it")
        nxt.lit = lit.text
        unk.remove(nxt)
    for ph in phantoms:
        if ph.vtype == "int":
            continue  # REM! INTEGER enters it
        if not unk:
            raise DecompileError(f"{u.name}: unreferenced local ${ph.addr:04X} and no FRE/POS argument for it")
        unk.pop(0).sym = ph


def decompile_many(units: list[Unit]) -> list[Unit]:
    for u in units:
        u.lf = lift(walk(u.data, u.load), u.fre_choice)
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
    return {(x.sym.vtype, x.sym.const) for x in _nodes(n)
            if isinstance(x, (Leaf, Unknown)) and x.sym is not None and x.sym.region == "const"}


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
        unks = [x for x in u.lifted.unknowns if x.lit is None]
        if not flips and len(unks) < 2:
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
            # FRE/POS arguments holding unreferenced symbols: which gets which is a guess
            holder = [x for x in unks if x.sym is not None and (x.sym.vtype, x.sym.const) in (want, have)]
            for h in holder if not improved else []:
                for x in unks:
                    if x is h:
                        continue
                    h.sym, x.sym = x.sym, h.sym
                    decompile_names(units)
                    sc = score(u)
                    if sc > best:
                        best, improved = sc, True
                        break
                    h.sym, x.sym = x.sym, h.sym
                if improved:
                    break
            # a filler FRE/POS argument may enter a used constant early (e.g. POS(3) before 3 is
            # used): give `want` to each filler argument in turn
            wsym = next((x for x in u.lifted.walk.syms.values()
                         if x.region == "const" and (x.vtype, x.const) == want), None)
            for x in ([y for y in unks if y.sym is None] if not improved and wsym is not None else []):
                x.sym = wsym
                decompile_names(units)
                sc = score(u)
                if sc > best:
                    best, improved = sc, True
                    break
                x.sym = None
            if not improved:
                decompile_names(units)
                break


def decompile(data: bytes, load: int, opts: Options | None = None) -> Unit:
    """Decompile one object.  A FRE/POS that took a pending string as its argument may be
    wrong in a way that still lifts; if the recompile differs, those choices are flipped."""
    u = decompile_many([Unit(data, load, opts or Options())])[0]
    if compare(u) == "identical":
        return u
    for a in reversed(u.lifted.fre_decisions):
        try:
            v = decompile_many([Unit(data, load, opts or Options(), fre_choice={**u.fre_choice, a: False})])[0]
        except Exception:  # noqa: BLE001
            continue
        if compare(v) == "identical":
            return v
    return u


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
