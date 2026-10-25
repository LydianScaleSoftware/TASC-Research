"""TASC code generation (Phase 1 predictor; seed of the Python compiler).

Rules come from the observed templates (tasc/templates/core.json, RAG
phase1.md).  Lines marked GUESS are unverified extrapolations: a byte mismatch
in a test should be checked against them first.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from fractions import Fraction

from tasc.compiler import fp
from tasc.compiler.fin import fin
from tasc.compiler.parse import (
    TOK, Bin, Builtin, Expr, FnCall, Num, ParseError, Stmt, Str, Unary, VarRef, is_str, iter_statements, read_program,
)
from tasc.harness import Options

# ---------------------------------------------------------------- RUNTIME / ROM addresses (library at $0803)

RT = {
    "END": 0x1363, "STOP": 0x134B, "POP": 0x097B, "RESTORE": 0x0963, "CLEAR": 0x08AA, "CLEARCOMMON": 0x08A7,
    "CLEARCHAIN": 0x0F0B, "FOR.INIT/I": 0x09E5, "FOR.INIT": 0x09E8, "FOR.LIMIT/I": 0x16BC, "FOR.LIMIT": 0x16BF,
    "FOR.STEP/I": 0x16B5, "FOR.STEP": 0x16B8, "FOR.STEP1": 0x16AC, "IFOR.INIT": 0x09E1, "IFOR.LIMIT": 0x1691,
    "IFOR.STEP": 0x168A, "IFOR.STEP1": 0x167E, "NEXT": 0x0A31, "ARR.STORE": 0x0C6F, "PUSH.SUB": 0x165C,
    "FLOAT": 0x166E, "INEG": 0x0CC3, "PRINTNUM": 0x1761, "PRINTINT": 0x175E, "PRINTSTR": 0x0EEE,
    "STRLIT": 0x0EC5, "STRLIT.PROMPT": 0x0EC2, "COMMA": 0x148E, "TAB": 0x146F, "SPC": 0x147F,
    "INPUT.BEGIN": 0x1627, "INPUT.NUM": 0x12FD, "INPUT.NUM.PROMPT": 0x1300, "INPUT.NUM.NEXT": 0x1312,
    "INPUT.STR": 0x1287, "INPUT.END": 0x1387, "GET.STR": 0x10CC, "GET.NUM": 0x1399, "READ.NUM": 0x13AC,
    "READ.STR": 0x13A9, "ONGOTO": 0x14B0, "ONGOSUB": 0x14B7, "ONERR": 0x1637, "RESUME": 0x1656, "DEBUG": 0x1423,
    "EQ": 0x1524, "LT": 0x1528, "GT": 0x1519, "LE": 0x1526, "GE": 0x151B, "NE": 0x1517,
    "AND": 0x1511, "OR": 0x150B, "AND/I": 0x1503, "OR/I": 0x14FD,
    "PUSHSTR": 0x1135, "CONCAT": 0x10EF, "CONCAT.T": 0x10DF, "STREQ": 0x1582, "STRLT": 0x1532, "STRNE": 0x15B7,
    "PUSH.BYTE": 0x15DF, "FRE": 0x0F13, "POS": 0x1700, "PEEK": 0x1747, "PEEK/I": 0x1744, "PDL": 0x172B,
    "SCRN": 0x16EB, "LEN": 0x0EB6, "ASC": 0x0EAA, "VAL": 0x0E80, "STR": 0x11A9, "CHR": 0x1192, "CHR/I": 0x1195,
    "LEFT": 0x11C4, "RIGHT": 0x11F2, "MID2": 0x1227, "MID3": 0x1231,
    "SAVE.X": 0x15FD, "SAVE.X/I": 0x1600, "PLOT": 0x170A, "PLOT/I": 0x170D, "SAVE.Y": 0x1608, "HLIN": 0x1716,
    "VLIN": 0x1722, "SAVE.ADDR": 0x1741, "SAVE.ADDR/I": 0x173E, "POKE": 0x1451, "POKE/I": 0x1454,
    "WAIT2": 0x145A, "SAVE.ARG3": 0x15D6, "WAIT3": 0x1466, "SAVE.HX": 0x15E8, "HPLOT": 0x0DF4,
    "HPLOT.TO": 0x0DED, "SAVE.SHAPE": 0x15CD, "DRAW.AT": 0x0DD9, "XDRAW.AT": 0x0DE0,
    "DRAW": 0x0E34, "XDRAW": 0x0E3B, "IMOVE": 0x1675, "ISUBT": 0x0CDA, "STRGT": 0x1549, "STRLE": 0x1546,
    "STRGE": 0x152F, "INPUT.STR.NEXT": 0x1298, "INPUT.STR.PROMPT": 0x128A,
}
# observed: an integer-argument variant sits 3 bytes above the real entry, except these (3 below)
MINUS3 = {0x173B, 0x08DB, 0x1741, 0x1747}  # CALL, HIMEM:, POKE/WAIT address, PEEK


def int_entry(real: int) -> int:
    return real - 3 if real in MINUS3 else real + 3
RT_RANGE = (0x0803, 0x0803 + 4013)

ROM = {"HOME": 0xFC58, "TEXT": 0xF399, "GR": 0xF390, "HGR": 0xF3E2, "HGR2": 0xF3D8, "NORMAL": 0xF273,
       "INVERSE": 0xF277, "FLASH": 0xF280, "CRDO": 0xDAFB, "AYINT": 0xE10C, "MOVAF": 0xEB63, "FSUBT": 0xE7AA,
       "FDIVT": 0xEA69, "FPWRT": 0xEE97, "NEGOP": 0xEED0, "SGN": 0xEB90, "INT": 0xEC23, "ABS": 0xEBAF,
       "SQR": 0xEE8D, "RND": 0xEFAE, "LOG": 0xE941, "EXP": 0xEF09, "COS": 0xEFEA, "SIN": 0xEFF1, "TAN": 0xF03A,
       "ATN": 0xF09E, "USR": 0x000A}

# one-argument statements: (real entry, int entry or None if unknown)
ARG1 = {"VTAB": 0x149E, "HTAB": 0x14A7, "COLOR=": 0x0E77, "HCOLOR=": 0x15F4, "SPEED=": 0x161E, "ROT=": 0x15BB,
        "SCALE=": 0x15C4, "CALL": 0x173B, "IN#": 0x1448, "PR#": 0x143F, "HIMEM:": 0x08DB}
# Confirmed from PASS1's own code (session 4): the statement dispatcher (decompiled PASS1
# lines 350-370, ON token-127 GOTO) reaches the debug emitter (line 5380, call-table entry 85
# = $1423) from every handler except these (RUN, not supported here, also gets the call).
NO_DEBUG = {"REM", "DATA", "DIM", "END", "GOTO", "GOSUB", "RETURN", "HOME", "TEXT", "GR", "HGR", "HGR2", "NORMAL",
            "INVERSE", "FLASH", "RESUME", "DEF", "NEW", "ONERR", "STOP", "RESTORE"}
REAL_OP = {"+": 2, "-": 3, "*": 4, "/": 7}
CMP = {"=": "EQ", "<": "LT", ">": "GT", "<=": "LE", ">=": "GE", "<>": "NE"}
SWAP = {"=": "=", "<>": "<>", "<": ">", ">": "<", "<=": ">=", ">=": "<="}


class CompileError(Exception):
    pass


# ---------------------------------------------------------------- symbols

TYPE_HASH = {"real": 0, "str": 1, "int": 2}
SIZE = {"real": 5, "int": 2, "str": 2}


@dataclass(eq=False)
class Sym:
    name: str
    vtype: str  # real | int | str
    kind: str  # var | temp | param | const
    array: bool = False
    dims: tuple[int, ...] = ()
    hash_t: int = 0
    seq: int = 0
    ops: set[int] = field(default_factory=set)
    common: int | None = None  # declaration index in COMMON
    raw: bytes = b""  # constants: stored bytes
    used: bool = False  # constants tested in memory (AND/OR) need pool storage
    addr: int = 0  # storage
    rtn: int = 0  # routine address
    label: str = ""
    busy: bool = False  # temps: in use

    @property
    def bucket(self) -> int:
        if self.kind == "const":
            return (self.raw[1] if self.vtype == "int" else self.raw[0]) & 31
        c1 = ord(self.name[0]) & 31
        c2 = ord(self.name[1]) & 31 if len(self.name) > 1 else 0
        return (3 * (c1 - 1) + c2 + self.hash_t) % 32

    def size(self) -> int:
        n = 1
        for d in self.dims:
            n *= d + 1
        return n * SIZE[self.vtype]

    def __repr__(self) -> str:
        return self.label or f"{self.kind}:{self.name}"


# ---------------------------------------------------------------- items

@dataclass
class Ref:
    kind: str  # abs | rt | entry | line | label | store | rtn
    a: object = None
    b: int = 0


@dataclass
class Item:
    op: int | None  # opcode for 3-byte abs instruction; None = raw bytes / word / label
    ref: Ref | None = None
    raw: bytes = b""
    word: bool = False
    label: str | None = None
    line: int | None = None  # line-start marker
    note: str = ""

    def size(self) -> int:
        if self.label is not None or self.line is not None:
            return 0
        if self.op is not None:
            return 3
        if self.word:
            return 2
        return len(self.raw)


JSR, JMP, LDA, ORA = 0x20, 0x4C, 0xAD, 0x0D


# ---------------------------------------------------------------- compiler

class Compiler:
    def __init__(self, opts: Options) -> None:
        self.o = opts
        self.items: list[Item] = []
        self.syms: dict[tuple[str, str, bool], Sym] = {}
        self.consts: dict[tuple[bytes, str], Sym] = {}
        self.const_seq = 0
        self.seq = 0
        self.temps: dict[str, list[Sym]] = {"real": [], "int": [], "str": []}
        # every temp created inside a DEF FN body (all functions); see fn_pool
        self.fn_temps: dict[str, list[Sym]] = {"real": [], "int": [], "str": []}
        # observed (PASS1, session 4): each DEF FN body gets temps of its own; they are not
        # reused by the next function's body
        self.fn_pool: dict[str, list[Sym]] = {"real": [], "int": [], "str": []}
        self.in_fn = False
        self.params: list[Sym] = []
        self.scope_param: dict[str, Sym] = {}
        self.int_names: set[str] = set()
        self.int_all = False
        self.int_arrays: dict[str, tuple[int, ...]] = {}
        self.common: list[Sym] = []
        self.common_flag = 0x00
        self.common_last_line: int | None = None
        self.dims: dict[tuple[str, str], tuple[int, ...]] = {}
        self.labels = 0
        self.data_blocks: list[str] = []
        self.cur_line = 0
        self.next_line: dict[int, int] = {}
        self.in_if = False
        self.rem_after_then = False
        self.d2 = 2  # PASS1 D2: 2 = declarations allowed, 1 = after COMMON, 0 = after a statement
        self.common_kind: str | None = None
        self.table: dict[int, int] | None = None
        self.table_str: list[int] = []
        # literal data emitted at scan time, keyed by id() with the node kept alive (a stale
        # entry, e.g. a literal FRE/POS argument that is never generated, must not match a
        # later node that reuses the id)
        self.lit_data: dict[int, tuple[Expr, str]] = {}
        self.depth = 0

    # -- symbols ------------------------------------------------------
    def var(self, name: str, suffix: str, array: bool = False, nsubs: int = 1) -> Sym:
        if not array and suffix != "$" and name in self.scope_param and suffix == "":
            return self.scope_param[name]
        key = (name, suffix, array)
        s = self.syms.get(key)
        if s is None:
            if suffix == "$":
                vt, ht = "str", 1
            elif suffix == "%":
                vt, ht = "int", 2
            else:
                declared = self.int_all or (name in self.int_names if not array else name in self.int_arrays)
                vt, ht = ("int", 0) if declared else ("real", 0)
            self.seq += 1
            dims: tuple[int, ...] = ()
            if array:
                dims = self.dims.get((name, suffix)) or self.int_arrays.get(name) or (10,) * nsubs
            if array:  # observed: array hash term = scalar term + 22 (real 22, string 23, int 24)
                ht = (ht + 22) % 32
            s = Sym(name, vt, "var", array, dims, ht, self.seq, label=name + suffix + ("()" if array else ""))
            self.syms[key] = s
        return s

    def const(self, value: Fraction, vtype: str, text: str | None = None) -> Sym:
        """Constant symbol (created on first need at code generation)."""
        return self._const_entry(value, vtype, text)

    def _const_entry(self, value: Fraction, vtype: str, text: str | None = None) -> Sym:
        if vtype == "int":
            raw = int(value).to_bytes(2, "big", signed=True)
        else:
            raw = fin(text) if text is not None else fp.pack_fraction(value)  # ROM FIN, bit-exact
        key = (raw, vtype)
        s = self.consts.get(key)
        if s is None:
            self.const_seq += 1
            s = Sym("K", vtype, "const", seq=self.const_seq, raw=raw,
                    label=f"K({int(value) if vtype == 'int' else float(value):g}{'%' if vtype == 'int' else ''})")
            self.consts[key] = s
        return s

    def temp(self, vtype: str) -> Sym:
        """Confirmed from PASS1 (lines 5460-5480): temps live in per-type chains of the
        symbol table (int, string, real; one shared chain inside DEF FN bodies); a request
        takes the first free temp of the type in its chain, else appends a new one."""
        pool = self.fn_pool[vtype] if self.in_fn else self.temps[vtype]
        for t in pool:
            if not t.busy:
                t.busy = True
                return t
        self.seq += 1
        t = Sym(f"T{len(pool)}", vtype, "temp", seq=self.seq, label=f"T{vtype[0]}{len(pool)}", busy=True)
        pool.append(t)
        if self.in_fn:
            self.fn_temps[vtype].append(t)
        return t

    def free_temp(self, t: Sym) -> None:
        """PASS1 6540 / 5485: a temp is freed when its value is used."""
        t.busy = False

    # -- emit ----------------------------------------------------------
    def emit(self, op: int, ref: Ref, note: str = "") -> None:
        self.items.append(Item(op, ref, note=note))

    def jsr_rt(self, name: str) -> None:
        self.emit(JSR, Ref("rt", RT[name]), name)

    def jsr_rt_t(self, name: str, t: str) -> None:
        """JSR to RUNTIME entry `name`, or its integer variant when t == 'int'."""
        a = RT[name]
        self.emit(JSR, Ref("rt", int_entry(a) if t == "int" else a), name + ("/I" if t == "int" else ""))

    def jsr_rom(self, name: str) -> None:
        self.emit(JSR, Ref("abs", ROM[name]), name)

    def just_stored(self, s: Sym) -> bool:
        """PASS1 6555: the last thing emitted is a store (op1) of s in this line (TASC: BJ = s
        and the store is the last 3 bytes; BJ is cleared at each line start)."""
        if not self.items:
            return False
        last = self.items[-1]
        return (last.op == JSR and last.ref is not None and last.ref.kind == "entry" and last.ref.a is s
                and last.ref.b == 1)

    def entry(self, s: Sym, op: int) -> None:
        # store-load peephole: a load right after a store of the same symbol in the same line
        if op == 0 and self.just_stored(s):
            return
        s.ops.add(op)
        self.emit(JSR, Ref("entry", s, op), f"{s!r}.op{op}")

    def raw(self, b: bytes) -> None:
        self.items.append(Item(None, raw=b))

    def word(self, ref: Ref) -> None:
        self.items.append(Item(None, ref, word=True))

    def new_label(self) -> str:
        self.labels += 1
        return f"L{self.labels}"

    def label(self, name: str) -> None:
        self.items.append(Item(None, label=name))

    # -- typing --------------------------------------------------------
    def is_intlit(self, e: Expr) -> bool:
        if not isinstance(e, Num):
            return False
        v = fp.literal_value(e.text)
        return v.denominator == 1 and abs(v) <= 32767

    def etype(self, e: Expr) -> str:
        """'int', 'real', 'str' or 'lit' (integer literal, type decided by context)."""
        if isinstance(e, Num):
            return "lit" if self.o.int_const and self.is_intlit(e) else "real"
        if isinstance(e, Str):
            return "str"
        if isinstance(e, VarRef):  # pure lookup: symbols are entered at scan time only
            if e.suffix == "$":
                return "str"
            if e.suffix == "%":
                return "int"
            if e.subs is None and e.name in self.scope_param:
                return "real"
            known = self.syms.get((e.name, e.suffix, e.subs is not None))
            if known is not None:
                return known.vtype
            declared = self.int_all or (e.name in self.int_names if e.subs is None else e.name in self.int_arrays)
            return "int" if declared else "real"
        if isinstance(e, FnCall):
            return "real"
        if isinstance(e, Builtin):
            if e.name in ("PEEK", "PDL", "SCRN", "LEN", "ASC", "POS"):
                return "int"
            if e.name in ("STR$", "CHR$", "LEFT$", "RIGHT$", "MID$"):
                return "str"
            return "real"
        if isinstance(e, Unary):
            if e.op == "+":
                return self.etype(e.e)
            if e.op == "NOT":
                return "real"
            t = self.etype(e.e)
            if t == "lit":
                return "int" if self.o.int_arith else "real"
            return "int" if t == "int" and self.o.int_arith else "real"
        if isinstance(e, Bin):
            lt, rt_ = self.etype(e.l), self.etype(e.r)
            if lt == "str":
                return "str" if e.op == "+" else "real"
            if e.op in ("+", "-", "*"):
                if lt in ("int", "lit") and rt_ in ("int", "lit") and self.o.int_arith:
                    return "int"
                return "real"
            return "real"
        raise CompileError(f"type of {e}")

    def want_any(self, e: Expr) -> str:
        return "any_int" if self.etype(e) == "lit" else "any"

    def simple_or_str(self, e: Expr) -> bool:
        return self.simple(e) or isinstance(e, Str)

    def simple(self, e: Expr) -> bool:
        return isinstance(e, Num) or (isinstance(e, VarRef) and e.subs is None)

    def operand(self, e: Expr, mode: str) -> Sym:
        """Symbol for a simple operand used in `mode` ('int' or 'real')."""
        if isinstance(e, Num):
            v = fp.literal_value(e.text)
            return self.const(v, "int" if mode == "int" else "real", e.text)
        assert isinstance(e, VarRef)
        return self.var(e.name, e.suffix)

    def apply(self, e: Expr, mode: str, k: int) -> None:
        """Apply op k (real numbering, or int numbering in int mode) with simple operand e."""
        s = self.operand(e, mode)
        if mode == "real" and s.vtype == "int":
            self.entry(s, 6 + k)
        else:
            self.entry(s, k)

    # -- expressions ---------------------------------------------------
    def gen(self, e: Expr, want: str) -> str:
        """Generate e; want = 'real' | 'int' | 'any' | 'str'.  Returns the type in the accumulator.

        Observed: TASC parses a whole expression before generating code, so the data of
        all its string literals is emitted first, in source order."""
        own_table = self.depth == 0 and self.table is None
        if self.depth == 0:
            self.prescan(e)
        if own_table:
            self.begin_table([e])
        self.depth += 1
        try:
            t = self._gen(e, want)
        finally:
            self.depth -= 1
            if own_table:
                self.table = None
        if want == "real" and t == "int":
            self.jsr_rt("FLOAT")
            return "real"
        return t

    def _gen(self, e: Expr, want: str) -> str:
        et = self.etype(e)
        if isinstance(e, Num):
            if et == "lit" and want in ("int", "any_int"):
                self.entry(self.const(fp.literal_value(e.text), "int"), 0)
                return "int"
            self.entry(self.const(fp.literal_value(e.text), "real", e.text), 0)
            return "real"
        if isinstance(e, Str):
            ent = self.lit_data.pop(id(e), None)
            lab = ent[1] if ent is not None and ent[0] is e else None
            if lab is None:
                lab = self.strlit_data(e.text)
            self.jsr_rt("STRLIT")
            self.word(Ref("label", lab))
            return "str"
        if isinstance(e, VarRef):
            if e.subs is not None:
                s = self.var(e.name, e.suffix, True, len(e.subs))
                self.subscripts(e.subs)
                self.entry(s, 0)
                return s.vtype
            s = self.var(e.name, e.suffix)
            if s.vtype == "int" and want == "real":
                self.entry(s, 6)
                return "real"
            self.entry(s, 0)
            return s.vtype
        if isinstance(e, Unary):
            if e.op == "+":
                return self._gen(e.e, want)
            if e.op == "NOT":
                self.need_flags(self.gen(e.e, self.want_any(e.e)))  # observed: NOT 10 uses int 10
                self.jsr_rt("EQ")
                return "real"
            if et == "int":
                self.gen(e.e, "int")
                self.jsr_rt("INEG")
                return "int"
            self.gen(e.e, "real")
            self.jsr_rom("NEGOP")
            return "real"
        if isinstance(e, FnCall):
            raise CompileError("FN call outside codegen table")  # handled in fncall()
        if isinstance(e, Builtin):
            return self.builtin(e)
        if isinstance(e, Bin):
            return self.binop(e, et)
        raise CompileError(f"cannot generate {e}")

    def subscripts(self, subs: list[Expr]) -> None:
        """Observed: complex subscripts are computed left to right as scanned (a pending
        result is spilled to a temp when the accumulator is needed again); then the
        subscripts are pushed from last to first, and the first ends in the accumulator."""
        descs: list[tuple[str, object, str]] = []  # (kind, payload, type): leaf / acc / temp

        def spill() -> None:
            for i, (kind, _, ty) in enumerate(descs):
                if kind == "acc":
                    t = self.temp(ty)
                    self.entry(t, 1)
                    descs[i] = ("temp", t, ty)

        for sub in subs:
            if self.simple(sub):
                descs.append(("leaf", sub, ""))
            else:
                spill()
                descs.append(("acc", None, self.gen(sub, self.want_any(sub))))
        for i in range(len(descs) - 1, -1, -1):
            kind, payload, ty = descs[i]
            if kind == "leaf":
                spill()
                assert isinstance(payload, Expr)
                ty = self.gen(payload, self.want_any(payload))
            elif kind == "temp":
                assert isinstance(payload, Sym)
                self.entry(payload, 0)
                self.free_temp(payload)
            descs[i] = ("done", None, ty)
            if i > 0:
                self.jsr_rt_t("PUSH.SUB", ty)
            elif ty == "real":
                self.jsr_rom("AYINT")

    def binop(self, e: Bin, et: str) -> str:
        lt, rt_ = self.etype(e.l), self.etype(e.r)

        if lt == "str":
            return self.strop(e)
        if e.op in ("AND", "OR"):
            return self.andor(e)
        if e.op in CMP:
            mode = "int" if lt in ("int", "lit") and rt_ in ("int", "lit") and (
                lt == "int" or rt_ == "int" or self.o.int_const) else "real"
            if lt == "lit" and rt_ == "lit" and not self.o.int_const:
                mode = "real"
            return self.compare(e, mode)
        mode = "int" if et == "int" else "real"
        if e.op == "^":
            if self.simple(e.l):
                self.gen(e.r, "real")
                self.apply(e.l, "real", 6)
            elif self.simple(e.r):
                self.gen(e.l, "real")
                self.jsr_rom("MOVAF")
                self.gen(e.r, "real")
            else:
                self.both_complex(e, "real", 6)
            self.jsr_rom("FPWRT")
            return "real"
        k = REAL_OP[e.op]
        if e.op in ("+", "*"):
            if self.simple(e.r):
                self.gen(e.l, mode)
                self.apply(e.r, mode, k)
            elif self.simple(e.l):
                self.gen(e.r, mode)
                self.apply(e.l, mode, k)
            else:
                self.both_complex(e, mode, k)
            return mode
        # - and /: memory operand is the left one (M-FAC, M/FAC)
        if self.simple(e.l):
            self.gen(e.r, mode)
            self.apply(e.l, mode, k)
        elif self.simple(e.r) and mode == "real":
            self.gen(e.l, "real")
            self.jsr_rom("MOVAF")
            self.gen(e.r, "real")
            self.jsr_rom("FSUBT" if e.op == "-" else "FDIVT")
        elif self.simple(e.r) and mode == "int":  # observed: IACC -> IARG, load right, IARG-IACC
            self.gen(e.l, "int")
            self.jsr_rt("IMOVE")
            self.gen(e.r, "int")
            self.jsr_rt("ISUBT")
        else:
            self.both_complex(e, mode, k)
        return mode

    def both_complex(self, e: Bin, mode: str, k: int) -> None:
        """Observed: the left result goes to a temp of its own type (an int result is not
        floated first); the op is applied to the temp (6+k for an int temp in real mode)."""
        lt = self._gen_top(e.l, "int" if mode == "int" else "any")
        t = self.temp(lt)
        self.entry(t, 1)
        self.gen(e.r, mode)
        self.entry(t, 6 + k if (mode == "real" and lt == "int") else k)
        self.free_temp(t)

    def _gen_top(self, e: Expr, want: str) -> str:
        return self.gen(e, want)

    def compare(self, e: Bin, mode: str) -> str:
        op = e.op
        if self.simple(e.r):
            self.gen(e.l, mode)
            self.apply(e.r, mode, 5)
        elif self.simple(e.l):  # PASS1 5920-5980 (confirmed p3_lift): right in acc -> left.op5, swapped relation
            self.gen(e.r, mode)
            self.apply(e.l, mode, 5)
            op = SWAP[op]
        else:  # observed: typed temp as for arithmetic; relation swapped
            self.both_complex(e, mode, 5)
            op = SWAP[op]
        self.jsr_rt(CMP[op])
        return "real"

    def test_mem(self, e: Expr) -> str:
        """LDA (and ORA) of a simple operand's storage (a constant: its pool bytes)."""
        if isinstance(e, Num):
            s = self.operand(e, "int" if self.etype(e) == "lit" else "real")
            s.used = True
        else:
            s = self.operand(e, "real")
        return self.test_sym(s)

    def test_sym(self, s: Sym) -> str:
        if self.just_stored(s):
            # PASS1 6555 (confirmed p3_lift peep_and): the peephole also drops an AND/OR memory
            # test of the variable just stored, LDA and ORA alike (TASC quirk: AND/OR then test
            # whatever the store routine left in A)
            return s.vtype
        self.emit(LDA, Ref("store", s, 0), f"LDA {s!r}")
        if s.vtype == "int":
            self.emit(ORA, Ref("store", s, 1), f"ORA {s!r}+1")
        return s.vtype

    def andor(self, e: Bin) -> str:
        if self.simple(e.l):
            t = self.gen(e.r, self.want_any(e.r))
            self.test_mem(e.l)
        elif self.simple(e.r):
            t = self.gen(e.l, self.want_any(e.l))
            self.test_mem(e.r)
        else:
            lt = self.gen(e.l, "any")
            tmp = self.temp(lt)
            self.entry(tmp, 1)
            t = self.gen(e.r, "any")
            self.test_sym(tmp)
            self.free_temp(tmp)
        name = e.op + ("/I" if t == "int" else "")
        self.jsr_rt(name)
        return "real"

    def strop(self, e: Bin) -> str:
        """Observed: a complex string result (array element, function, concatenation) is
        pushed; a simple variable or literal is only loaded.  CONCAT = pushed + loaded,
        CONCAT.T = loaded + pushed."""
        simple_l = self.simple_or_str(e.l)
        simple_r = self.simple_or_str(e.r)
        names = {"=": "STREQ", "<": "STRLT", "<>": "STRNE", ">": "STRGT", "<=": "STRLE", ">=": "STRGE"}
        op = e.op
        if simple_l and simple_r:
            self.gen(e.l, "str")
            self.jsr_rt("PUSHSTR")
            self.gen(e.r, "str")
            rev = False
        elif not simple_l and simple_r:
            self.gen(e.l, "str")
            self.gen(e.r, "str")
            rev = False
        elif simple_l and not simple_r:
            self.gen(e.r, "str")
            self.gen(e.l, "str")
            rev = True
        else:
            self.gen(e.l, "str")
            t = self.temp("str")
            self.entry(t, 1)
            self.gen(e.r, "str")
            self.entry(t, 0)
            self.free_temp(t)
            rev = True
        if op == "+":
            self.jsr_rt("CONCAT.T" if rev else "CONCAT")
            return "str"
        if rev:  # PASS1 6085-6120 (confirmed p3_lift): right in the accumulator -> swapped relation
            op = SWAP[op]
        self.jsr_rt(names[op])
        return "real"

    def reduce_args(self, args: list[Expr], steps: list[tuple[str, object]]) -> list[str]:
        """Observed: complex arguments are computed first (as scanned), simple ones are
        loaded at the reduction; string and numeric accumulators are separate.
        steps: ('load', i) or ('push', name) or ('call', name); 'push'/'call' use the
        integer variant when the value just loaded/computed is an int."""
        desc: list[tuple[str, object, str]] = []
        cls = lambda x: "str" if self.etype(x) == "str" else "num"  # noqa: E731

        def spill(c: str, keep: int | None = None) -> None:
            for j, (kind, _, ty) in enumerate(desc):
                if kind == "acc" and j != keep and (ty == "str") == (c == "str"):
                    t = self.temp(ty)
                    self.entry(t, 1)
                    desc[j] = ("temp", t, ty)

        for i, x in enumerate(args):
            if self.simple_or_str(x):
                desc.append(("leaf", x, ""))
            else:
                # observed: spill whatever accumulator this or any later complex argument uses
                need: set[str] = set()
                for y in args[i:]:
                    if not self.simple_or_str(y):
                        need |= self.uses(y)
                for c2 in need:
                    spill(c2)
                desc.append(("acc", None, self.gen(x, "str" if cls(x) == "str" else self.want_any(x))))
        # observed: at the reduction, a pending result that is not the first value of its
        # class to be consumed is spilled straight away (before any load)
        first_load: dict[str, int] = {}
        for kind, v in steps:
            if kind == "load":
                first_load.setdefault(cls(args[int(v)]), int(v))  # type: ignore[call-overload]
        for j, (k2, _, ty) in enumerate(desc):
            c2 = "str" if ty == "str" else "num"
            if k2 == "acc" and first_load.get(c2) != j:
                t = self.temp(ty)
                self.entry(t, 1)
                desc[j] = ("temp", t, ty)
        types = ["" for _ in args]
        last_t = ""
        for kind, v in steps:
            if kind == "load":
                i = int(v)  # type: ignore[call-overload]
                k2, pay, ty = desc[i]
                if k2 == "leaf":
                    spill(cls(args[i]), keep=None)
                    assert isinstance(pay, Expr)
                    ty = self.gen(pay, "str" if cls(args[i]) == "str" else self.want_any(pay))
                elif k2 == "temp":  # observed: reloading a temp spills the pending result first
                    assert isinstance(pay, Sym)
                    spill(cls(args[i]))
                    self.entry(pay, 0)
                    self.free_temp(pay)
                desc[i] = ("done", None, ty)
                types[i] = ty
                last_t = ty
            else:
                self.jsr_rt_t(str(v), last_t)
        return types

    def uses(self, e: Expr) -> set[str]:
        """Accumulator classes ('num', 'str') used while computing e."""
        if isinstance(e, Str):
            return {"str"}
        if isinstance(e, Num):
            return {"num"}
        if isinstance(e, VarRef):
            out = {"str" if e.suffix == "$" else "num"}
            if e.subs:
                out.add("num")
                for x in e.subs:
                    out |= self.uses(x)
            return out
        if isinstance(e, Unary):
            return self.uses(e.e) | {"num"}
        if isinstance(e, Bin):
            return self.uses(e.l) | self.uses(e.r)
        if isinstance(e, Builtin):
            if e.name in ("FRE", "POS") and self.simple_or_str(e.args[0]):
                return {"num"}  # the operand is not loaded (PASS1 6250)
            out = {"str" if self.etype(e) == "str" else "num"}
            for x in e.args:
                out |= self.uses(x)
            return out
        if isinstance(e, FnCall):
            return self.uses(e.arg) | {"num"}
        return {"num", "str"}

    def builtin(self, e: Builtin) -> str:
        n, a = e.name, e.args
        if n in ("LEFT$", "RIGHT$", "MID$", "SCRN", "PDL", "PEEK", "CHR$", "LEN", "ASC", "VAL"):
            name = {"LEFT$": "LEFT", "RIGHT$": "RIGHT", "CHR$": "CHR"}.get(n, n)
            if n == "MID$":
                steps: list[tuple[str, object]] = [("load", 0), ("load", 1)]
                steps += [("call", "MID2")] if len(a) == 2 else [("call", "PUSH.BYTE"), ("load", 2), ("call", "MID3")]
            elif n == "SCRN":
                steps = [("load", 0), ("call", "PUSH.BYTE"), ("load", 1), ("call", "SCRN")]
            elif n in ("LEFT$", "RIGHT$"):
                steps = [("load", 0), ("load", 1), ("call", name)]
            else:
                steps = [("load", 0), ("call", name)]
            self.reduce_args(a, steps)
            return {"PEEK": "int", "PDL": "int", "SCRN": "int", "LEN": "int", "ASC": "int", "VAL": "real"}.get(n, "str")
        if n in ("SGN", "INT", "ABS", "SQR", "RND", "LOG", "EXP", "COS", "SIN", "TAN", "ATN", "USR"):
            self.gen(a[0], "real")
            self.jsr_rom(n)
            return "real"
        if n in ("FRE", "POS"):
            # PASS1 6250 (confirmed p3_lift): the call is emitted without loading the operand,
            # so a simple argument is only entered in the symbol table; a complex one is still
            # computed (its own triples)
            if self.simple_or_str(a[0]):
                self.touch(a[0])
            elif self.etype(a[0]) == "str":
                self.gen(a[0], "str")
                # PASS1 6330-6375 (p3_rand5 r5030): FRE/POS do not consume a string result; if
                # another string-producing triple follows in the same table, the result is spilled
                # to a string temp, which is never used and so never freed
                me = self.table.get(id(e)) if self.table is not None else None
                if me is not None and any(i > me for i in self.table_str):
                    self.entry(self.temp("str"), 1)
            else:  # a numeric operand is wanted as a real (p3_rand5: JSR POS / FLOAT / JSR FRE)
                self.gen(a[0], "real")
            self.jsr_rt(n)
            return "real" if n == "FRE" else "int"
        if n == "PEEK":
            t = self.gen(a[0], "any_int" if self.etype(a[0]) == "lit" else "any")
            self.jsr_rt("PEEK/I" if t == "int" else "PEEK")
            return "int"
        if n == "PDL":
            self.jsr_rt_t("PDL", self.gen(a[0], self.want_any(a[0])))
            return "int"
        if n == "SCRN":
            self.jsr_rt_t("PUSH.BYTE", self.gen(a[0], self.want_any(a[0])))
            self.jsr_rt_t("SCRN", self.gen(a[1], self.want_any(a[1])))
            return "int"
        if n in ("LEN", "ASC", "VAL"):
            self.gen(a[0], "str")
            self.jsr_rt(n)
            return "real" if n == "VAL" else "int"
        if n == "STR$":
            self.gen(a[0], "real")
            self.jsr_rt("STR")
            return "str"
        if n == "CHR$":
            t = self.gen(a[0], "any_int" if self.etype(a[0]) == "lit" else "any")
            self.jsr_rt("CHR/I" if t == "int" else "CHR")
            return "str"
        if n in ("LEFT$", "RIGHT$"):
            self.gen(a[0], "str")
            self.jsr_rt_t("LEFT" if n == "LEFT$" else "RIGHT", self.gen(a[1], self.want_any(a[1])))
            return "str"
        if n == "MID$":
            self.gen(a[0], "str")
            t = self.gen(a[1], self.want_any(a[1]))
            if len(a) == 2:
                self.jsr_rt_t("MID2", t)
            else:
                self.jsr_rt_t("PUSH.BYTE", t)
                self.jsr_rt_t("MID3", self.gen(a[2], self.want_any(a[2])))
            return "str"
        raise CompileError(f"function {n}")

    def touch(self, e: Expr) -> None:
        """Enter the variables of e into the symbol table without generating code."""
        if isinstance(e, VarRef):
            self.var(e.name, e.suffix, e.subs is not None, len(e.subs or []))
            for x in e.subs or []:
                self.touch(x)
        elif isinstance(e, Unary):
            self.touch(e.e)
        elif isinstance(e, Bin):
            self.touch(e.l)
            self.touch(e.r)
        elif isinstance(e, Builtin):
            for x in e.args:
                self.touch(x)
        elif isinstance(e, FnCall):
            self.touch(e.arg)

    def strlit_data(self, text: bytes) -> str:
        """JMP over [len][text]; returns the label of the length byte."""
        after = self.new_label()
        lenlab = self.new_label()
        self.emit(JMP, Ref("label", after))
        self.label(lenlab)
        self.raw(bytes([len(text)]) + text)
        self.label(after)
        return lenlab

    def strlit(self, text: bytes, entry: str) -> None:
        lab = self.strlit_data(text)
        self.jsr_rt(entry)
        self.word(Ref("label", lab))

    def prescan(self, e: Expr) -> None:
        """Observed: while scanning an expression TASC emits string literal data and
        enters numeric literals into the constant table with their natural type (int
        when integer constants are on and the value is an integer in range)."""
        if isinstance(e, Str):
            self.scan(e)
        elif isinstance(e, Num):
            v = fp.literal_value(e.text)
            self.const(v, "int" if self.etype(e) == "lit" else "real", e.text)
        elif isinstance(e, VarRef):
            # observed: variables are entered into the symbol table as they are scanned
            self.var(e.name, e.suffix, e.subs is not None, len(e.subs or []))
            for x in e.subs or []:
                self.prescan(x)
        elif isinstance(e, Unary):
            self.prescan(e.e)
        elif isinstance(e, Bin):
            self.prescan(e.l)
            self.prescan(e.r)
        elif isinstance(e, Builtin):
            for x in e.args:
                self.prescan(x)
        elif isinstance(e, FnCall):
            self.prescan(e.arg)

    def scan(self, e: Expr) -> None:
        """Observed: a string literal's data is emitted when the (bottom-up) parser
        scans it; its STRLIT call comes at the reduction that consumes it."""
        if isinstance(e, Str) and not (id(e) in self.lit_data and self.lit_data[id(e)][0] is e):
            self.lit_data[id(e)] = (e, self.strlit_data(e.text))

    # -- statements ----------------------------------------------------
    # -- triple tables (PASS1 builds one per expression; an array target and its subscripts
    # form their own) -------------------------------------------------------------------
    def begin_table(self, exprs: list[Expr]) -> None:
        """Remember the order in which the triples of this table are generated (post-order),
        for TASC's look-ahead at a pending string result (PASS1 6330-6375)."""
        order: list[Expr] = []

        def walk(e: Expr) -> None:
            if isinstance(e, Bin):
                walk(e.l)
                walk(e.r)
            elif isinstance(e, Unary):
                walk(e.e)
            elif isinstance(e, Builtin):
                for x in e.args:
                    walk(x)
            elif isinstance(e, FnCall):
                walk(e.arg)
            elif isinstance(e, VarRef) and e.subs is not None:
                for x in e.subs:
                    walk(x)
            else:
                return  # operands, not triples
            order.append(e)

        for e in exprs:
            walk(e)
        self.table = {id(e): i for i, e in enumerate(order)}
        self.table_str = [i for i, e in enumerate(order) if self.str_related(e)]

    def str_related(self, e: Expr) -> bool:
        """String-related triples, those PASS1's look-ahead (6330-6345) stops at: concatenation,
        string array element, string comparison, and LEN STR$ VAL ASC CHR$ LEFT$ RIGHT$ MID$
        (op codes 16, 20, 23-28, >=46)."""
        if isinstance(e, VarRef):
            return e.subs is not None and e.suffix == "$"
        if isinstance(e, Bin):
            return is_str(e.l) and (e.op == "+" or e.op in CMP)
        return isinstance(e, Builtin) and e.name in ("LEN", "STR$", "VAL", "ASC", "CHR$", "LEFT$", "RIGHT$", "MID$")

    def store(self, v: VarRef, rhs: Expr) -> None:
        if v.subs is not None:
            self.prescan(v)  # observed: all target subscripts are scanned before any code
            s = self.var(v.name, v.suffix, True, len(v.subs))
            self.begin_table([v])
            self.subscripts(v.subs)
            self.table = None
            s.ops.add(1)
            self.emit(JSR, Ref("entry", s, 1), f"{s!r}.op1")
            if s.vtype == "str":
                self.gen(rhs, "str")
            elif s.vtype == "int":
                t = self.gen(rhs, "any_int" if self.etype(rhs) == "lit" else "any")
                if t == "real":
                    self.jsr_rom("AYINT")
            else:
                self.gen(rhs, "real")
            self.jsr_rt("ARR.STORE")
            return
        s = self.var(v.name, v.suffix)
        if s.vtype == "str":
            self.gen(rhs, "str")
            self.entry(s, 1)
            return
        if s.vtype == "int":
            t = self.gen(rhs, "any_int" if self.etype(rhs) == "lit" else "any")
            self.entry(s, 1 if t == "int" else 7)
            return
        self.gen(rhs, "real")
        self.entry(s, 1)

    def arg(self, e: Expr) -> str:
        return self.gen(e, "any_int" if self.etype(e) == "lit" else "any")

    def stmt(self, st: Stmt, line_no: int) -> None:
        k = st.kind
        if self.o.resume and k not in NO_DEBUG and not self.in_if:
            self.jsr_rt("DEBUG")
        self.rem_after_then = self.in_if
        self.in_if = False  # observed: only the first statement after THEN skips the debug call
        if k in ("HOME", "TEXT", "GR", "HGR", "HGR2", "NORMAL", "INVERSE", "FLASH"):
            self.jsr_rom(k)
        elif k == "END":
            self.emit(JMP, Ref("rt", RT["END"]))
        elif k == "NEW":
            self.jsr_rt("END")
        elif k in ("STOP", "POP", "RESTORE", "CLEAR"):
            self.jsr_rt(k)
        elif k == "RETURN":
            self.raw(b"\x60")
        elif k == "RUN":
            # PASS1 1290-1310: RUN = JMP $03F5 (the & vector RUNTIME points at the program);
            # RUN n = JSR CLEAR (call-table entry 61) + the GOTO code
            if st.args:
                self.jsr_rt("CLEAR")
                self.emit(JMP, Ref("line", st.args[0]))
            else:
                self.emit(JMP, Ref("abs", 0x03F5))
        elif k == "REM":
            self.rem(st.args[0])  # type: ignore[arg-type]
        elif k == "DIM":
            for v in st.args[0]:  # type: ignore[union-attr]
                assert isinstance(v, VarRef)
                if v.subs is not None:
                    if not all(isinstance(x, Num) for x in v.subs):
                        raise CompileError("DIM needs integer constants")
                    self.dims[(v.name, v.suffix)] = tuple(int(fp.literal_value(x.text)) for x in v.subs)  # type: ignore[union-attr]
                    self.var(v.name, v.suffix, True, len(v.subs))
        elif k == "LET":
            v, rhs = st.args
            assert isinstance(v, VarRef) and isinstance(rhs, Expr)
            self.store(v, rhs)
        elif k == "GOTO":
            self.emit(JMP, Ref("line", st.args[0]))
        elif k == "GOSUB":
            self.emit(JSR, Ref("line", st.args[0]))
        elif k in ARG1:
            t = self.arg(st.args[0])  # type: ignore[arg-type]
            self.emit(JSR, Ref("rt", int_entry(ARG1[k]) if t == "int" else ARG1[k]), k)
        elif k == "PLOT":
            a, b = st.args
            self.jsr_rt_t("SAVE.X", self.arg(a))  # type: ignore[arg-type]
            self.jsr_rt_t("PLOT", self.arg(b))  # type: ignore[arg-type]
        elif k == "POKE":
            a, b = st.args
            self.jsr_rt_t("SAVE.ADDR", self.arg(a))  # type: ignore[arg-type]
            self.jsr_rt_t("POKE", self.arg(b))  # type: ignore[arg-type]
        elif k in ("HLIN", "VLIN"):
            a, b, c = st.args
            for e, nm in ((a, "SAVE.X"), (b, "SAVE.Y"), (c, k)):
                self.jsr_rt_t(nm, self.arg(e))  # type: ignore[arg-type]
        elif k == "WAIT":
            a = st.args
            for e, nm in zip(a, ["SAVE.ADDR", "WAIT2" if len(a) == 2 else "SAVE.ARG3", "WAIT3"]):
                self.jsr_rt_t(nm, self.arg(e))  # type: ignore[arg-type]
        elif k == "HPLOT":
            to_next = False
            for p in st.args:
                if p == "TO":
                    to_next = True
                    continue
                x, y = p  # type: ignore[misc]
                for e, nm in ((x, "SAVE.HX"), (y, "HPLOT.TO" if to_next else "HPLOT")):
                    self.jsr_rt_t(nm, self.arg(e))
                to_next = False
        elif k in ("DRAW", "XDRAW"):
            sh, at = st.args
            t = self.arg(sh)  # type: ignore[arg-type]
            if at is None:
                self.jsr_rt_t(k, t)
            else:
                self.jsr_rt_t("SAVE.SHAPE", t)
                x, y = at  # type: ignore[misc]
                for e, nm in ((x, "SAVE.HX"), (y, "DRAW.AT" if k == "DRAW" else "XDRAW.AT")):
                    self.jsr_rt_t(nm, self.arg(e))
        elif k == "IF":
            self.if_(st.args[0])  # type: ignore[arg-type]
        elif k == "IFGOTO":
            cond, n = st.args
            self.cond(cond)  # type: ignore[arg-type]
            self.raw(b"\xF0\x03")
            self.emit(JMP, Ref("line", n))
        elif k in ("ONGOTO", "ONGOSUB"):
            e, targets = st.args
            self.jsr_rt_t(k, self.arg(e))  # type: ignore[arg-type]
            self.raw(bytes([len(targets)]))  # type: ignore[arg-type]
            for n in targets:  # type: ignore[union-attr]
                self.word(Ref("line", n))
        elif k == "ONERR":
            self.jsr_rt("ONERR")
            self.word(Ref("line", st.args[0]))
        elif k == "RESUME":
            if self.o.resume:
                self.emit(JMP, Ref("rt", RT["RESUME"]))
        elif k == "FOR":
            self.for_(*st.args)  # type: ignore[arg-type]
        elif k == "NEXT":
            vs = st.args[0]
            for v in vs or [None]:  # type: ignore[union-attr]
                self.jsr_rt("NEXT")
                if v is None:
                    self.raw(b"\x00\x00")
                else:
                    assert isinstance(v, VarRef)
                    self.word(Ref("store", self.var(v.name, v.suffix), 0))
        elif k == "PRINT":
            self.print_(st.args)
        elif k == "INPUT":
            self.input_(*st.args)  # type: ignore[arg-type]
        elif k == "GET":
            v = st.args[0]
            assert isinstance(v, VarRef)
            s = self.var(v.name, v.suffix)
            self.jsr_rt("GET.STR" if s.vtype == "str" else "GET.NUM")
            self.entry(s, 7 if s.vtype == "int" else 1)
        elif k == "READ":
            for v in st.args[0]:  # type: ignore[union-attr]
                assert isinstance(v, VarRef)
                self.read_into(v, "READ.STR" if v.suffix == "$" else "READ.NUM")
        elif k == "DATA":
            self.data(st.args[0])  # type: ignore[arg-type]
        elif k == "DEF":
            self.def_(*st.args)  # type: ignore[arg-type]
        else:
            raise CompileError(f"statement {k} not supported yet")

    def cond(self, e: Expr) -> None:
        self.need_flags(self.gen(e, self.want_any(e)))  # observed: IF 287 uses int 287

    FLAG_RT = {"EQ", "LT", "GT", "LE", "GE", "NE", "AND", "OR", "AND/I", "OR/I", "STREQ", "STRLT", "STRNE", "STRGT",
               "STRLE", "STRGE"}

    def need_flags(self, t: str = "real") -> None:
        """Observed: a value just loaded from a variable, or a comparison/logic result,
        has the flags set; any other computed real gets LDA $9D (FAC exponent)."""
        last = self.items[-1] if self.items else None
        if last is not None and last.op == JSR and last.ref is not None:
            if last.ref.kind == "entry":
                sym = last.ref.a
                assert isinstance(sym, Sym)
                if last.ref.b in ((0, 1, 6, 7) if sym.vtype == "int" else (0, 1)):
                    return
            if last.ref.kind == "rt" and last.note in self.FLAG_RT:
                return
        self.raw(b"\xA5\xA0\x05\xA1" if t == "int" else b"\xA5\x9D")  # IACC $A0-$A1 / FAC exponent

    def if_(self, cond: Expr) -> None:
        self.cond(cond)
        self.raw(b"\xD0\x03")
        self.emit(JMP, Ref("line", self.next_line[self.cur_line]))
        self.in_if = True

    def for_(self, v: VarRef, a: Expr, b: Expr, step: Expr | None) -> None:
        s = self.var(v.name, v.suffix)
        if s.vtype == "int":  # observed: real-valued expressions use the entry 3 below
            def ient(name: str, e: Expr) -> None:
                t = self.arg(e)
                self.emit(JSR, Ref("rt", RT[name] - (3 if t != "int" else 0)), name)
            ient("IFOR.INIT", a)
            self.word(Ref("store", s, 0))
            ient("IFOR.LIMIT", b)
            if step is None:
                self.jsr_rt("IFOR.STEP1")
            else:
                ient("IFOR.STEP", step)
            return
        t = self.arg(a)
        self.jsr_rt("FOR.INIT/I" if t == "int" else "FOR.INIT")
        self.word(Ref("store", s, 0))
        self.jsr_rt("FOR.LIMIT/I" if self.arg(b) == "int" else "FOR.LIMIT")
        if step is None:
            self.jsr_rt("FOR.STEP1")
        else:
            self.jsr_rt("FOR.STEP/I" if self.arg(step) == "int" else "FOR.STEP")

    def print_(self, items: list[object]) -> None:
        last: object = None
        for it in items:
            last = it
            if it == ";":
                continue
            if it == ",":
                self.jsr_rt("COMMA")
            elif isinstance(it, tuple):
                kind, e = it
                self.jsr_rt_t(kind, self.arg(e))
            else:
                assert isinstance(it, Expr)
                t = self.gen(it, self.want_any(it))
                self.jsr_rt({"str": "PRINTSTR", "int": "PRINTINT", "real": "PRINTNUM"}[t])
        if not (last in (";", ",") or isinstance(last, tuple)):
            self.jsr_rom("CRDO")

    def input_(self, prompt: Str | None, vs: list[VarRef]) -> None:
        self.jsr_rt("INPUT.BEGIN")
        if prompt is not None:
            self.strlit(prompt.text, "STRLIT.PROMPT")
        for i, v in enumerate(vs):
            st = "STR" if v.suffix == "$" else "NUM"
            entry = f"INPUT.{st}.NEXT" if i else (f"INPUT.{st}.PROMPT" if prompt is not None else f"INPUT.{st}")
            self.read_into(v, entry)
        self.jsr_rt("INPUT.END")

    def read_into(self, v: VarRef, entry: str) -> None:
        """INPUT/READ target: scalar = entry, store; element = address, entry, ARR.STORE."""
        if v.subs is not None:
            s = self.var(v.name, v.suffix, True, len(v.subs))
            self.subscripts(v.subs)
            s.ops.add(1)
            self.emit(JSR, Ref("entry", s, 1), f"{s!r}.op1")
            self.jsr_rt(entry)
            if s.vtype == "int":  # observed (r2027, r2030)
                self.jsr_rom("AYINT")
            self.jsr_rt("ARR.STORE")
            return
        s = self.var(v.name, v.suffix)
        self.jsr_rt(entry)
        self.entry(s, 7 if s.vtype == "int" else 1)

    def data(self, raw: bytes) -> None:
        after = self.new_label()
        first = self.new_label()
        self.emit(JMP, Ref("label", after))
        self.label(first)
        items: list[bytes] = []
        cur = bytearray()
        i = 0
        while i <= len(raw):
            ch = raw[i] if i < len(raw) else None
            if ch is None or ch == ord(","):
                items.append(bytes(cur).strip(b" ") if b'"' not in cur else bytes(cur))
                cur = bytearray()
            elif ch == ord('"'):
                j = raw.index(b'"', i + 1) if b'"' in raw[i + 1 :] else len(raw)
                cur += raw[i + 1 : j]
                cur += b'"'  # marker that the item was quoted (removed below)
                i = j
            else:
                cur.append(ch)
            i += 1
        for it in items:
            it = it.replace(b'"', b"")
            self.raw(bytes([len(it)]) + it)
        self.raw(b"\xFF")
        link = Item(None, Ref("datalink", len(self.data_blocks)), word=True)
        self.items.append(link)
        self.data_blocks.append(first)
        self.label(after)

    def def_(self, name: str, param: tuple[str, str], body: Expr) -> None:
        after = self.new_label()
        self.emit(JMP, Ref("label", after))
        lab = f"FN_{name}"
        self.label(lab)
        self.seq += 1
        p = Sym(param[0], "real", "param", seq=self.seq, label=f"P_{param[0]}")
        self.params.append(p)
        saved = self.scope_param
        self.scope_param = {param[0]: p}
        self.in_fn = True
        self.fn_pool = {"real": [], "int": [], "str": []}
        self.entry(p, 1)
        self.gen(body, "real")
        self.in_fn = False
        self.scope_param = saved
        self.raw(b"\x60")
        self.label(after)

    def rem(self, text: bytes) -> None:
        """REM! declarations.  Errors as in PASS1 (1475-1865): INTEGER only while D2=2 (before
        any statement but REM, and before COMMON), COMMON while D2<>0 and of one kind
        (DECLARATION); a declaration list or CLEAR COMMON/CHAIN must end the line (SYNTAX)."""
        t = text.decode("ascii", "replace").lstrip(" ")
        if not t.startswith("!"):
            return
        body = t[1:].strip()
        up = body.replace(" ", "")
        if up.startswith("INTEGER"):
            if self.d2 != 2:
                raise CompileError(f"line {self.cur_line}: DECLARATION")
            rest = up[len("INTEGER"):]
            if rest.startswith("*"):
                if rest != "*":
                    raise CompileError(f"line {self.cur_line}: SYNTAX")
                self.int_all = True
                return
            for nm, suf, dims in _decl_list(rest, self.cur_line):
                if dims:
                    self.int_arrays[nm] = dims
                else:
                    self.int_names.add(nm)
                self.var(nm, suf, bool(dims), len(dims) or 1)  # observed: entered at the declaration
        elif up.startswith("DEFCOMMON") or up.startswith("USECOMMON"):
            kind = up[:3]
            if self.d2 == 0 or self.common_kind not in (None, kind):
                raise CompileError(f"line {self.cur_line}: DECLARATION")
            self.d2, self.common_kind = 1, kind
            self.common_last_line = self.cur_line
            if up.startswith("USECOMMON"):
                self.common_flag = 0xFF
            for nm, suf, dims in _decl_list(up[9:], self.cur_line):
                if dims:
                    self.dims[(nm, suf)] = dims
                s = self.var(nm, suf, bool(dims), len(dims) or 1)
                s.common = len(self.common)
                self.common.append(s)
        elif up.startswith("CLEARCOMMON") or up.startswith("CLEARCHAIN"):
            if up not in ("CLEARCOMMON", "CLEARCHAIN"):
                raise CompileError(f"line {self.cur_line}: SYNTAX")  # PASS1 1625 -> 1805
            self.d2 = 0  # PASS1 1610
            # PASS1 1585-1615: these go through the debug emitter (line 5380)
            if self.o.resume and not self.rem_after_then:
                self.jsr_rt("DEBUG")
            self.jsr_rt("CLEARCOMMON" if up.startswith("CLEARCOMMON") else "CLEARCHAIN")

    def fn_calls(self, e: Expr) -> Expr:
        return e

    # -- program -------------------------------------------------------
    def compile_lines(self, prog: list[tuple[int, bytes]]) -> None:
        nums = [n for n, _ in prog]
        for i, n in enumerate(nums):
            self.next_line[n] = nums[i + 1] if i + 1 < len(nums) else -1
        for n, body in prog:
            self.cur_line = n
            self.in_if = False
            self.items.append(Item(None, line=n))
            dead = False
            pending_ret: Stmt | None = None
            try:
                for kw, is_data, unsupported, parse, tok in iter_statements(body):
                    if tok != TOK["REM"]:
                        self.d2 = 0  # PASS1 320
                    if unsupported:
                        # PASS1 2485 (confirmed p3_unsup): an unsupported keyword prints a warning
                        # and is skipped unparsed (no code, no symbols) to the next ':' outside
                        # quotes; parsing resumes at 310, which also clears the after-THEN flag
                        parse(True)
                        if pending_ret is not None:
                            self.stmt(pending_ret, n)
                            pending_ret = None
                        self.in_if = False
                        continue
                    if dead and kw and not is_data:
                        # observed: after GOTO / THEN line / RETURN / END / STOP / NEW, statements
                        # that begin with a keyword are skipped unparsed (no code, no symbols);
                        # implicit assignments and DATA are still compiled
                        parse(True)
                        continue
                    st = parse(False)
                    assert st is not None
                    if pending_ret is not None:
                        if st.kind == "RETURN":
                            # observed: IF c THEN RETURN -> c, BEQ *+3, RTS (then dead code)
                            if self.o.resume and not self.in_if:
                                self.jsr_rt("DEBUG")
                            self.in_if = False
                            self.cond(pending_ret.args[0])  # type: ignore[arg-type]
                            self.raw(b"\xF0\x01\x60")
                            pending_ret = None
                            dead = True
                            continue
                        self.stmt(pending_ret, n)
                        pending_ret = None
                    if st.kind == "IF" and st.then_colon:
                        # PASS1 1355 sees ':' (not RETURN): general IF form; the empty statement
                        # ends through 2435 -> 310, clearing the after-THEN flag (confirmed p3_then)
                        self.stmt(st, n)
                        self.in_if = False
                        continue
                    if st.kind == "IF":
                        pending_ret = st  # decide once the next statement is known
                        continue
                    self.stmt(st, n)
                    if st.kind in ("GOTO", "IFGOTO", "RETURN", "END", "STOP", "NEW", "ONERR", "RUN") or (
                            st.kind == "RESUME" and self.o.resume):  # observed: RESUME = JMP $1656 only with the option
                        dead = True
                if pending_ret is not None:
                    self.stmt(pending_ret, n)
            except ParseError as exc:
                raise CompileError(f"line {n}: {exc}") from exc
        self.items.append(Item(None, line=-1))
        self.emit(JMP, Ref("rt", RT["END"]))


