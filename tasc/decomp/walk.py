"""Decompiler front end, step 1: walk a TASC object file into semantic ops.

The object is parsed with `tasc.objfile` (header, constant pool, variable
routines); the code section is then decoded into `Op`s that name what each
template piece does (routine entry + op number, RUNTIME/ROM call with its
inline operands, string literal data, DATA block, branch pieces).  Every
address is kept so line starts and branch targets can be resolved later.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from tasc import m6502
from tasc.compiler.codegen import ARG1, ROM, RT, int_entry
from tasc.objfile import ObjectFile, Routine, parse

# RUNTIME entries that have an integer-argument variant (codegen.jsr_rt_t users and ARG1)
TYPED = ["PUSH.SUB", "SAVE.X", "PLOT", "SAVE.ADDR", "POKE", "SAVE.Y", "HLIN", "VLIN", "WAIT2", "SAVE.ARG3", "WAIT3",
         "SAVE.HX", "HPLOT.TO", "HPLOT", "SAVE.SHAPE", "DRAW", "XDRAW", "DRAW.AT", "XDRAW.AT", "TAB", "SPC", "ONGOTO",
         "ONGOSUB", "PUSH.BYTE", "PDL", "SCRN", "LEFT", "RIGHT", "MID2", "MID3", "CHR", "PEEK"]
# integer FOR entries: the real-valued variant sits 3 below
IFOR = ["IFOR.INIT", "IFOR.LIMIT", "IFOR.STEP"]
WORD_AFTER = {"STRLIT", "STRLIT.PROMPT", "FOR.INIT", "FOR.INIT/I", "IFOR.INIT", "NEXT", "ONERR"}
ON_LIST = {"ONGOTO", "ONGOSUB"}


def _rt_names() -> dict[int, tuple[str, bool]]:
    """RUNTIME address (library at $0803) -> (name, integer variant)."""
    out: dict[int, tuple[str, bool]] = {}
    for name, a in RT.items():
        if name.endswith("/I") and name[:-2] in RT:
            continue  # explicit /I names are added below as integer variants
        out[a] = (name, False)
    for name in TYPED:
        if name in RT and name + "/I" not in RT:
            out.setdefault(int_entry(RT[name]), (name, True))
    for name in RT:
        if name.endswith("/I") and name[:-2] in RT:
            out[RT[name]] = (name[:-2], True)
    for name, a in ARG1.items():
        out[a] = (name, False)
        out[int_entry(a)] = (name, True)
    for name in IFOR:
        out[RT[name]] = (name, True)
        out[RT[name] - 3] = (name, False)
    return out


RT_NAMES = _rt_names()
ROM_NAMES = {a: n for n, a in ROM.items()}


@dataclass(eq=False)
class Sym:
    """A storage location seen in the object: variable, temp, parameter or constant."""
    addr: int
    vtype: str  # real | int | str
    array: bool = False
    dims: tuple[int, ...] = ()
    region: str = ""  # const | common | local
    const: bytes = b""  # constants: pool bytes
    routine: Routine | None = None
    kind: str = "var"  # var | temp | param | fntemp | const (decided by later passes)
    name: str = ""

    def size(self) -> int:
        n = 1
        for d in self.dims:
            n *= d + 1
        return n * {"real": 5, "int": 2, "str": 2}[self.vtype]

    def __repr__(self) -> str:
        return self.name or f"{self.region[:1]}{self.addr:04X}{ {'real': '', 'int': '%', 'str': '$'}[self.vtype]}" + (
            "()" if self.array else "")


@dataclass
class Op:
    addr: int
    size: int
    kind: str  # see Walk.ops docstring
    name: str = ""  # RUNTIME/ROM name
    is_int: bool = False  # integer variant of a RUNTIME entry
    sym: Sym | None = None
    op: int = -1  # routine op number
    target: int = 0  # jump/call target, or storage address for lda/ora
    words: list[int] = field(default_factory=list)  # inline words after a RUNTIME call
    text: bytes = b""  # string literal text
    items: list[bytes] = field(default_factory=list)  # DATA items
    link: int = 0  # DATA link word

    def __repr__(self) -> str:
        s = f"{self.addr:04X} {self.kind}"
        if self.kind == "ent":
            s += f" {self.sym!r}.op{self.op}"
        elif self.kind in ("rt", "jmprt"):
            s += f" {self.name}{'/I' if self.is_int else ''}" + (f" {[hex(w) for w in self.words]}" if self.words else "")
        elif self.kind == "rom":
            s += f" {self.name}"
        elif self.kind in ("jmp", "jsr"):
            s += f" ${self.target:04X}"
        elif self.kind in ("lda", "ora"):
            s += f" {self.sym!r}+{self.target - self.sym.addr if self.sym else 0}"
        elif self.kind == "lit":
            s += f" {self.text!r}"
        elif self.kind == "data":
            s += f" {self.items!r} link ${self.link:04X}"
        return s


class WalkError(Exception):
    pass


@dataclass
class Walk:
    """ops kinds: ent (routine call), rt / jmprt (RUNTIME JSR / JMP), rom, jsr / jmp (inside the
    object), end (JMP RT.END), lit (JMP over a string literal), data (JMP over a DATA block),
    rts, bne3, beq3, beq1, flag_real (LDA $9D), flag_int (LDA $A0 / ORA $A1), lda / ora (abs)."""
    obj: ObjectFile
    load: int
    delta: int
    ops: list[Op]
    syms: dict[int, Sym]  # storage address -> symbol
    entries: dict[int, tuple[Sym, int]]  # routine entry address -> (symbol, op)

    @property
    def header(self) -> dict[str, int]:
        return self.obj.header.words

    def op_at(self) -> dict[int, int]:
        return {o.addr: i for i, o in enumerate(self.ops)}


def _region(addr: int, h: dict[str, int], load: int, code_end: int, rstart: int) -> str:
    if h["COMBEG1"] < addr <= h["STRCOMEND"]:
        return "common"
    if code_end <= addr < rstart:
        return "const"
    return "local"


def walk(data: bytes, load: int) -> Walk:
    """Walk the code.  A JMP whose next byte happens to equal its distance - 4 looks like a
    string literal; a literal is accepted only if some STRLIT word points at it, else the
    walk is redone with that JMP taken as a plain jump."""
    forced: set[int] = set()
    while True:
        w = _walk(data, load, forced)
        refs = {o.words[0] for o in w.ops if o.kind == "rt" and o.name in ("STRLIT", "STRLIT.PROMPT")}
        bad = {o.addr for o in w.ops if o.kind == "lit" and o.addr + 3 not in refs}
        chain = _data_chain(data, load)
        bad |= {o.addr for o in w.ops if o.kind == "data" and o.addr + 3 not in chain}
        if not bad:
            return w
        forced |= {min(bad)}


def _walk(data: bytes, load: int, forced: set[int]) -> Walk:
    obj = parse(data, load)
    lib = data[1] | data[2] << 8
    delta = lib - 0x0803
    h = obj.header.words
    rstart = obj.routines[0].addr if obj.routines else load + len(data)
    syms: dict[int, Sym] = {}
    entries: dict[int, tuple[Sym, int]] = {}
    for r in obj.routines:
        s = syms.get(r.target)
        if s is None:
            s = Sym(r.target, r.vtype, bool(r.dims), tuple(reversed(r.dims)), _region(r.target, h, load, obj.code_end, rstart),
                    routine=r)
            if s.region == "const":
                s.kind = "const"
                off = r.target - load
                s.const = data[off : off + (5 if r.vtype == "real" else 2)]
            syms[r.target] = s
        for a, op in r.entries.items():
            entries[a] = (s, op)

    def storage(addr: int, vtype: str) -> Sym:
        s = syms.get(addr)
        if s is None:
            s = Sym(addr, vtype, region=_region(addr, h, load, obj.code_end, rstart))
            if s.region == "const":
                s.kind = "const"
                off = addr - load
                s.const = data[off : off + (5 if vtype == "real" else 2)]
            syms[addr] = s
        return s

    ops: list[Op] = []
    a = load + 20
    end = obj.code_end
    rt_end = RT["END"] + delta
    while a < end:
        off = a - load
        i = m6502.decode(data, load, a)
        b = data[off]
        if b in (0x20, 0x4C) and i.operand is not None:
            t = i.operand
            jsr = b == 0x20
            if t in entries:
                s, op = entries[t]
                if not jsr:
                    raise WalkError(f"${a:04X}: JMP to a routine entry")
                ops.append(Op(a, 3, "ent", sym=s, op=op))
                a += 3
                continue
            if not jsr and t == 0x03F5:  # RUN: JMP to the & vector
                ops.append(Op(a, 3, "run"))
                a += 3
                continue
            if not jsr and t == rt_end:
                ops.append(Op(a, 3, "end"))
                a += 3
                continue
            if (t - delta) in RT_NAMES:
                name, is_int = RT_NAMES[t - delta]
                if not jsr:
                    ops.append(Op(a, 3, "jmprt", name=name, is_int=is_int))
                    a += 3
                    continue
                o = Op(a, 3, "rt", name=name, is_int=is_int)
                p = off + 3
                if name in WORD_AFTER:
                    o.words.append(data[p] | data[p + 1] << 8)
                    o.size += 2
                elif name in ON_LIST:
                    n = data[p]
                    o.words = [data[p + 1 + 2 * k] | data[p + 2 + 2 * k] << 8 for k in range(n)]
                    o.size += 1 + 2 * n
                ops.append(o)
                a += o.size
                continue
            if t in ROM_NAMES and jsr:
                ops.append(Op(a, 3, "rom", name=ROM_NAMES[t]))
                a += 3
                continue
            if load <= t < end:
                if not jsr and t > a + 3 and a not in forced:
                    n = data[off + 3]
                    if t == a + 4 + n:
                        ops.append(Op(a, t - a, "lit", text=data[off + 4 : t - load]))
                        a = t
                        continue
                    items = _data_block(data, load, a + 3, t)
                    if items is not None:
                        lk = data[t - load - 2] | data[t - load - 1] << 8
                        ops.append(Op(a, t - a, "data", items=items, link=lk))
                        a = t
                        continue
                ops.append(Op(a, 3, "jsr" if jsr else "jmp", target=t))
                a += 3
                continue
            raise WalkError(f"${a:04X}: {'JSR' if jsr else 'JMP'} ${t:04X} unknown target")
        raw2 = data[off : off + 2]
        if b == 0x60:
            ops.append(Op(a, 1, "rts"))
            a += 1
        elif raw2 == b"\xD0\x03":
            ops.append(Op(a, 2, "bne3"))
            a += 2
        elif raw2 == b"\xF0\x03":
            ops.append(Op(a, 2, "beq3"))
            a += 2
        elif raw2 == b"\xF0\x01":
            ops.append(Op(a, 2, "beq1"))
            a += 2
        elif raw2 == b"\xA5\x9D":
            ops.append(Op(a, 2, "flag_real"))
            a += 2
        elif data[off : off + 4] == b"\xA5\xA0\x05\xA1":
            ops.append(Op(a, 4, "flag_int"))
            a += 4
        elif b in (0xAD, 0x0D) and i.operand is not None:
            t = i.operand
            if a < t < end:
                end = t  # an LDA into the object: the constant pool starts there
                obj.code_end = t
            s = syms.get(t) or syms.get(t - 1)
            if s is None:
                s = storage(t, "real")  # refined later: an ORA on t+1 makes it an int
            ops.append(Op(a, 3, "lda" if b == 0xAD else "ora", sym=s, target=t))
            a += 3
        else:
            raise WalkError(f"${a:04X}: unexpected byte ${b:02X}")
    # ORA marks an integer operand
    for k, o in enumerate(ops):
        if o.kind == "ora" and o.sym is not None and o.target == o.sym.addr + 1:
            o.sym.vtype = "int" if o.sym.vtype == "real" and o.sym.routine is None else o.sym.vtype
            if o.sym.region == "const" and not o.sym.routine:
                o.sym.const = data[o.sym.addr - load : o.sym.addr - load + 2]
    w = Walk(obj, load, delta, ops, syms, entries)
    _storage_syms(w, storage)
    return w


def _storage_syms(w: Walk, storage) -> None:  # type: ignore[no-untyped-def]
    """Symbols referenced only by address (FOR/NEXT words)."""
    for o in w.ops:
        if o.kind == "rt" and o.name in ("FOR.INIT", "NEXT", "IFOR.INIT") and o.words and o.words[0]:
            vt = "int" if o.name == "IFOR.INIT" else "real"
            s = storage(o.words[0], vt)
            if o.name == "NEXT" and s.routine is None and s.vtype == "real":
                pass
            o.sym = s


def _data_chain(d: bytes, load: int) -> set[int]:
    """DATA block addresses: header DATAPTR, then each block's link word."""
    out: set[int] = set()
    p = d[3] | d[4] << 8
    while p and p not in out and load <= p < load + len(d):
        out.add(p)
        q = p - load
        while q < len(d) and d[q] != 0xFF:
            q += 1 + d[q]
        if q + 2 >= len(d):
            break
        p = d[q + 1] | d[q + 2] << 8
    return out


def _data_block(d: bytes, load: int, start: int, target: int) -> list[bytes] | None:
    p = start - load
    end = target - load
    items: list[bytes] = []
    while p < end:
        n = d[p]
        if n == 0xFF:
            return items if p + 3 == end else None
        items.append(d[p + 1 : p + 1 + n])
        p += 1 + n
    return None
