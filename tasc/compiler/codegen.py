"""TASC code generation (Phase 1 predictor; seed of the Python compiler).

Rules come from the observed templates (tasc/templates/core.json, RAG
phase1.md).  Lines marked GUESS are unverified extrapolations: a byte mismatch
in a test should be checked against them first.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from fractions import Fraction

from tasc.compiler import fp
from tasc.compiler.parse import (
    Bin, Builtin, Expr, FnCall, Num, ParseError, Stmt, Str, Unary, VarRef, parse_line, read_program,
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
}
RT_RANGE = (0x0803, 0x0803 + 4013)

ROM = {"HOME": 0xFC58, "TEXT": 0xF399, "GR": 0xF390, "HGR": 0xF3E2, "HGR2": 0xF3D8, "NORMAL": 0xF273,
       "INVERSE": 0xF277, "FLASH": 0xF280, "CRDO": 0xDAFB, "AYINT": 0xE10C, "MOVAF": 0xEB63, "FSUBT": 0xE7AA,
       "FDIVT": 0xEA69, "FPWRT": 0xEE97, "NEGOP": 0xEED0, "SGN": 0xEB90, "INT": 0xEC23, "ABS": 0xEBAF,
       "SQR": 0xEE8D, "RND": 0xEFAE, "LOG": 0xE941, "EXP": 0xEF09, "COS": 0xEFEA, "SIN": 0xEFF1, "TAN": 0xF03A,
       "ATN": 0xF09E, "USR": 0x000A}

# one-argument statements: (real entry, int entry or None if unknown)
ARG1 = {"VTAB": (0x149E, 0x14A1), "HTAB": (0x14A7, None), "COLOR=": (0x0E77, 0x0E7A), "HCOLOR=": (0x15F4, None),
        "SPEED=": (0x161E, None), "ROT=": (0x15BB, None), "SCALE=": (0x15C4, None), "CALL": (0x173B, None),
        "IN#": (0x1448, None), "PR#": (0x143F, None), "HIMEM:": (0x08DB, None)}
NO_DEBUG = {"REM", "DATA", "DIM", "END", "GOTO", "GOSUB", "RETURN", "HOME", "TEXT", "GR", "HGR", "HGR2", "NORMAL",
            "INVERSE", "FLASH", "RESUME", "DEF", "POP", "NEW", "ONERR"}  # GUESS beyond HOME/END/GOTO/GOSUB/RETURN/REM/DATA
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
    addr: int = 0  # storage
    rtn: int = 0  # routine address
    label: str = ""

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
        self.temp_depth: dict[str, int] = {"real": 0, "int": 0, "str": 0}
        self.params: list[Sym] = []
        self.scope_param: dict[str, Sym] = {}
        self.int_names: set[str] = set()
        self.int_all = False
        self.int_arrays: dict[str, tuple[int, ...]] = {}
        self.common: list[Sym] = []
        self.common_flag = 0x00
        self.dims: dict[tuple[str, str], tuple[int, ...]] = {}
        self.labels = 0
        self.data_blocks: list[str] = []
        self.cur_line = 0
        self.next_line: dict[int, int] = {}
        self.in_if = False
        self.lit_data: dict[int, str] = {}

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
            if array:  # observed for int arrays (BALL): T = 24 = scalar T + 22; GUESS for real/string arrays
                ht = (ht + 22) % 32
            s = Sym(name, vt, "var", array, dims, ht, self.seq, label=name + suffix + ("()" if array else ""))
            self.syms[key] = s
        return s

    def const(self, value: Fraction, vtype: str) -> Sym:
        """Constant symbol.  Observed: an integer-valued literal (int constants on)
        enters the table as int first, then real, whatever form is used first."""
        if vtype == "real" and self.o.int_const and value.denominator == 1 and abs(value) <= 32767:
            self._const_entry(value, "int")
        return self._const_entry(value, vtype)

    def _const_entry(self, value: Fraction, vtype: str) -> Sym:
        if vtype == "int":
            raw = int(value).to_bytes(2, "big", signed=True)
        else:
            raw = fp.pack_fraction(value)
        key = (raw, vtype)
        s = self.consts.get(key)
        if s is None:
            if vtype == "int" and value.denominator == 1:
                self.const_seq += 1
            self.const_seq += 1
            s = Sym("K", vtype, "const", seq=self.const_seq, raw=raw,
                    label=f"K({int(value) if vtype == 'int' else float(value):g}{'%' if vtype == 'int' else ''})")
            self.consts[key] = s
        return s

    def temp(self, vtype: str) -> Sym:
        d = self.temp_depth[vtype]
        pool = self.temps[vtype]
        if d == len(pool):
            self.seq += 1
            pool.append(Sym(f"T{d}", vtype, "temp", seq=self.seq, label=f"T{vtype[0]}{d}"))
        self.temp_depth[vtype] = d + 1
        return pool[d]

    def free_temp(self, vtype: str) -> None:
        self.temp_depth[vtype] -= 1

    # -- emit ----------------------------------------------------------
    def emit(self, op: int, ref: Ref, note: str = "") -> None:
        self.items.append(Item(op, ref, note=note))

    def jsr_rt(self, name: str) -> None:
        self.emit(JSR, Ref("rt", RT[name]), name)

    def jsr_rom(self, name: str) -> None:
        self.emit(JSR, Ref("abs", ROM[name]), name)

    def entry(self, s: Sym, op: int) -> None:
        # store-load peephole: a load right after a store of the same symbol in the same line
        if op == 0 and self.items:
            last = self.items[-1]
            if (last.op == JSR and last.ref is not None and last.ref.kind == "entry" and last.ref.a is s
                    and last.ref.b == 1):
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
        if isinstance(e, VarRef):
            if e.suffix == "$":
                return "str"
            return self.var(e.name, e.suffix, e.subs is not None, len(e.subs or [])).vtype
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

    def simple_or_str(self, e: Expr) -> bool:
        return self.simple(e) or isinstance(e, Str)

    def simple(self, e: Expr) -> bool:
        return isinstance(e, Num) or (isinstance(e, VarRef) and e.subs is None)

    def operand(self, e: Expr, mode: str) -> Sym:
        """Symbol for a simple operand used in `mode` ('int' or 'real')."""
        if isinstance(e, Num):
            v = fp.literal_value(e.text)
            return self.const(v, "int" if mode == "int" else "real")
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
        """Generate e; want = 'real' | 'int' | 'any' | 'str'.  Returns the type in the accumulator."""
        t = self._gen(e, want)
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
            self.entry(self.const(fp.literal_value(e.text), "real"), 0)
            return "real"
        if isinstance(e, Str):
            lab = self.lit_data.pop(id(e), None)
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
                self.gen(e.e, "any")
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
        """Observed: subscripts evaluated right to left; the first one ends in the accumulator."""
        order = list(reversed(subs))
        for i, sub in enumerate(order):
            last = i == len(order) - 1
            t = self.gen(sub, "any_int" if self.etype(sub) == "lit" else "any")
            if last:
                if t == "real":
                    self.jsr_rom("AYINT")
            else:
                if t == "int":
                    raise CompileError("GUESS: int push-subscript entry unknown")
                self.jsr_rt("PUSH.SUB")

    def binop(self, e: Bin, et: str) -> str:
        lt, rt_ = self.etype(e.l), self.etype(e.r)
        self.scan(e.l) if isinstance(e.l, Str) else None
        if isinstance(e.r, Str) and self.simple_or_str(e.l):
            self.scan(e.r)
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
            if not self.simple(e.l):
                raise CompileError("GUESS: ^ with complex left operand")
            self.gen(e.r, "real")
            self.apply(e.l, "real", 6)
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
                self.gen(e.l, mode)
                t = self.temp(mode)
                self.entry(t, 1)
                self.gen(e.r, mode)
                self.entry(t, k)
                self.free_temp(mode)
            return mode
        # - and /: memory operand is the left one (M-FAC, M/FAC)
        if self.simple(e.l):
            self.gen(e.r, mode)
            self.apply(e.l, mode, k)
        elif self.simple(e.r) and mode == "real":
            self.gen(e.l, "real")
            self.jsr_rom("MOVAF")
            self.gen(e.r, "real")
            self.jsr_rom("FSUBT" if e.op == "-" else "FDIVT")  # GUESS for '/'
        else:
            self.gen(e.l, mode)
            t = self.temp(mode)
            self.entry(t, 1)
            self.gen(e.r, mode)
            self.entry(t, k)
            self.free_temp(mode)
        return mode

    def compare(self, e: Bin, mode: str) -> str:
        op = e.op
        if self.simple(e.r):
            self.gen(e.l, mode)
            self.apply(e.r, mode, 5)
        elif self.simple(e.l):  # GUESS: evaluate right, compare with left, swapped relation
            self.gen(e.r, mode)
            self.apply(e.l, mode, 5)
            op = SWAP[op]
        else:  # GUESS
            self.gen(e.l, mode)
            t = self.temp(mode)
            self.entry(t, 1)
            self.gen(e.r, mode)
            self.entry(t, 5)
            self.free_temp(mode)
            op = SWAP[op]
        self.jsr_rt(CMP[op])
        return "real"

    def test_mem(self, e: Expr) -> str:
        """LDA (and ORA) of a simple operand's storage; returns its type."""
        if isinstance(e, Num):
            raise CompileError("GUESS: AND/OR with a constant operand")
        s = self.operand(e, "real")
        return self.test_sym(s)

    def test_sym(self, s: Sym) -> str:
        self.emit(LDA, Ref("store", s, 0), f"LDA {s!r}")
        if s.vtype == "int":
            self.emit(ORA, Ref("store", s, 1), f"ORA {s!r}+1")
        return s.vtype

    def andor(self, e: Bin) -> str:
        if self.simple(e.l):
            t = self.gen(e.r, "any")
            self.test_mem(e.l)
        elif self.simple(e.r):
            t = self.gen(e.l, "any")
            self.test_mem(e.r)
        else:
            lt = self.gen(e.l, "any")
            tmp = self.temp(lt)
            self.entry(tmp, 1)
            t = self.gen(e.r, "any")
            self.test_sym(tmp)
            self.free_temp(lt)
        name = e.op + ("/I" if t == "int" else "")
        self.jsr_rt(name)
        return "real"

    def strop(self, e: Bin) -> str:
        complex_r = not (isinstance(e.r, Str) or (isinstance(e.r, VarRef) and e.r.subs is None))
        if e.op == "+" and complex_r and isinstance(e.r, VarRef):  # observed: B$(1)+B$(2) uses a string temp
            self.gen(e.l, "str")
            t = self.temp("str")
            self.entry(t, 1)
            self.gen(e.r, "str")
            self.entry(t, 0)
            self.free_temp("str")
            self.jsr_rt("CONCAT.T")
            return "str"
        self.gen(e.l, "str")
        if not (e.op == "+" and isinstance(e.l, Bin) and e.l.op == "+"):  # a concat result is already pushed
            self.jsr_rt("PUSHSTR")
        self.gen(e.r, "str")
        if e.op == "+":
            self.jsr_rt("CONCAT")
            return "str"
        names = {"=": "STREQ", "<": "STRLT", "<>": "STRNE"}
        if e.op not in names:
            raise CompileError(f"GUESS: string relation {e.op}")
        self.jsr_rt(names[e.op])
        return "real"

    def builtin(self, e: Builtin) -> str:
        n, a = e.name, e.args
        if n in ("SGN", "INT", "ABS", "SQR", "RND", "LOG", "EXP", "COS", "SIN", "TAN", "ATN", "USR"):
            self.gen(a[0], "real")
            self.jsr_rom(n)
            return "real"
        if n in ("FRE", "POS"):  # observed: argument symbols allocated, no code
            self.touch(a[0])
            self.jsr_rt(n)
            return "real" if n == "FRE" else "int"
        if n == "PEEK":
            t = self.gen(a[0], "any_int" if self.etype(a[0]) == "lit" else "any")
            self.jsr_rt("PEEK/I" if t == "int" else "PEEK")
            return "int"
        if n == "PDL":
            t = self.gen(a[0], "any")
            if t == "int":
                raise CompileError("GUESS: PDL int entry")
            self.jsr_rt("PDL")
            return "int"
        if n == "SCRN":
            self.gen(a[0], "any")
            self.jsr_rt("PUSH.BYTE")
            self.gen(a[1], "any")
            self.jsr_rt("SCRN")
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
            t = self.gen(a[1], "any")
            if t == "int":
                raise CompileError(f"GUESS: {n} int entry")
            self.jsr_rt("LEFT" if n == "LEFT$" else "RIGHT")
            return "str"
        if n == "MID$":
            self.gen(a[0], "str")
            self.gen(a[1], "any")
            if len(a) == 2:
                self.jsr_rt("MID2")
            else:
                self.jsr_rt("PUSH.BYTE")
                self.gen(a[2], "any")
                self.jsr_rt("MID3")
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

    def scan(self, e: Expr) -> None:
        """Observed: a string literal's data is emitted when the (bottom-up) parser
        scans it; its STRLIT call comes at the reduction that consumes it."""
        if isinstance(e, Str) and id(e) not in self.lit_data:
            self.lit_data[id(e)] = self.strlit_data(e.text)

    # -- statements ----------------------------------------------------
    def store(self, v: VarRef, rhs: Expr) -> None:
        if v.subs is not None:
            s = self.var(v.name, v.suffix, True, len(v.subs))
            self.subscripts(v.subs)
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
            real_e, int_e = ARG1[k]
            t = self.arg(st.args[0])  # type: ignore[arg-type]
            if t == "int":
                if int_e is None:
                    raise CompileError(f"GUESS: int entry for {k}")
                self.emit(JSR, Ref("rt", int_e), k)
            else:
                self.emit(JSR, Ref("rt", real_e), k)
        elif k == "PLOT":
            a, b = st.args
            self.jsr_rt("SAVE.X/I" if self.arg(a) == "int" else "SAVE.X")  # type: ignore[arg-type]
            self.jsr_rt("PLOT/I" if self.arg(b) == "int" else "PLOT")  # type: ignore[arg-type]
        elif k == "POKE":
            a, b = st.args
            self.jsr_rt("SAVE.ADDR/I" if self.arg(a) == "int" else "SAVE.ADDR")  # type: ignore[arg-type]
            self.jsr_rt("POKE/I" if self.arg(b) == "int" else "POKE")  # type: ignore[arg-type]
        elif k in ("HLIN", "VLIN"):
            a, b, c = st.args
            for e, nm in ((a, "SAVE.X"), (b, "SAVE.Y"), (c, k)):
                if self.arg(e) == "int":  # type: ignore[arg-type]
                    raise CompileError(f"GUESS: int entry for {k}")
                self.jsr_rt(nm)
        elif k == "WAIT":
            a = st.args
            for e, nm in zip(a, ["SAVE.ADDR", "WAIT2" if len(a) == 2 else "SAVE.ARG3", "WAIT3"]):
                if self.arg(e) == "int":  # type: ignore[arg-type]
                    raise CompileError("GUESS: int entry for WAIT")
                self.jsr_rt(nm)
        elif k == "HPLOT":
            to_next = False
            for p in st.args:
                if p == "TO":
                    to_next = True
                    continue
                x, y = p  # type: ignore[misc]
                for e, nm in ((x, "SAVE.HX"), (y, "HPLOT.TO" if to_next else "HPLOT")):
                    if self.arg(e) == "int":
                        raise CompileError("GUESS: int entry for HPLOT")
                    self.jsr_rt(nm)
                to_next = False
        elif k in ("DRAW", "XDRAW"):
            sh, at = st.args
            if self.arg(sh) == "int":  # type: ignore[arg-type]
                raise CompileError(f"GUESS: int entry for {k}")
            if at is None:
                self.emit(JSR, Ref("rt", 0x0E34 if k == "DRAW" else 0x0E3B), k)
            else:
                self.jsr_rt("SAVE.SHAPE")
                x, y = at  # type: ignore[misc]
                for e, nm in ((x, "SAVE.HX"), (y, "DRAW.AT" if k == "DRAW" else "XDRAW.AT")):
                    if self.arg(e) == "int":
                        raise CompileError(f"GUESS: int entry for {k}")
                    self.jsr_rt(nm)
        elif k == "IF":
            self.if_(st.args[0])  # type: ignore[arg-type]
        elif k == "IFGOTO":
            cond, n = st.args
            self.cond(cond)  # type: ignore[arg-type]
            self.raw(b"\xF0\x03")
            self.emit(JMP, Ref("line", n))
        elif k in ("ONGOTO", "ONGOSUB"):
            e, targets = st.args
            if self.arg(e) == "int":  # type: ignore[arg-type]
                raise CompileError("GUESS: ON with int expression")
            self.jsr_rt(k[:2] + k[2:])
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
                if v.subs is not None:
                    raise CompileError("READ into array element")
                s = self.var(v.name, v.suffix)
                self.jsr_rt("READ.STR" if s.vtype == "str" else "READ.NUM")
                self.entry(s, 7 if s.vtype == "int" else 1)
        elif k == "DATA":
            self.data(st.args[0])  # type: ignore[arg-type]
        elif k == "DEF":
            self.def_(*st.args)  # type: ignore[arg-type]
        else:
            raise CompileError(f"statement {k} not supported yet")

    def cond(self, e: Expr) -> None:
        self.gen(e, "any")

    def if_(self, cond: Expr) -> None:
        self.cond(cond)
        self.raw(b"\xD0\x03")
        self.emit(JMP, Ref("line", self.next_line[self.cur_line]))
        self.in_if = True

    def for_(self, v: VarRef, a: Expr, b: Expr, step: Expr | None) -> None:
        s = self.var(v.name, v.suffix)
        if s.vtype == "int":
            for e in (a, b) + ((step,) if step else ()):
                if self.arg(e) != "int" if e is a else False:
                    raise CompileError("GUESS: real expression in integer FOR")
            self.jsr_rt("IFOR.INIT")
            self.word(Ref("store", s, 0))
            if self.arg(b) != "int":
                raise CompileError("GUESS: real limit in integer FOR")
            self.jsr_rt("IFOR.LIMIT")
            if step is None:
                self.jsr_rt("IFOR.STEP1")
            else:
                if self.arg(step) != "int":
                    raise CompileError("GUESS: real step in integer FOR")
                self.jsr_rt("IFOR.STEP")
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
                if self.arg(e) == "int":
                    raise CompileError(f"GUESS: int {kind}")
                self.jsr_rt(kind)
            else:
                assert isinstance(it, Expr)
                t = self.gen(it, "any")
                self.jsr_rt({"str": "PRINTSTR", "int": "PRINTINT", "real": "PRINTNUM"}[t])
        if not (last in (";", ",") or isinstance(last, tuple)):
            self.jsr_rom("CRDO")

    def input_(self, prompt: Str | None, vs: list[VarRef]) -> None:
        self.jsr_rt("INPUT.BEGIN")
        if prompt is not None:
            self.strlit(prompt.text, "STRLIT.PROMPT")
        for i, v in enumerate(vs):
            if v.subs is not None:
                raise CompileError("INPUT into array element")
            s = self.var(v.name, v.suffix)
            if s.vtype == "str":
                if i or prompt is not None:
                    raise CompileError("GUESS: INPUT string after first/prompt")
                self.jsr_rt("INPUT.STR")
                self.entry(s, 1)
            else:
                self.jsr_rt("INPUT.NUM.NEXT" if i else ("INPUT.NUM.PROMPT" if prompt is not None else "INPUT.NUM"))
                self.entry(s, 7 if s.vtype == "int" else 1)
        self.jsr_rt("INPUT.END")

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
        self.entry(p, 1)
        self.gen(body, "real")
        self.scope_param = saved
        self.raw(b"\x60")
        self.label(after)

    def rem(self, text: bytes) -> None:
        t = text.decode("ascii", "replace").lstrip(" ")
        if not t.startswith("!"):
            return
        body = t[1:].strip()
        up = body.replace(" ", "")
        if up.startswith("INTEGER"):
            rest = up[len("INTEGER"):]
            if rest.startswith("*"):
                self.int_all = True
                return
            for nm, suf, dims in _decl_list(rest):
                if dims:
                    self.int_arrays[nm] = dims
                else:
                    self.int_names.add(nm)
        elif up.startswith("DEFCOMMON") or up.startswith("USECOMMON"):
            if up.startswith("USECOMMON"):
                self.common_flag = 0xFF
            for nm, suf, dims in _decl_list(up[9:]):
                if dims:
                    self.dims[(nm, suf)] = dims
                s = self.var(nm, suf, bool(dims), len(dims) or 1)
                s.common = len(self.common)
                self.common.append(s)
        elif up.startswith("CLEARCOMMON"):
            self.jsr_rt("CLEARCOMMON")
        elif up.startswith("CLEARCHAIN"):
            self.jsr_rt("CLEARCHAIN")

    def fn_calls(self, e: Expr) -> Expr:
        return e

    # -- program -------------------------------------------------------
    def compile_lines(self, prog: list[tuple[int, list[Stmt]]]) -> None:
        nums = [n for n, _ in prog]
        for i, n in enumerate(nums):
            self.next_line[n] = nums[i + 1] if i + 1 < len(nums) else -1
        for n, stmts in prog:
            self.cur_line = n
            self.in_if = False
            self.items.append(Item(None, line=n))
            i = 0
            while i < len(stmts):
                st = stmts[i]
                if st.kind == "IF" and i + 2 == len(stmts) and stmts[i + 1].kind == "RETURN":
                    # observed (BALL line 370): IF c THEN RETURN -> c, BEQ *+3, RTS
                    if self.o.resume and not self.in_if:
                        self.jsr_rt("DEBUG")
                    self.cond(st.args[0])  # type: ignore[arg-type]
                    self.raw(b"\xF0\x01\x60")
                    break
                self.stmt(st, n)
                i += 1
        self.items.append(Item(None, line=-1))
        self.emit(JMP, Ref("rt", RT["END"]))


def _decl_list(s: str) -> list[tuple[str, str, tuple[int, ...]]]:
    import re
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


def parse_program(data: bytes) -> list[tuple[int, list[Stmt]]]:
    out = []
    for ln in read_program(data):
        try:
            out.append((ln.number, parse_line(ln.body)))
        except ParseError as exc:
            raise CompileError(f"line {ln.number}: {exc}") from exc
    return out