def _decl_list(s: str, line: int = 0) -> list[tuple[str, str, tuple[int, ...]]]:
    import re
    if not re.fullmatch(r"[A-Z][A-Z0-9]*[%$]?(\(\d+(,\d+)*\))?(,[A-Z][A-Z0-9]*[%$]?(\(\d+(,\d+)*\))?)*", s):
        raise CompileError(f"line {line}: SYNTAX")
    out = []
    for m in re.finditer(r"([A-Z][A-Z0-9]*)([%$]?)(?:\(([\d,]+)\))?", s):
        dims = tuple(int(x) for x in m.group(3).split(",")) if m.group(3) else ()
        out.append((m.group(1)[:2], m.group(2), dims))
    return out


# patch FnCall generation into Compiler._gen
_orig_gen = Compiler._gen


def _gen_with_fn(self: Compiler, e: Expr, want: str) -> str:
    if isinstance(e, FnCall):
        self.gen(e.arg, "real")
        self.emit(JSR, Ref("label", f"FN_{e.name}"))
        return "real"
    return _orig_gen(self, e, want)


Compiler._gen = _gen_with_fn  # type: ignore[method-assign]


def parse_program(data: bytes) -> list[tuple[int, bytes]]:
    return [(ln.number, ln.body) for ln in read_program(data)]
