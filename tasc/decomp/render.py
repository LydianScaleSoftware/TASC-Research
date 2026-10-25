"""Decompiler step 3: lay statements out in lines and render tokenized Applesoft.

Lines are rendered straight to tokenized bytes (keywords as tokens), so string
literals and DATA items may hold any byte.  `listing()` gives a readable text
form with non-printing bytes escaped as {$xx}.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from tasc.compiler.fin import fin
from tasc.compiler.parse import TOK
from tasc.decomp.lift import (
    BinN, CallN, Elem, FnN, Leaf, Lifted, Lit, Node, Stmt, UnN, Unknown,
)
from tasc.decomp.walk import Sym
from tasc.objfile import int_value, real_value

PRIO = {"OR": 0x46, "AND": 0x50, "=": 0x64, "<": 0x64, ">": 0x64, "<=": 0x64, ">=": 0x64, "<>": 0x64,
        "+": 0x79, "-": 0x79, "*": 0x7B, "/": 0x7B, "^": 0x7D}
ENDS_LINE = {"GOTO", "IFGOTO", "IFRETURN", "RETURN", "END", "STOP", "NEW", "ONERR", "RESUME"}


class RenderError(Exception):
    pass


def real_text(raw: bytes) -> str:
    """Shortest decimal text that the ROM's FIN packs to exactly `raw`."""
    v = real_value(raw)
    if v == 0:
        return "0"
    for p in range(1, 18):
        t = f"{v:.{p}G}"
        if "E" in t:
            m, e = t.split("E")
            t = f"{m}E{int(e)}"
        if "." in t and "E" not in t:
            t = t.rstrip("0").rstrip(".")
        if t.startswith("0."):
            t = t[1:]
        elif t.startswith("-0."):
            t = "-" + t[2:]
        try:
            if fin(t) == raw:
                return t
        except Exception:  # noqa: BLE001
            continue
    raise RenderError(f"no decimal text for {raw.hex()}")


def _rel(op: str) -> bytes:
    return bytes(TOK[c] for c in op)


@dataclass
class Renderer:
    names: dict[Sym, str]  # name with suffix, e.g. 'AB%', 'C$'
    line_of: dict[int, int]  # code address -> line number
    fn_names: dict[int, str]
    param_names: dict[Sym, str]
    lits: list[bytes] = field(default_factory=list)

    def name(self, s: Sym) -> bytes:
        if s.kind == "const" or s.region == "const":
            if s.vtype == "int":
                return str(int_value(s.const)).encode()
            return real_text(s.const).encode()
        if s in self.param_names:
            return self.param_names[s].encode()
        if s not in self.names:
            raise RenderError(f"no name for {s!r}")
        return self.names[s].encode()

    def expr(self, n: Node, ctx: int = 0, right: bool = False) -> bytes:
        if isinstance(n, Leaf):
            return self.name(n.sym)
        if isinstance(n, Lit):
            return b'"' + n.text + b'"'
        if isinstance(n, Elem):
            return self.name(n.sym) + b"(" + b",".join(self.expr(x) for x in n.subs) + b")"
        if isinstance(n, Unknown):
            return b"0"
        if isinstance(n, UnN):
            inner = self.expr(n.e, 0x100)
            return (bytes([TOK["-"]]) if n.op == "-" else bytes([TOK["NOT"]])) + inner
        if isinstance(n, CallN):
            nm = n.name
            tok = bytes([TOK[nm]]) + (b"" if nm.endswith("(") else b"(")
            return tok + b",".join(self.expr(x) for x in n.args) + b")"
        if isinstance(n, FnN):
            return bytes([TOK["FN"]]) + self.fn_names[n.fn].encode() + b"(" + self.expr(n.arg) + b")"
        if isinstance(n, BinN):
            p = PRIO[n.op]
            opb = _rel(n.op) if p == 0x64 else bytes([TOK[n.op]])
            s = self.expr(n.l, p, False) + opb + self.expr(n.r, p, True)
            if p < ctx or (p == ctx and right):
                s = b"(" + s + b")"
            return s
        raise RenderError(f"node {n!r}")

    def line_ref(self, addr: int) -> bytes:
        if addr not in self.line_of:
            raise RenderError(f"no line at ${addr:04X}")
        return str(self.line_of[addr]).encode()

    def stmt(self, st: Stmt) -> bytes:
        k, a = st.kind, st.args
        T = lambda name: bytes([TOK[name]])  # noqa: E731
        if k == "LET":
            return self.expr(a[0]) + T("=") + self.expr(a[1])  # type: ignore[arg-type]
        if k == "PRINT":
            out = T("PRINT")
            prev_expr = False
            for it in a:
                if it == ";":
                    out += b";"
                    prev_expr = False
                elif it == ",":
                    out += b","
                    prev_expr = False
                elif isinstance(it, tuple):
                    out += T(it[0] + "(") + self.expr(it[1]) + b")"
                    prev_expr = False
                else:
                    if prev_expr:
                        out += b";"
                    out += self.expr(it)  # type: ignore[arg-type]
                    prev_expr = True
            return out
        if k == "IF":
            return T("IF") + self.expr(a[0]) + T("THEN")  # type: ignore[arg-type]
        if k == "IFGOTO":
            return T("IF") + self.expr(a[0]) + T("THEN") + self.line_ref(a[1])  # type: ignore[arg-type]
        if k == "IFRETURN":
            return T("IF") + self.expr(a[0]) + T("THEN") + T("RETURN")  # type: ignore[arg-type]
        if k in ("GOTO", "GOSUB"):
            return T(k) + self.line_ref(a[0])  # type: ignore[arg-type]
        if k in ("ONGOTO", "ONGOSUB"):
            return T("ON") + self.expr(a[0]) + T(k[2:]) + b",".join(self.line_ref(x) for x in a[1])  # type: ignore
        if k == "ONERR":
            return T("ONERR") + T("GOTO") + self.line_ref(a[0])  # type: ignore[arg-type]
        if k == "FOR":
            out = T("FOR") + self.expr(a[0]) + T("=") + self.expr(a[1]) + T("TO") + self.expr(a[2])  # type: ignore
            if a[3] is not None:
                out += T("STEP") + self.expr(a[3])  # type: ignore[arg-type]
            return out
        if k == "NEXT":
            return T("NEXT") + (b",".join(self.expr(x) for x in a) if a[0] is not None else b"")  # type: ignore
        if k == "DEF":
            f = a[0]
            return (T("DEF") + T("FN") + self.fn_names[f.addr].encode() + b"(" + self.param_names[f.param].encode()  # type: ignore
                    + b")" + T("=") + self.expr(f.body))  # type: ignore[union-attr]
        if k == "INPUT":
            out = T("INPUT")
            if a[0] is not None:
                out += b'"' + a[0] + b'";'  # type: ignore[operator]
            return out + b",".join(self.expr(x) for x in a[1])  # type: ignore[union-attr]
        if k in ("READ", "GET"):
            return T(k) + b",".join(self.expr(x) for x in a)  # type: ignore[arg-type]
        if k == "DATA":
            items = []
            for it in a[0]:  # type: ignore[union-attr]
                if it == b"" or it != it.strip(b" ") or any(c in it for c in b",:") or it.startswith(b'"'):
                    items.append(b'"' + it + b'"')
                else:
                    items.append(it)
            return T("DATA") + b",".join(items)
        if k in ("PLOT", "POKE"):
            return T(k) + self.expr(a[0]) + b"," + self.expr(a[1])  # type: ignore[arg-type]
        if k in ("HLIN", "VLIN"):
            return T(k) + self.expr(a[0]) + b"," + self.expr(a[1]) + T("AT") + self.expr(a[2])  # type: ignore
        if k == "WAIT":
            return T("WAIT") + b",".join(self.expr(x) for x in a)  # type: ignore[arg-type]
        if k in ("HPLOT", "HPLOT.TO"):
            out = T("HPLOT") + (T("TO") if k == "HPLOT.TO" else b"") + self.expr(a[0]) + b"," + self.expr(a[1])  # type: ignore
            for extra in a[2:]:
                out += T("TO") + self.expr(extra[1]) + b"," + self.expr(extra[2])  # type: ignore[index]
            return out
        if k in ("DRAW", "XDRAW"):
            out = T(k) + self.expr(a[0])  # type: ignore[arg-type]
            if a[1] is not None:
                x, y = a[1]  # type: ignore[misc]
                out += T("AT") + self.expr(x) + b"," + self.expr(y)
            return out
        if k == "CLEARCOMMON":
            return T("REM") + b"! CLEAR COMMON"
        if k == "CLEARCHAIN":
            return T("REM") + b"! CLEAR CHAIN"
        if k in TOK and not a:
            return T(k)
        if k in TOK and len(a) == 1:
            return T(k) + self.expr(a[0])  # type: ignore[arg-type]
        raise RenderError(f"statement {k}")


