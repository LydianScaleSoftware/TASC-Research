"""Parse a TASC object file into header, code, constants and variable routines.

Layout (observed, Phase 1): [JSR $0803][17-byte header][code][constants][routines].
Variable storage follows the object file in memory.  Code is rendered with
symbolic operands so templates can be compared independent of addresses.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass, field

from tasc import m6502
from tasc.applesoft import Var, variables
from tasc.symbols import DISPATCHERS, INLINE_OPERANDS, all_names

HEADER_FIELDS = ["DATAPTR", "HIGHEST", "COMBEG1", "NUMCOMEND", "STRCOMEND", "LOCBEG1", "LOCNUMEND", "LOCSTREND"]


@dataclass
class Header:
    words: dict[str, int]
    flag: int  # $00 define COMMON, $FF use existing COMMON (checked against $69-$6E)

    def describe(self) -> str:
        w = " ".join(f"{k}=${v:04X}" for k, v in self.words.items())
        return f"{w} FLAG=${self.flag:02X}"


@dataclass
class Routine:
    addr: int
    entries: dict[int, int]  # entry address -> op number (str: 0 load / 1 store)
    target: int  # variable or constant address
    dispatcher: int
    vtype: str  # real / int / str
    name: str = ""
    dims: tuple[int, ...] = ()  # arrays: max index per subscript (inline after the JSR)

    @property
    def end(self) -> int:
        return self.addr + self.length

    length: int = 0


@dataclass
class Constant:
    addr: int
    vtype: str
    raw: bytes
    value: float


@dataclass
class CodeItem:
    addr: int
    raw: bytes
    text: str  # symbolic


@dataclass
class ObjectFile:
    load: int
    data: bytes
    header: Header
    code: list[CodeItem] = field(default_factory=list)
    constants: list[Constant] = field(default_factory=list)
    routines: list[Routine] = field(default_factory=list)
    code_end: int = 0
    notes: list[str] = field(default_factory=list)

    def symbolic(self) -> list[str]:
        return [c.text for c in self.code]

    def listing(self) -> str:
        out = [f"; load ${self.load:04X} len {len(self.data)}", f"; header {self.header.describe()}"]
        for c in self.code:
            hexb = " ".join(f"{b:02X}" for b in c.raw[:8]) + (" ..." if len(c.raw) > 8 else "")
            out.append(f"{c.addr:04X}: {hexb:<24} {c.text}")
        for k in self.constants:
            out.append(f"{k.addr:04X}: {' '.join(f'{b:02X}' for b in k.raw):<24} const {k.vtype} {k.value:g}")
        for r in self.routines:
            ent = ", ".join(f"${a:04X}=op{o}" for a, o in sorted(r.entries.items()))
            out.append(f"{r.addr:04X}: routine {r.name:<10} {r.vtype:<4} -> ${r.target:04X} via ${r.dispatcher:04X} [{ent}]")
        out.extend(f"; NOTE {n}" for n in self.notes)
        return "\n".join(out) + "\n"


def real_value(raw: bytes) -> float:
    exp = raw[0]
    if exp == 0:
        return 0.0
    m: int = struct.unpack(">I", bytes([raw[1] | 0x80]) + raw[2:5])[0]
    v = m / 2.0**32 * 2.0 ** (exp - 128)
    return -v if raw[1] & 0x80 else v


def int_value(raw: bytes) -> int:
    v: int = struct.unpack(">h", raw)[0]
    return v


ARRAY_DISPATCHERS = {0x0B11: "real", 0x0B14: "str", 0x0B17: "int"}


def _parse_routine(d: bytes, load: int, off: int, delta: int = 0) -> Routine | None:
    """Try to parse one routine at file offset off."""
    a = off
    entries: dict[int, int] = {}
    if d[a : a + 4] == b"\x38\xa9\x18\x20" and a + 9 <= len(d):  # array: SEC/CLC, JSR disp, inline data
        disp = (d[a + 4] | d[a + 5] << 8) - delta
        if disp not in ARRAY_DISPATCHERS:
            return None
        tgt = d[a + 6] | d[a + 7] << 8
        nd = d[a + 8]
        if nd == 0 or a + 9 + 2 * nd > len(d):
            return None
        dims = tuple(d[a + 9 + 2 * i] | d[a + 10 + 2 * i] << 8 for i in range(nd))
        return Routine(load + a, {load + a: 0, load + a + 2: 1}, tgt, disp, ARRAY_DISPATCHERS[disp],
                       dims=dims, length=9 + 2 * nd)
    if d[a : a + 3] == b"\x38\xa9\x18":  # string: SEC / (LDA #$18 = CLC)
        if d[a + 3] == 0xA0 and d[a + 5] == 0xA9 and d[a + 7] == 0x4C:
            disp = (d[a + 8] | d[a + 9] << 8) - delta
            if DISPATCHERS.get(disp) != "str":
                return None
            tgt = d[a + 6] | d[a + 4] << 8
            return Routine(load + a, {load + a: 0, load + a + 2: 1}, tgt, disp, "str", length=10)
        return None
    while a + 1 < len(d) and d[a] == 0xA2:  # LDX #op
        entries[load + a] = d[a + 1]
        if a + 2 < len(d) and d[a + 2] in (0xAD, 0x2C):  # skip trick
            a += 3
            continue
        a += 2
        break
    else:
        return None
    if a + 7 > len(d) or d[a] != 0xA0 or d[a + 2] != 0xA9 or d[a + 4] != 0x4C:
        return None
    disp = (d[a + 5] | d[a + 6] << 8) - delta
    if disp not in DISPATCHERS:
        return None
    tgt = d[a + 3] | d[a + 1] << 8
    return Routine(load + off, entries, tgt, disp, DISPATCHERS[disp], length=a + 7 - off)


def _parse_routines_from(d: bytes, load: int, off: int, end: int, delta: int = 0) -> list[Routine] | None:
    out: list[Routine] = []
    while off < end:
        r = _parse_routine(d, load, off, delta)
        if r is None:
            return None
        out.append(r)
        off += r.length
    return out if off == end else None


TYPE_ORDER = {"real": 0, "int": 1, "str": 2}
TYPE_SIZE = {"real": 5, "int": 2, "str": 2}


TYPE_HASH = {"real": 0, "str": 1, "int": 2}


def symbol_hash(v: Var) -> int:
    """Observed symbol-table bucket (p1_order, p1_order2): 32 buckets,
    h = (3*(c1-1) + c2 + T) mod 32 with 5-bit character codes (A=1, '0'=16,
    c2=0 for one-letter names), T = 0 real, 1 string, 2 integer.  Buckets are
    walked in order; within a bucket entries keep insertion (source) order."""
    c1 = ord(v.name[0]) & 0x1F
    c2 = ord(v.name[1]) & 0x1F if len(v.name) > 1 else 0
    return (3 * (c1 - 1) + c2 + TYPE_HASH[v.vtype]) % 32


def symbol_key(v: Var) -> int:
    return symbol_hash(v)  # sorted() is stable, so ties keep source order


def var_size(v: Var) -> int:
    n = 1
    for d in v.dims if v.array else ():
        n *= d + 1
    return n * TYPE_SIZE[v.vtype]


def predict_locals(vars_: list[Var], start: int) -> dict[int, Var]:
    """Hypothesis: numeric scalars, numeric arrays, string scalars, string
    arrays; each group in symbol-table order."""
    out: dict[int, Var] = {}
    a = start
    groups = [
        [v for v in vars_ if not v.array and v.vtype != "str"],
        [v for v in vars_ if v.array and v.vtype != "str"],
        [v for v in vars_ if not v.array and v.vtype == "str"],
        [v for v in vars_ if v.array and v.vtype == "str"],
    ]
    for g in groups:
        for v in sorted(g, key=symbol_key):
            out[a] = v
            a += var_size(v)
    return out


def parse(data: bytes, load: int, source: str | None = None) -> ObjectFile:
    if data[0] != 0x20:
        raise ValueError("object file does not start with JSR <library>")
    lib = data[1] | data[2] << 8
    delta = lib - 0x0803  # RUNTIME is relocated as a whole
    words = {k: data[3 + 2 * i] | data[4 + 2 * i] << 8 for i, k in enumerate(HEADER_FIELDS)}
    obj = ObjectFile(load, data, Header(words, data[19]))
    prog_end = words["LOCBEG1"] - load + 1  # file offset just past the object file
    if prog_end != len(data):  # variables placed elsewhere (memory option)
        prog_end = len(data)

    # routines: earliest offset from which the rest parses as routines
    routines: list[Routine] = []
    rstart = prog_end
    for off in range(20, prog_end):
        rs = _parse_routines_from(data, load, off, prog_end, delta)
        if rs is not None:
            routines, rstart = rs, off
            break
    obj.routines = routines

    # constants: routine targets inside the object file
    const_addrs = sorted({r.target for r in routines if load <= r.target < load + rstart})
    cstart = (const_addrs[0] - load) if const_addrs else rstart
    for ca in const_addrs:
        r = next(x for x in routines if x.target == ca)
        size = 5 if r.vtype == "real" else 2
        raw = data[ca - load : ca - load + size]
        val = real_value(raw) if r.vtype == "real" else float(int_value(raw))
        obj.constants.append(Constant(ca, r.vtype, raw, val))
    if obj.constants:
        last = obj.constants[-1]
        if last.addr - load + len(last.raw) != rstart:
            obj.notes.append("constant pool does not end at the routines")
    obj.code_end = load + cstart

    # name routines
    vars_seen: dict[int, str] = {}
    if source is not None:
        pred = predict_locals(variables(source), words["LOCBEG1"] + 1)
        vars_seen = {a: str(v) for a, v in pred.items()}
        targets = {r.target for r in routines if not (load <= r.target < load + rstart)}
        if not targets <= set(pred):
            obj.notes.append(f"ALLOC MISMATCH: routine targets {sorted(targets - set(pred))} not predicted")
        end_pred = max((a + var_size(v) for a, v in pred.items()), default=words["LOCBEG1"] + 1) - 1
        if pred and end_pred != words["LOCSTREND"]:
            obj.notes.append(f"ALLOC MISMATCH: predicted end ${end_pred:04X} != LOCSTREND ${words['LOCSTREND']:04X}")
    for r in routines:
        if load <= r.target < load + rstart:
            k = next(c for c in obj.constants if c.addr == r.target)
            r.name = f"K({int(k.value) if k.vtype == 'int' else f'{k.value:g}'}{'%' if k.vtype == 'int' else ''})"
        else:
            suffix = {"real": "", "int": "%", "str": "$"}[r.vtype] + ("()" if r.dims else "")
            r.name = vars_seen.setdefault(r.target, f"V{r.target:04X}{suffix}")

    entry_names: dict[int, str] = {}
    for r in routines:
        for a, op in r.entries.items():
            entry_names[a] = f"{r.name}.op{op}"
    names = all_names(delta)
    inline_ops = {a + delta: n for a, n in INLINE_OPERANDS.items()}

    # code: linear decode with inline strings and inline operands
    a = load + 20
    while a < obj.code_end:
        i = m6502.decode(data, load, a)
        off = a - load
        if i.mnemonic == "JMP" and i.operand is not None:
            n = i.operand - (a + 3) - 1
            if 0 <= n < 256 and off + 3 < len(data) and data[off + 3] == n:
                text = data[off + 4 : off + 4 + n].decode("ascii", "replace")
                obj.code.append(CodeItem(a, i.raw, f"JMP +str"))
                obj.code.append(CodeItem(a + 3, data[off + 3 : off + 4 + n], f'STR "{text}"'))
                a = i.operand
                continue
        sym = i.text(names)
        if i.operand is not None and i.operand in entry_names and i.mnemonic in ("JSR", "JMP"):
            sym = f"{i.mnemonic} {entry_names[i.operand]}"
        elif i.mnemonic in ("JSR", "JMP") and i.operand is not None and load <= i.operand < obj.code_end:
            sym = f"{i.mnemonic} @+{i.operand - load}"
        obj.code.append(CodeItem(a, i.raw, sym))
        a += i.length
        if i.mnemonic == "JSR" and i.operand in inline_ops:
            n = inline_ops[i.operand]
            w = data[a - load : a - load + n]
            ref = w[0] | w[1] << 8 if n == 2 else 0
            obj.code.append(CodeItem(a, w, f".WORD @+{ref - load}" if n == 2 else ".BYTES"))
            a += n
    return obj
