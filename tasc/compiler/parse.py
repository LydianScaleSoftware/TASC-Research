"""Applesoft program reader and parser (tokenized bytes -> AST).

Input is the tokenized program as stored in an Applesoft file (link, line
number, token bytes, $00 per line).  Expressions follow Applesoft priorities
(ROM MATHTBL): unary - and NOT $7F, ^ $7D, * / $7B, + - $79, relational $64,
AND $50, OR $46; binary operators are left associative.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from tasc.applesoft import TOKENS

TOK = {name: 0x80 + i for i, name in enumerate(TOKENS)}
TOKNAME = {v: k for k, v in TOK.items()}


class ParseError(Exception):
    pass


# ---------------------------------------------------------------- program file

@dataclass
class Line:
    number: int
    body: bytes


def read_program(data: bytes) -> list[Line]:
    lines: list[Line] = []
    p = 0
    while p + 4 <= len(data):
        link = data[p] | data[p + 1] << 8
        if link == 0:
            break
        num = data[p + 2] | data[p + 3] << 8
        end = data.index(0, p + 4)
        lines.append(Line(num, data[p + 4 : end]))
        p = end + 1
    return lines


# ---------------------------------------------------------------- AST

@dataclass
class Expr:
    pass


@dataclass
class Num(Expr):
    text: str


@dataclass
class Str(Expr):
    text: bytes


@dataclass
class VarRef(Expr):
    name: str  # two significant chars
    suffix: str  # '', '%', '$'
    subs: list[Expr] | None = None  # array subscripts


@dataclass
class FnCall(Expr):  # user function FN name(arg)
    name: str
    arg: Expr


@dataclass
class Builtin(Expr):  # SGN( ... MID$(
    name: str
    args: list[Expr]


@dataclass
class Unary(Expr):
    op: str  # '-', '+', 'NOT'
    e: Expr


@dataclass
class Bin(Expr):
    op: str  # + - * / ^ AND OR = < > <= >= <>
    l: Expr
    r: Expr


@dataclass
class Stmt:
    kind: str
    args: list[object] = field(default_factory=list)
    kw: bool = True  # began with a keyword token (an implicit LET does not)
    then_colon: bool = False  # IF: a ':' directly after THEN (an empty statement follows)


# ---------------------------------------------------------------- tokenizer view

class Cursor:
    def __init__(self, body: bytes) -> None:
        self.b = body
        self.p = 0

    def peek(self) -> int | None:
        return self.b[self.p] if self.p < len(self.b) else None

    def at(self, tok: str) -> bool:
        c = self.peek()
        if tok in TOK:
            return c == TOK[tok]
        return c is not None and c == ord(tok)

    def take(self, tok: str) -> bool:
        if self.at(tok):
            self.p += 1
            return True
        return False

    def expect(self, tok: str) -> None:
        if not self.take(tok):
            raise ParseError(f"expected {tok!r} at {self.p} in {self.b!r}")

    def eos(self) -> bool:
        c = self.peek()
        return c is None or c == ord(":")

    def rest(self) -> bytes:
        r = self.b[self.p :]
        self.p = len(self.b)
        return r

    def name(self) -> tuple[str, str] | None:
        """A variable name: letter, then letters/digits; optional % or $."""
        c = self.peek()
        if c is None or not (65 <= c <= 90):
            return None
        s = self.p
        while self.p < len(self.b) and (65 <= self.b[self.p] <= 90 or 48 <= self.b[self.p] <= 57):
            self.p += 1
        full = self.b[s : self.p].decode()
        suffix = ""
        if self.peek() in (ord("%"), ord("$")):
            suffix = chr(self.b[self.p])
            self.p += 1
        return full[:2], suffix

    def number(self) -> str | None:
        """Numeric literal text as written (digits, '.', E exponent)."""
        s = self.p
        b = self.b
        while self.p < len(b) and (48 <= b[self.p] <= 57 or b[self.p] == ord(".")):
            self.p += 1
        if self.p == s:
            return None
        if self.p < len(b) and b[self.p] == ord("E"):
            q = self.p + 1
            if q < len(b) and b[q] in (ord("+"), ord("-"), TOK["+"], TOK["-"]):
                q += 1
            if q < len(b) and 48 <= b[q] <= 57:
                while q < len(b) and 48 <= b[q] <= 57:
                    q += 1
                self.p = q
        raw = b[s : self.p]
        return raw.replace(bytes([TOK["+"]]), b"+").replace(bytes([TOK["-"]]), b"-").decode()


# ---------------------------------------------------------------- expressions

PRIO = {"OR": 0x46, "AND": 0x50, "REL": 0x64, "+": 0x79, "-": 0x79, "*": 0x7B, "/": 0x7B, "^": 0x7D}
FUNCS = ["SGN", "INT", "ABS", "USR", "FRE", "SCRN(", "PDL", "POS", "SQR", "RND", "LOG", "EXP", "COS", "SIN",
         "TAN", "ATN", "PEEK", "LEN", "STR$", "VAL", "ASC", "CHR$", "LEFT$", "RIGHT$", "MID$"]


def _binop_at(c: Cursor) -> tuple[str, int] | None:
    t = c.peek()
    if t is None:
        return None
    for op in ("+", "-", "*", "/", "^", "AND", "OR"):
        if t == TOK[op]:
            return op, PRIO[op]
    if t in (TOK[">"], TOK["="], TOK["<"]):
        return "REL", PRIO["REL"]
    return None


def _relop(c: Cursor) -> str:
    bits = set()
    while c.peek() in (TOK[">"], TOK["="], TOK["<"]):
        bits.add(TOKNAME[c.b[c.p]])
        c.p += 1
    return {frozenset("="): "=", frozenset("<"): "<", frozenset(">"): ">", frozenset("<="): "<=",
            frozenset(">="): ">=", frozenset("<>"): "<>"}[frozenset("".join(sorted(bits)))]


def is_str(e: Expr) -> bool:
    if isinstance(e, Str):
        return True
    if isinstance(e, VarRef):
        return e.suffix == "$"
    if isinstance(e, Builtin):
        return e.name in ("STR$", "CHR$", "LEFT$", "RIGHT$", "MID$")
    if isinstance(e, Bin):
        return e.op == "+" and is_str(e.l)
    return False


def expr(c: Cursor, minprio: int = 0) -> Expr:
    left = unary(c)
    while True:
        if (isinstance(left, Bin) and left.op == "+" and is_str(left) and c.peek() is not None
                and c.peek() in (TOK["*"], TOK["/"], TOK["^"], TOK["NOT"])):
            # PASS1 4555-4580: a pending concatenation cannot be reduced by an operator of
            # higher input priority than + (9): INCOMPLETE
            raise ParseError("INCOMPLETE")
        op = _binop_at(c)
        if op is None or op[1] <= minprio:
            return left
        if is_str(left) and op[0] not in ("+", "REL"):
            return left  # observed: an operator invalid for strings ends the expression (PRINT juxtaposition)
        name, prio = op
        if name == "REL":
            name = _relop(c)
        else:
            c.p += 1
        right = expr(c, prio)
        left = Bin(name, left, right)


def unary(c: Cursor) -> Expr:
    if c.take("-"):
        return Unary("-", expr(c, 0x7F - 1) if False else _tight(c))
    if c.take("+"):
        return Unary("+", _tight(c))
    if c.take("NOT"):
        return Unary("NOT", _tight(c))
    return atom(c)


def _tight(c: Cursor) -> Expr:
    """Operand of unary - / NOT: binds tighter than ^ (priority $7F)."""
    return unary(c)


def atom(c: Cursor) -> Expr:
    if c.take("("):
        e = expr(c)
        c.expect(")")
        return e
    if c.peek() == ord('"'):
        c.p += 1
        s = c.p
        while c.p < len(c.b) and c.b[c.p] != ord('"'):
            c.p += 1
        text = c.b[s : c.p]
        c.take('"')
        return Str(text)
    n = c.number()
    if n is not None:
        return Num(n)
    if c.take("FN"):
        nm = c.name()
        if nm is None:
            raise ParseError("FN name")
        c.expect("(")
        a = expr(c)
        c.expect(")")
        return FnCall(nm[0], a)
    for f in FUNCS:
        if c.take(f):
            if not f.endswith("("):
                c.expect("(")
            args = [expr(c)]
            while c.take(","):
                args.append(expr(c))
            c.expect(")")
            return Builtin(f.rstrip("("), args)
    nm = c.name()
    if nm is None:
        raise ParseError(f"bad expression at {c.p} in {c.b!r}")
    if c.take("("):
        subs = [expr(c)]
        while c.take(","):
            subs.append(expr(c))
        c.expect(")")
        return VarRef(nm[0], nm[1], subs)
    return VarRef(nm[0], nm[1])


def varref(c: Cursor) -> VarRef:
    e = atom(c)
    if not isinstance(e, VarRef):
        raise ParseError("variable expected")
    return e


def line_number(c: Cursor) -> int:
    n = c.number()
    if n is None:
        raise ParseError("line number expected")
    return int(n)


# ---------------------------------------------------------------- statements

SIMPLE0 = ["HOME", "TEXT", "GR", "HGR", "HGR2", "NORMAL", "INVERSE", "FLASH", "END", "STOP", "RETURN", "POP",
           "RESTORE", "CLEAR", "NEW"]
ARG1 = ["VTAB", "HTAB", "COLOR=", "HCOLOR=", "SPEED=", "ROT=", "SCALE=", "CALL", "IN#", "PR#", "HIMEM:"]


def statement(c: Cursor) -> Stmt:
    for k in SIMPLE0:
        if c.take(k):
            return Stmt(k)
    for k in ARG1:
        if c.take(k):
            return Stmt(k, [expr(c)])
    if c.take("REM"):
        return Stmt("REM", [c.rest()])
    if c.take("DATA"):
        raw = bytearray()
        while c.peek() is not None and c.peek() != ord(":"):
            if c.peek() == ord('"'):
                raw.append(c.b[c.p])
                c.p += 1
                while c.peek() is not None and c.peek() != ord('"'):
                    raw.append(c.b[c.p])
                    c.p += 1
                if c.peek() is not None:
                    raw.append(c.b[c.p])
                    c.p += 1
                continue
            raw.append(c.b[c.p])
            c.p += 1
        return Stmt("DATA", [bytes(raw)])
    if c.take("GOTO"):
        return Stmt("GOTO", [line_number(c)])
    if c.take("RUN"):
        return Stmt("RUN", [] if c.eos() else [line_number(c)])
    if c.take("GOSUB"):
        return Stmt("GOSUB", [line_number(c)])
    if c.take("IF"):
        cond = expr(c)
        if c.take("GOTO"):
            return Stmt("IFGOTO", [cond, line_number(c)])
        c.expect("THEN")
        if c.take("GOTO"):
            return Stmt("IFGOTO", [cond, line_number(c)])
        if c.peek() is not None and 48 <= c.peek() <= 57:  # type: ignore[operator]
            return Stmt("IFGOTO", [cond, line_number(c)])
        st = Stmt("IF", [cond])  # following statements on the line are conditional
        st.then_colon = c.at(":")
        return st
    if c.take("ON"):
        e = expr(c)
        kind = "ONGOTO" if c.take("GOTO") else ("ONGOSUB" if c.take("GOSUB") else None)
        if kind is None:
            raise ParseError("ON without GOTO/GOSUB")
        targets = [line_number(c)]
        while c.take(","):
            targets.append(line_number(c))
        return Stmt(kind, [e, targets])
    if c.take("ONERR"):
        c.expect("GOTO")
        return Stmt("ONERR", [line_number(c)])
    if c.take("RESUME"):
        return Stmt("RESUME")
    if c.take("FOR"):
        v = varref(c)
        if v.suffix or v.subs is not None:
            raise ParseError("SYNTAX: FOR needs a real or INTEGER-declared name")  # PASS1 395-445
        c.expect("=")
        a = expr(c)
        c.expect("TO")
        b = expr(c)
        step = expr(c) if c.take("STEP") else None
        return Stmt("FOR", [v, a, b, step])
    if c.take("NEXT"):
        vs: list[VarRef] = []
        if not c.eos():
            vs.append(varref(c))
            while c.take(","):
                vs.append(varref(c))
        if any(v.suffix or v.subs is not None for v in vs):
            raise ParseError("SYNTAX: NEXT variable")
        return Stmt("NEXT", [vs])
    if c.take("PRINT"):
        items: list[object] = []
        while not c.eos():
            if c.take(";"):
                items.append(";")
            elif c.take(","):
                items.append(",")
            elif c.take("TAB("):
                items.append(("TAB", expr(c)))
                c.expect(")")
            elif c.take("SPC("):
                items.append(("SPC", expr(c)))
                c.expect(")")
            else:
                items.append(expr(c))
        return Stmt("PRINT", items)
    if c.take("INPUT"):
        prompt = None
        if c.peek() == ord('"'):
            p = atom(c)
            assert isinstance(p, Str)
            prompt = p
            c.expect(";")
        vs = [varref(c)]
        while c.take(","):
            vs.append(varref(c))
        return Stmt("INPUT", [prompt, vs])
    if c.take("GET"):
        return Stmt("GET", [varref(c)])
    if c.take("READ"):
        vs = [varref(c)]
        while c.take(","):
            vs.append(varref(c))
        return Stmt("READ", [vs])
    if c.take("DIM"):
        vs = [varref(c)]
        while c.take(","):
            vs.append(varref(c))
        return Stmt("DIM", [vs])
    if c.take("DEF"):
        c.expect("FN")
        nm = c.name()
        if nm is None:
            raise ParseError("DEF FN name")
        c.expect("(")
        p = c.name()
        if p is None:
            raise ParseError("DEF FN parameter")
        c.expect(")")
        c.expect("=")
        return Stmt("DEF", [nm[0], p, expr(c)])
    if c.take("PLOT"):
        a = expr(c)
        c.expect(",")
        return Stmt("PLOT", [a, expr(c)])
    if c.take("HLIN") or c.take("VLIN"):
        kind = TOKNAME[c.b[c.p - 1]]
        a = expr(c)
        c.expect(",")
        b = expr(c)
        c.expect("AT")
        return Stmt(kind, [a, b, expr(c)])
    if c.take("POKE"):
        a = expr(c)
        c.expect(",")
        return Stmt("POKE", [a, expr(c)])
    if c.take("WAIT"):
        args = [expr(c)]
        while c.take(","):
            args.append(expr(c))
        return Stmt("WAIT", args)
    if c.take("HPLOT"):
        pts: list[object] = []
        if c.take("TO"):
            pts.append("TO")
        while True:
            x = expr(c)
            c.expect(",")
            pts.append((x, expr(c)))
            if not c.take("TO"):
                break
            pts.append("TO")
        return Stmt("HPLOT", pts)
    if c.take("DRAW") or c.take("XDRAW"):
        kind = TOKNAME[c.b[c.p - 1]]
        s = expr(c)
        at = None
        if c.take("AT"):
            x = expr(c)
            c.expect(",")
            at = (x, expr(c))
        return Stmt(kind, [s, at])
    c.take("LET")
    v = varref(c)
    c.expect("=")
    return Stmt("LET", [v, expr(c)])


def skip_statement(c: Cursor) -> None:
    """Skip one statement without parsing it (TASC's dead-code skip): to the next ':'
    outside quotes; REM skips the rest of the line."""
    if c.at("REM"):
        c.rest()
        return
    quoted = False
    while c.peek() is not None:
        ch = c.peek()
        if ch == ord('"'):
            quoted = not quoted
        elif ch == ord(":") and not quoted:
            return
        c.p += 1


# PASS1 dispatcher entries that go to the "WARNING / LINE NUMBER n / IGNORED" handler (2485)
UNSUPPORTED = {TOK[k] for k in ("DEL", "SHLOAD", "TRACE", "NOTRACE", "LOMEM:", "RECALL", "STORE", "&", "LOAD",
                                "SAVE", "CONT", "LIST")}


def iter_statements(body: bytes):  # type: ignore[no-untyped-def]
    """Yields (kw, parse) per statement: kw = begins with a keyword token; parse(skip)
    parses the statement (or skips it when skip=True and returns None)."""
    c = Cursor(body)
    while c.peek() is not None:
        if c.take(":"):
            continue
        kw = (c.peek() or 0) >= 0x80
        # PASS1 330: DATA and REM are exempt from the dead-code skip
        is_data = c.at("DATA") or c.at("REM")
        unsupported = c.peek() in UNSUPPORTED
        done = False

        def parse(skip: bool, c: Cursor = c, kw: bool = kw) -> Stmt | None:
            nonlocal done
            done = True
            if skip:
                skip_statement(c)
                return None
            st = statement(c)
            st.kw = kw
            if c.peek() is not None and not c.at(":") and st.kind != "IF":
                raise ParseError(f"junk after statement at {c.p} in {c.b!r}")
            return st

        yield kw, is_data, unsupported, parse, c.peek()
        if not done:
            raise ParseError("statement neither parsed nor skipped")


def parse_line(body: bytes) -> list[Stmt]:
    c = Cursor(body)
    out: list[Stmt] = []
    while c.peek() is not None:
        if c.take(":"):
            continue
        kw = (c.peek() or 0) >= 0x80
        out.append(statement(c))
        out[-1].kw = kw
        if c.peek() is not None and not c.at(":") and out[-1].kind not in ("IF",):
            raise ParseError(f"junk after statement at {c.p} in {body!r}")
    return out