@dataclass
class Line:
    number: int
    stmts: list[Stmt]
    addr: int


def layout(lf: Lifted, step: int = 5, first: int = 10) -> list[Line]:
    """Group statements into lines: a line starts at every branch target and after any
    unconditional transfer; IF ... THEN keeps its statements up to the next line's
    address; a statement that uses a just-stored value without reloading it (store-load
    peephole) stays on the previous statement's line."""
    lines: list[Line] = []
    cur: Line | None = None
    scope_end = 0
    for st in lf.stmts:
        new = cur is None or st.addr in lf.line_starts
        if cur is not None and not new:
            last = cur.stmts[-1]
            if scope_end and st.addr < scope_end:
                new = False
            elif st.join:
                new = False
            elif last.kind in ENDS_LINE or scope_end:
                new = True
            else:
                new = True
        if st.join and new and cur is not None:
            raise RenderError(f"${st.addr:04X}: peephole join across a line start")
        if new:
            cur = Line(0, [], st.addr)
            lines.append(cur)
            scope_end = 0
        assert cur is not None
        cur.stmts.append(st)
        if st.kind == "IF":
            scope_end = st.scope_end
        if scope_end and st.end >= scope_end and st.kind != "IF":
            pass
    for i, ln in enumerate(lines):
        ln.number = first + step * i
    return lines


def program_bytes(lines: list[tuple[int, bytes]]) -> bytes:
    data = bytearray()
    addr = 0x0801
    for num, body in lines:
        nxt = addr + 4 + len(body) + 1
        data += bytes([nxt & 0xFF, nxt >> 8]) + num.to_bytes(2, "little") + body + b"\x00"
        addr = nxt
    data += b"\x00\x00"
    return bytes(data)


def listing(lines: list[tuple[int, bytes]]) -> str:
    rev = {v: k for k, v in TOK.items()}
    out = []
    for num, body in lines:
        s = []
        quoted = False
        for b in body:
            if b == 0x22:
                quoted = not quoted
                s.append('"')
            elif b >= 0x80 and not quoted:
                s.append(" " + rev[b] + " ")
            elif 0x20 <= b < 0x7F:
                s.append(chr(b))
            else:
                s.append(f"{{${b:02X}}}")
        out.append(f"{num} " + "".join(s).strip().replace("  ", " "))
    return "\n".join(out) + "\n"
