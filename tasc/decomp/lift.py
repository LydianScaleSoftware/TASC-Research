"""Decompiler step 2: abstract interpretation of the op stream into statements.

The machine mirrors the code generator (`tasc.compiler.codegen`): one numeric
accumulator (FAC/IACC) with ARG, one string "loaded" register plus the string
stack for complex results, typed temps, the subscript stack, PUSH.BYTE and the
SAVE.* argument registers.  Each RUNTIME/ROM call or routine entry updates the
abstract state; statement-ending calls emit a `Stmt`.

Canonical operand order (chosen so the predictor regenerates the same bytes):
a simple memory operand M with accumulator value A gives `A op M` for + * and
comparisons, `M op A` for - / ^ and AND/OR; a temp always holds the source's
left operand.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from tasc.decomp.walk import Op, Sym, Walk

# ---------------------------------------------------------------- expression nodes


@dataclass(eq=False)
class Node:
    pass


@dataclass(eq=False)
class Leaf(Node):
    sym: Sym
    peep: bool = False  # value left in the accumulator by a store (load elided)


@dataclass(eq=False)
class Lit(Node):
    text: bytes


@dataclass(eq=False)
class Elem(Node):
    sym: Sym
    subs: list[Node]


@dataclass(eq=False)
class BinN(Node):
    op: str
    l: Node
    r: Node
    # flippable: the operands can be written in either order with the same code (a simple
    # operand with a complex one, + * AND OR and comparisons); the order only changes when
    # symbols and constants are first scanned.  flip: render the other order.
    flippable: bool = False
    flip: bool = False


def simple(n: Node) -> bool:
    return isinstance(n, (Leaf, Lit))


@dataclass(eq=False)
class UnN(Node):
    op: str  # '-', 'NOT'
    e: Node


@dataclass(eq=False)
class CallN(Node):
    name: str  # Applesoft function keyword, e.g. 'MID$', 'SCRN('
    args: list[Node]


@dataclass(eq=False)
class FnN(Node):
    fn: int  # body address
    arg: Node


@dataclass(eq=False)
class Unknown(Node):
    """FRE/POS argument: allocated but never evaluated.  The decompiler puts an otherwise
    unreferenced local here (sym), so that it is entered into the symbol table."""
    sym: Sym | None = None


SWAP = {"=": "=", "<>": "<>", "<": ">", ">": "<", "<=": ">=", ">=": "<="}
CMP_RT = {"EQ": "=", "LT": "<", "GT": ">", "LE": "<=", "GE": ">=", "NE": "<>"}
STRCMP_RT = {"STREQ": "=", "STRLT": "<", "STRNE": "<>", "STRGT": ">", "STRLE": "<=", "STRGE": ">="}
ROM_FUNCS = {"SGN", "INT", "ABS", "SQR", "RND", "LOG", "EXP", "COS", "SIN", "TAN", "ATN", "USR"}
ROM_STMTS = {"HOME", "TEXT", "GR", "HGR", "HGR2", "NORMAL", "INVERSE", "FLASH"}
ARG1 = {"VTAB", "HTAB", "COLOR=", "HCOLOR=", "SPEED=", "ROT=", "SCALE=", "CALL", "IN#", "PR#", "HIMEM:"}


# ---------------------------------------------------------------- statements

@dataclass(eq=False)
class Stmt:
    kind: str
    args: list[object] = field(default_factory=list)
    addr: int = 0
    end: int = 0  # address after the statement's code
    join: bool = False  # must share a line with the previous statement (store-load peephole)
    scope_end: int = 0  # IF ... THEN stmts: the next line's address

    def __repr__(self) -> str:
        return f"{self.addr:04X} {self.kind} {self.args!r}{' +join' if self.join else ''}"


class LiftError(Exception):
    pass


@dataclass
class FnDef:
    addr: int  # body address (JSR target)
    param: Sym
    body: Node | None = None


@dataclass
class Lifted:
    walk: Walk
    stmts: list[Stmt]
    fns: dict[int, FnDef]
    temps: set[Sym]
    line_starts: set[int]
    unknowns: list[Unknown] = field(default_factory=list)


def _has_peep(n: object) -> bool:
    if isinstance(n, Leaf):
        return n.peep
    if isinstance(n, BinN):
        return _has_peep(n.l) or _has_peep(n.r)
    if isinstance(n, UnN):
        return _has_peep(n.e)
    if isinstance(n, Elem):
        return any(_has_peep(x) for x in n.subs)
    if isinstance(n, CallN):
        return any(_has_peep(x) for x in n.args)
    if isinstance(n, FnN):
        return _has_peep(n.arg)
    if isinstance(n, (list, tuple)):
        return any(_has_peep(x) for x in n)
    return False


def _unpeep(n: Node) -> Node:
    return Leaf(n.sym) if isinstance(n, Leaf) and n.peep else n


class Machine:
    def __init__(self, w: Walk, temps: set[Sym], fns: dict[int, FnDef]) -> None:
        self.w = w
        self.temps = temps
        self.fns = fns
        self.stmts: list[Stmt] = []
        self.unknowns: list[Unknown] = []
        self.reset()

    def reset(self) -> None:
        self.num: Node | None = None
        self.arg: Node | None = None
        self.sload: Node | None = None
        self.sload_temp = False
        self.sstack: list[Node] = []
        self.slast = ""  # 'load' | 'stack'
        self.tval: dict[Sym, Node] = {}
        self.subs: list[Node] = []
        self.bytes_: list[Node] = []
        self.saves: list[tuple[str, Node]] = []
        self.cmp: tuple[Node, Node, bool] | None = None  # (acc, mem, mem is temp)
        self.test: Node | None = None
        self.test_temp = False
        self.pend_elem: Elem | None = None
        self.io: str = ""  # READ / GET / INPUT value pending in the accumulator
        self.for_: dict[str, object] | None = None
        self.input_: Stmt | None = None
        self.print_: Stmt | None = None
        self.stmt_start: int | None = None
        self.boundary = False  # a DEBUG call or line start since the last statement
        self.last_val = ""  # what the previous op produced: num / stack / load / ''

    # -- helpers --------------------------------------------------------
    def take_num(self, o: Op) -> Node:
        if self.num is None:
            raise LiftError(f"{o!r}: numeric accumulator empty")
        n = self.num
        return n

    def take_str(self, o: Op) -> Node:
        if self.slast == "stack":
            if not self.sstack:
                raise LiftError(f"{o!r}: string stack empty")
            v = self.sstack.pop()
        elif self.slast == "load":
            if self.sload is None:
                raise LiftError(f"{o!r}: string register empty")
            v = self.sload
            self.sload = None
        else:
            raise LiftError(f"{o!r}: no string value")
        self.slast = "stack" if self.sstack else ""
        return v

    def push_str(self, n: Node) -> None:
        self.sstack.append(n)
        self.slast = "stack"

    def load_str(self, n: Node, temp: bool = False) -> None:
        self.sload = n
        self.sload_temp = temp
        self.slast = "load"

    def leaf(self, s: Sym) -> Node:
        if s in self.temps:
            if s not in self.tval:
                raise LiftError(f"temp {s!r} read before written")
            return self.tval[s]
        return Leaf(s)

    def emit(self, kind: str, o: Op, *args: object) -> Stmt:
        self.close_print()
        start = self.start(o)
        prev = self.stmts[-1] if self.stmts else None
        if (prev is not None and not self.boundary and prev.end == start and (
                (kind == prev.kind and kind in ("NEXT", "READ") and prev.args[-1] is not None and args[0] is not None)
                or (kind == "HPLOT.TO" and prev.kind in ("HPLOT", "HPLOT.TO")))):
            # one statement: NEXT A,B / READ A,B / HPLOT .. TO .. (no DEBUG call or line start between)
            prev.args.append(("TO",) + tuple(args) if kind == "HPLOT.TO" else args[0])
            prev.end = o.addr + o.size
            self.stmt_start = None
            return prev
        st = Stmt(kind, list(args), start, o.addr + o.size)
        st.join = _has_peep(args)
        self.stmts.append(st)
        self.stmt_start = None
        self.boundary = False
        return st

    def start(self, o: Op) -> int:
        return self.stmt_start if self.stmt_start is not None else o.addr

    def mark(self, o: Op) -> None:
        if self.stmt_start is None:
            self.stmt_start = o.addr

    def close_print(self) -> None:
        if self.print_ is not None:
            self.print_.args.append(";")
            self.print_ = None

    def print_item(self, o: Op, item: object, crlf: bool = False) -> None:
        if self.print_ is None or self.stmt_start is not None and self.stmt_start != o.addr and False:
            pass
        if self.print_ is None:
            st = Stmt("PRINT", [], self.start(o), 0)
            self.stmts.append(st)
            self.print_ = st
            self.boundary = False
        else:
            # code between items (the next item's expression) belongs to this statement
            pass
        self.stmt_start = None
        if item is not None:
            self.print_.args.append(item)
            if _has_peep(item) and len(self.print_.args) == 1:
                self.print_.join = True
        self.print_.end = o.addr + o.size
        if crlf:
            self.print_ = None

    # -- the interpreter ------------------------------------------------
    def run(self, ops: list[Op], start: int, stop: int) -> None:
        i = start
        while i < stop:
            o = ops[i]
            i = self.step(ops, i, o)

    def step(self, ops: list[Op], i: int, o: Op) -> int:
        before = (id(self.num), len(self.sstack), id(self.sload))
        nxt = self._step(ops, i, o)
        if self.num is not None and id(self.num) != before[0]:
            self.last_val = "num"
        elif len(self.sstack) > before[1]:
            self.last_val = "stack"
        elif self.sload is not None and id(self.sload) != before[2]:
            self.last_val = "load"
        else:
            self.last_val = ""
        return nxt

    def _step(self, ops: list[Op], i: int, o: Op) -> int:
        k = o.kind
        if k == "ent":
            self.mark(o)
            self.entry(o)
        elif k == "rt":
            self.mark(o)
            self.rt(o)
        elif k == "rom":
            self.mark(o)
            self.rom(o)
        elif k == "lit":
            self.mark(o)
        elif k == "data":
            self.emit("DATA", o, o.items)
        elif k == "lda":
            self.mark(o)
            assert o.sym is not None
            self.test = self.leaf(o.sym)
            self.test_temp = o.sym in self.temps
        elif k == "ora":
            pass
        elif k in ("flag_real", "flag_int"):
            self.mark(o)
        elif k == "bne3":
            nxt = ops[i + 1]
            if nxt.kind != "jmp":
                raise LiftError(f"{o!r}: BNE not followed by JMP")
            st = self.emit("IF", o, self.take_num(o))
            st.scope_end = nxt.target
            st.end = nxt.addr + 3
            return i + 2
        elif k == "beq3":
            nxt = ops[i + 1]
            if nxt.kind != "jmp":
                raise LiftError(f"{o!r}: BEQ not followed by JMP")
            st = self.emit("IFGOTO", o, self.take_num(o), nxt.target)
            st.end = nxt.addr + 3
            return i + 2
        elif k == "beq1":
            nxt = ops[i + 1]
            if nxt.kind != "rts":
                raise LiftError(f"{o!r}: BEQ *+3 not followed by RTS")
            st = self.emit("IFRETURN", o, self.take_num(o))
            st.end = nxt.addr + 1
            return i + 2
        elif k == "jmp":
            if o.target in self.fns and False:
                pass
            self.emit("GOTO", o, o.target)
        elif k == "jsr":
            if o.target in self.fns:
                self.mark(o)
                self.num = FnN(o.target, self.take_num(o))
            else:
                self.emit("GOSUB", o, o.target)
        elif k == "rts":
            self.emit("RETURN", o)
        elif k == "end":
            self.emit("END", o)
        elif k == "run":
            self.emit("RUN", o)
        elif k == "jmprt":
            if o.name == "RESUME":
                self.emit("RESUME", o)
            else:
                raise LiftError(f"{o!r}: JMP into RUNTIME")
        else:
            raise LiftError(f"{o!r}: op kind {k}")
        return i + 1

    def entry(self, o: Op) -> None:
        s = o.sym
        assert s is not None
        op = o.op
        if s.array:
            n = len(s.dims)
            first = self.take_num(o)
            rest = [self.subs.pop() for _ in range(n - 1)] if n > 1 else []
            if len(self.subs) < 0:
                raise LiftError("subs")
            e = Elem(s, [first] + rest)
            self.num = None
            if op == 0:
                if s.vtype == "str":
                    self.push_str(e)
                else:
                    self.num = e
            else:
                self.pend_elem = e
            return
        if s.vtype == "str":
            if op == 0:
                if s in self.temps:
                    self.load_str(self.leaf(s), temp=True)
                else:
                    self.load_str(Leaf(s))
            elif self.io in ("READ$", "GET$", "INPUT$"):
                self.io_store(o, Leaf(s))
            else:
                v = self.take_str(o)
                if s in self.temps:
                    self.tval[s] = v
                else:
                    self.emit("LET", o, Leaf(s), v)
                    self.load_str(Leaf(s, peep=True))
            return
        # numeric
        if s.kind == "const" or s.region == "const":
            mem: Node = Leaf(s)
        else:
            mem = self.leaf(s) if op != 1 and not (s.vtype == "int" and op == 7) else Leaf(s)
        is_temp = s in self.temps
        k = op - 6 if (s.vtype == "int" and op >= 6) else op
        if k == 0:
            self.num = mem
        elif k == 1:
            if is_temp:
                self.tval[s] = self.take_num(o)
            elif self.io:
                self.io_store(o, Leaf(s))
            else:
                v = self.take_num(o)
                self.emit("LET", o, Leaf(s), v)
                self.num = Leaf(s, peep=True) if op == 1 else None
        elif k in (2, 4):
            a = self.take_num(o)
            sym = "+" if k == 2 else "*"
            self.num = BinN(sym, mem, a) if is_temp else BinN(sym, a, mem, flippable=not simple(a))
        elif k in (3, 7):
            a = self.take_num(o)
            self.num = BinN("-" if k == 3 else "/", mem, a)
        elif k == 5:
            self.cmp = (self.take_num(o), mem, is_temp)
            self.num = None
        elif k == 6:
            self.arg = mem
        else:
            raise LiftError(f"{o!r}: op {op}")

    def io_store(self, o: Op, target: Node) -> None:
        io = self.io.rstrip("$")
        self.io = ""
        if io == "INPUT":
            assert self.input_ is not None
            self.input_.args[1].append(target)  # type: ignore[union-attr]
            return
        self.emit(io, o, target)
        if o.kind == "ent" and o.op == 1 and isinstance(target, Leaf):
            # store-load peephole after READ/GET: the value stays in the accumulator
            if target.sym.vtype == "str":
                self.load_str(Leaf(target.sym, peep=True))
            else:
                self.num = Leaf(target.sym, peep=True)

    def rt(self, o: Op) -> None:
        n = o.name
        if n == "FLOAT":
            return
        if n == "INEG":
            self.num = UnN("-", self.take_num(o))
        elif n in CMP_RT:
            if self.cmp is not None:
                a, m, t = self.cmp
                self.cmp = None
                r = CMP_RT[n]
                self.num = BinN(SWAP[r], m, a) if t else BinN(r, a, m, flippable=not simple(a))
            elif n == "EQ":
                self.num = UnN("NOT", self.take_num(o))
            else:
                raise LiftError(f"{o!r}: comparison without operands")
        elif n in ("AND", "OR"):
            if self.test is None and isinstance(self.num, Leaf) and self.num.peep:
                # PASS1 6555: the memory test of the variable just stored was dropped too
                self.test, self.test_temp = Leaf(self.num.sym, peep=True), False
            if self.test is None:
                raise LiftError(f"{o!r}: AND/OR without memory operand")
            a = self.take_num(o)
            self.num = BinN(n, self.test, a, flippable=not self.test_temp and not simple(a))
            self.test = None
        elif n == "PUSHSTR":
            self.push_str(self.take_str(o))
        elif n in ("CONCAT", "CONCAT.T"):
            if self.sload is None or not self.sstack:
                raise LiftError(f"{o!r}: concat operands")
            ld, pu = self.sload, self.sstack.pop()
            self.sload = None
            self.push_str(BinN("+", pu, ld) if n == "CONCAT" else BinN("+", ld, pu))
        elif n in STRCMP_RT:
            if self.sload is None or not self.sstack:
                raise LiftError(f"{o!r}: string compare operands")
            ld, pu = self.sload, self.sstack.pop()
            r = STRCMP_RT[n]
            self.num = BinN(SWAP[r], ld, pu) if self.sload_temp else BinN(r, pu, ld, flippable=not simple(pu))
            self.sload = None
            self.slast = "stack" if self.sstack else ""
        elif n == "PUSH.SUB":
            self.subs.append(self.take_num(o))
            self.num = None
        elif n == "PUSH.BYTE":
            self.bytes_.append(self.take_num(o))
            self.num = None
        elif n in ("FRE", "POS"):
            # a complex argument is computed right before the call; a simple one never loaded
            if self.last_val == "num":
                self.num = CallN(n, [self.take_num(o)])
            elif self.last_val in ("stack", "load"):
                self.num = CallN(n, [self.take_str(o)])
            else:
                u = Unknown()
                self.unknowns.append(u)
                self.num = CallN(n, [u])
        elif n in ("PEEK", "PDL"):
            self.num = CallN(n, [self.take_num(o)])
        elif n == "SCRN":
            self.num = CallN("SCRN(", [self.bytes_.pop(), self.take_num(o)])
        elif n in ("LEN", "ASC", "VAL"):
            self.num = CallN(n, [self.take_str(o)])
        elif n in ("STR", "CHR"):
            self.push_str(CallN(n + "$", [self.take_num(o)]))
            self.num = None
        elif n in ("LEFT", "RIGHT", "MID2"):
            x = self.take_num(o)
            s = self.take_str(o)
            self.push_str(CallN({"LEFT": "LEFT$", "RIGHT": "RIGHT$", "MID2": "MID$"}[n], [s, x]))
            self.num = None
        elif n == "MID3":
            x = self.take_num(o)
            b = self.bytes_.pop()
            s = self.take_str(o)
            self.push_str(CallN("MID$", [s, b, x]))
            self.num = None
        elif n == "STRLIT":
            self.load_str(Lit(self.lit_text(o.words[0])))
        elif n == "IMOVE":
            self.arg = self.take_num(o)
        elif n == "ISUBT":
            if self.arg is None:
                raise LiftError(f"{o!r}: ISUBT without IARG")
            self.num = BinN("-", self.arg, self.take_num(o))
            self.arg = None
        # ---- statements
        elif n in ("END",):
            self.emit("NEW", o)
        elif n in ("STOP", "POP", "RESTORE", "CLEAR"):
            self.emit(n, o)
        elif n in ("CLEARCOMMON", "CLEARCHAIN"):
            self.emit(n, o)
        elif n == "DEBUG":
            self.close_print()
            self.boundary = True
        elif n in ARG1:
            self.emit(n, o, self.take_num(o))
        elif n in ("SAVE.X", "SAVE.Y", "SAVE.ADDR", "SAVE.ARG3", "SAVE.HX", "SAVE.SHAPE"):
            self.saves.append((n, self.take_num(o)))
            self.num = None
        elif n == "PLOT":
            self.emit("PLOT", o, self.pop_save("SAVE.X"), self.take_num(o))
        elif n in ("HLIN", "VLIN"):
            y = self.pop_save("SAVE.Y")
            self.emit(n, o, self.pop_save("SAVE.X"), y, self.take_num(o))
        elif n == "POKE":
            self.emit("POKE", o, self.pop_save("SAVE.ADDR"), self.take_num(o))
        elif n == "WAIT2":
            self.emit("WAIT", o, self.pop_save("SAVE.ADDR"), self.take_num(o))
        elif n == "WAIT3":
            b = self.pop_save("SAVE.ARG3")
            self.emit("WAIT", o, self.pop_save("SAVE.ADDR"), b, self.take_num(o))
        elif n in ("HPLOT", "HPLOT.TO"):
            x = self.pop_save("SAVE.HX")
            prev = self.stmts[-1] if self.stmts else None
            if n == "HPLOT.TO" and prev is not None and prev.kind == "HPLOT" and prev.end == self.start(o) and False:
                pass
            self.emit(n, o, x, self.take_num(o))
        elif n in ("DRAW", "XDRAW"):
            self.emit(n, o, self.take_num(o), None)
        elif n in ("DRAW.AT", "XDRAW.AT"):
            x = self.pop_save("SAVE.HX")
            sh = self.pop_save("SAVE.SHAPE")
            self.emit(n[:-3], o, sh, (x, self.take_num(o)))
        elif n in ("FOR.INIT", "IFOR.INIT"):
            self.for_ = {"var": o.sym, "from": self.take_num(o), "addr": self.start(o)}
            self.num = None
        elif n in ("FOR.LIMIT", "IFOR.LIMIT"):
            if self.for_ is None:
                raise LiftError(f"{o!r}: FOR limit without FOR")
            self.for_["to"] = self.take_num(o)
            self.num = None
        elif n in ("FOR.STEP1", "FOR.STEP", "IFOR.STEP", "IFOR.STEP1"):
            f = self.for_
            if f is None:
                raise LiftError(f"{o!r}: FOR step without FOR")
            step = self.take_num(o) if n in ("FOR.STEP", "IFOR.STEP") else None
            self.stmt_start = int(f["addr"])  # type: ignore[call-overload]
            self.emit("FOR", o, Leaf(f["var"]), f["from"], f["to"], step)  # type: ignore[arg-type]
            self.for_ = None
            self.num = None
        elif n == "NEXT":
            self.emit("NEXT", o, Leaf(o.sym) if o.sym is not None else None)
        elif n in ("ONGOTO", "ONGOSUB"):
            self.emit(n, o, self.take_num(o), list(o.words))
        elif n == "ONERR":
            self.emit("ONERR", o, o.words[0])
        elif n in ("PRINTNUM", "PRINTINT"):
            self.print_item(o, self.take_num(o))
            self.num = None
        elif n == "PRINTSTR":
            self.print_item(o, self.take_str(o))
        elif n == "COMMA":
            self.print_item(o, ",")
        elif n in ("TAB", "SPC"):
            self.print_item(o, (n, self.take_num(o)))
            self.num = None
        elif n == "INPUT.BEGIN":
            self.close_print()
            st = Stmt("INPUT", [None, []], self.start(o), 0)
            self.stmts.append(st)
            self.boundary = False
            self.input_ = st
            self.stmt_start = None
        elif n == "STRLIT.PROMPT":
            assert self.input_ is not None
            self.input_.args[0] = self.lit_text(o.words[0])
        elif n.startswith("INPUT.NUM") or n.startswith("INPUT.STR"):
            self.io = "INPUT" + ("$" if "STR" in n else "")
            if self.pend_elem is not None:
                pass
        elif n == "INPUT.END":
            assert self.input_ is not None
            self.input_.end = o.addr + o.size
            self.input_ = None
            self.stmt_start = None
        elif n in ("READ.NUM", "READ.STR", "GET.NUM", "GET.STR"):
            self.io = n.split(".")[0] + ("$" if n.endswith("STR") else "")
        elif n == "ARR.STORE":
            e = self.pend_elem
            if e is None:
                raise LiftError(f"{o!r}: ARR.STORE without element")
            self.pend_elem = None
            if self.io:
                self.io_store(o, e)
            else:
                v = self.take_str(o) if e.sym.vtype == "str" else self.take_num(o)
                self.emit("LET", o, e, v)
                self.num = None
        else:
            raise LiftError(f"{o!r}: RUNTIME {n} not handled")

    def pop_save(self, kind: str) -> Node:
        if not self.saves or self.saves[-1][0] != kind:
            raise LiftError(f"expected saved {kind}, have {self.saves}")
        return self.saves.pop()[1]

    def rom(self, o: Op) -> None:
        n = o.name
        if n in ROM_FUNCS:
            self.num = CallN(n, [self.take_num(o)])
        elif n == "NEGOP":
            self.num = UnN("-", self.take_num(o))
        elif n == "AYINT":
            return
        elif n == "MOVAF":
            self.arg = self.take_num(o)
        elif n in ("FSUBT", "FDIVT", "FPWRT"):
            if self.arg is None:
                raise LiftError(f"{o!r}: no ARG")
            self.num = BinN({"FSUBT": "-", "FDIVT": "/", "FPWRT": "^"}[n], self.arg, self.take_num(o))
            self.arg = None
        elif n == "CRDO":
            if self.print_ is not None and self.print_.args and (
                    self.print_.args[-1] == "," or isinstance(self.print_.args[-1], tuple)):
                # PRINT X, / PRINT TAB(..) emit no CR: this CR is a separate bare PRINT
                self.print_ = None
                self.emit("PRINT", o)
            elif self.print_ is not None:
                self.print_.end = o.addr + 3
                self.print_ = None
                self.stmt_start = None
            else:
                self.emit("PRINT", o)
        elif n in ROM_STMTS:
            self.emit(n, o)
        else:
            raise LiftError(f"{o!r}: ROM {n} not handled")

    def lit_text(self, addr: int) -> bytes:
        off = addr - self.w.load
        d = self.w.obj.data
        return d[off + 1 : off + 1 + d[off]]


# ---------------------------------------------------------------- analysis passes

def find_fns(w: Walk) -> dict[int, FnDef]:
    """DEF FN bodies: JMP over [P.op1, expression..., RTS]."""
    out: dict[int, FnDef] = {}
    ops = w.ops
    at = w.op_at()
    calls = {o.target for o in ops if o.kind == "jsr"}
    for i, o in enumerate(ops[:-1]):
        if o.kind != "jmp" or o.target <= o.addr:
            continue
        j = at.get(o.target)
        if j is None or j < i + 3:
            continue
        first = ops[i + 1]
        if (ops[j - 1].kind == "rts" and first.kind == "ent" and first.op == 1 and first.sym is not None
                and first.sym.region == "local" and first.sym.vtype == "real" and not first.sym.array
                and (o.addr + 3 in calls or True)):
            body = ops[i + 2 : j - 1]
            if all(b.kind in ("ent", "rt", "rom", "jsr", "lda", "ora", "flag_real", "flag_int", "lit") for b in body):
                out[o.addr + 3] = FnDef(o.addr + 3, first.sym)
    return out


def _producer(o: Op) -> bool:
    """An op that starts computing a new value (the first op of any expression's code)."""
    if o.kind == "ent":
        return o.op in (0, 6) or (o.sym is not None and o.sym.array) or (o.sym is not None and o.sym.vtype == "str")
    if o.kind == "rt":
        return o.name in ("STRLIT", "FRE", "POS")
    return o.kind == "lit"


STMT_RT = {"PRINTNUM", "PRINTINT", "PRINTSTR", "COMMA", "TAB", "SPC", "POKE", "PLOT", "HLIN", "VLIN", "WAIT2",
           "WAIT3", "HPLOT", "HPLOT.TO", "DRAW", "XDRAW", "DRAW.AT", "XDRAW.AT", "FOR.INIT", "IFOR.INIT", "NEXT",
           "ONGOTO", "ONGOSUB", "ONERR", "INPUT.BEGIN", "READ.NUM", "READ.STR", "GET.NUM", "GET.STR", "ARR.STORE",
           "END", "STOP", "POP", "RESTORE", "CLEAR", "DEBUG"} | ARG1


def _terminal(o: Op, cands: set[Sym], fns: dict[int, FnDef]) -> bool:
    """An op that ends a statement (so no temp can be live across it)."""
    if o.kind == "jsr":
        return o.target not in fns
    if o.kind in ("jmp", "rts", "bne3", "beq3", "beq1", "data", "end", "jmprt", "run"):
        return True
    if o.kind == "rt":
        return o.name in STMT_RT
    if o.kind == "rom":
        return o.name in ROM_STMTS or o.name == "CRDO"
    if o.kind == "ent" and o.sym is not None and (o.op == 1 or (o.op == 7 and o.sym.vtype == "int")):
        return o.sym not in cands and not o.sym.array and o.sym.kind != "const"
    return False


def find_temps(w: Walk, fns: dict[int, FnDef], line_starts: set[int]) -> set[Sym]:
    """Temps occupy the lowest local slots (numeric: int then real, before FN parameters;
    FN-body temps right after the parameters; strings: first in the string area).  A slot
    is a temp while every read of it follows a write within one statement.  Statement
    ends are recognised by statement calls, control flow and stores to non-temps, so the
    candidate set is shrunk to a fixed point."""
    h = w.header
    params = {f.param for f in fns.values()}
    locs = sorted((s for s in w.syms.values() if s.region == "local" and not s.array), key=lambda s: s.addr)
    num = [s for s in locs if s.addr <= h["LOCNUMEND"]]
    strs = [s for s in locs if s.addr > h["LOCNUMEND"]]
    first_param = min((p.addr for p in params), default=1 << 20)
    ops = w.ops
    at = w.op_at()
    bodies = []
    for f in fns.values():
        j = at[f.addr]
        while ops[j].kind != "rts":
            j += 1
        bodies.append((f.addr, ops[j].addr))

    def temp_like(s: Sym, cands: set[Sym]) -> bool:
        written = False
        reads = 0
        for k, o in enumerate(ops):
            if o.addr in line_starts:
                written = False
            if o.sym is not s:
                if written and _terminal(o, cands, fns):
                    written = False  # a statement ended: the value cannot be a temp's
                continue
            if o.kind == "ent" and o.op == 1:
                written = True
                nxt = ops[k + 1] if k + 1 < len(ops) else None
                if nxt is None or nxt.sym is s or not _producer(nxt):
                    return False
            elif not written:
                return False
            else:
                reads += 1
        return reads > 0

    def leading(cands: set[Sym]) -> set[Sym]:
        out: set[Sym] = set()
        for s in num:
            if s in params or s.addr > first_param or not temp_like(s, cands):
                break
            out.add(s)
        if fns:  # FN-body temps: after the parameters, referenced only inside FN bodies
            for s in num:
                if s.addr <= first_param or s in params:
                    continue
                refs = [o for o in ops if o.sym is s]
                if refs and all(any(a <= o.addr < b for a, b in bodies) for o in refs) and temp_like(s, cands):
                    out.add(s)
                else:
                    break
        for s in strs:
            if not temp_like(s, cands):
                break
            out.add(s)
        return out

    cands = set(num) | set(strs)
    while True:
        nxt = leading(cands)
        if nxt == cands:
            break
        cands = nxt
    for s in cands:
        s.kind = "fntemp" if s.addr > first_param else "temp"
    for p in params:
        p.kind = "param"
    return cands


def line_targets(w: Walk) -> set[int]:
    out: set[int] = set()
    for o in w.ops:
        if o.kind in ("jmp", "jsr"):
            out.add(o.target)
        elif o.kind == "rt" and o.name in ("ONGOTO", "ONGOSUB", "ONERR"):
            out.update(o.words)
    return out


def lift(w: Walk) -> Lifted:
    fns = find_fns(w)
    starts = line_targets(w) - set(fns)
    temps = find_temps(w, fns, starts)
    m = Machine(w, temps, fns)
    ops = w.ops
    at = w.op_at()
    # FN bodies first (their code sits in place; the DEF statement is emitted where it stands)
    body_ranges: dict[int, int] = {}
    for f in fns.values():
        i = at[f.addr]
        j = i + 1
        while ops[j].kind != "rts":
            j += 1
        sub = Machine(w, temps, fns)
        sub.num = Leaf(f.param, peep=True)
        sub.run(ops, i + 1, j)
        if sub.num is None or sub.stmts:
            raise LiftError(f"FN body at ${f.addr:04X} did not reduce to one expression")
        f.body = sub.num
        body_ranges[i - 1] = j + 1  # op index of the JMP over -> index after RTS
    i = 0
    while i < len(ops):
        o = ops[i]
        if i in body_ranges:
            f = fns[o.addr + 3]
            m.emit("DEF", o, f)
            m.stmts[-1].end = ops[body_ranges[i] - 1].addr + 1
            m.num = None
            i = body_ranges[i]
            continue
        if o.addr in starts or o.addr in fns:
            m.close_print()
            m.boundary = True
        i = m.step(ops, i, o)
    m.close_print()
    return Lifted(w, m.stmts, fns, temps, starts, m.unknowns)
