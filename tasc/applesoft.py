"""Applesoft language facts: tokens and variable-name extraction from listings."""

from __future__ import annotations

import re
from dataclasses import dataclass

# Applesoft tokens $80-$EA, in token order.
TOKENS: list[str] = (
    "END FOR NEXT DATA INPUT DEL DIM READ GR TEXT PR# IN# CALL PLOT HLIN VLIN HGR2 HGR HCOLOR= HPLOT DRAW "
    "XDRAW HTAB HOME ROT= SCALE= SHLOAD TRACE NOTRACE NORMAL INVERSE FLASH COLOR= POP VTAB HIMEM: LOMEM: "
    "ONERR RESUME RECALL STORE SPEED= LET GOTO RUN IF RESTORE & GOSUB RETURN REM STOP ON WAIT LOAD SAVE "
    "DEF POKE PRINT CONT LIST CLEAR GET NEW TAB( TO FN SPC( THEN AT NOT STEP + - * / ^ AND OR > = < SGN INT "
    "ABS USR FRE SCRN( PDL POS SQR RND LOG EXP COS SIN TAN ATN PEEK LEN STR$ VAL ASC CHR$ LEFT$ RIGHT$ MID$"
).split()
assert len(TOKENS) == 0xEB - 0x80, len(TOKENS)

_WORD_TOKENS = [t for t in TOKENS if t[0].isalpha()]


def strip_keywords(body: str) -> str:
    """Blank out keywords, scanning left to right with first match in token order
    (as the Applesoft tokenizer does; spaces are ignored)."""
    s = body.upper().replace(" ", "")
    out: list[str] = []
    i = 0
    while i < len(s):
        # Applesoft PARSE special case: "AT" followed by "N" is ATN; followed by "O" it is
        # "A" then "TO".
        if s.startswith("AT", i) and i + 2 < len(s) and s[i + 2] in "NO":
            if s[i + 2] == "N":
                out.append("   ")
                i += 3
            else:
                out.append("A")
                i += 1
            continue
        for t in _WORD_TOKENS:
            if s.startswith(t, i):
                out.append(" " * len(t))
                i += len(t)
                break
        else:
            out.append(s[i])
            i += 1
    return "".join(out)


@dataclass(frozen=True, order=True)
class Var:
    name: str  # first two significant characters
    vtype: str  # 'real' | 'int' | 'str'
    array: bool = False
    dims: tuple[int, ...] = ()  # arrays: max index per subscript (DIM, else 10 each)

    def __str__(self) -> str:
        return self.name + {"real": "", "int": "%", "str": "$"}[self.vtype] + ("()" if self.array else "")


def variables(listing: str) -> list[Var]:
    """Variables referenced in a plain-text listing (simple programs only).

    Removes string literals, REM/DATA tails and keywords, the way the Applesoft
    tokenizer would see them; names are cut to two characters.
    """
    found: list[Var] = []
    dimmed: dict[tuple[str, str], tuple[int, ...]] = {}
    for m in re.finditer(r"DIM\s*([^:\n]*)", listing.upper()):
        for d in re.finditer(r"([A-Z][A-Z0-9]*)([%$]?)\(([\d,\s]+)\)", m.group(1).replace(" ", "")):
            vt = {"%": "int", "$": "str", "": "real"}[d.group(2)]
            dimmed[(d.group(1)[:2], vt)] = tuple(int(x) for x in d.group(3).split(","))
    nsubs: dict[tuple[str, str], int] = {}
    for line in listing.splitlines():
        body = re.sub(r"^\s*\d+\s*", "", line)
        body = re.sub(r'"[^"]*"?', " ", body)
        body = re.split(r"\bREM\b|\bDATA\b", body)[0]
        # FN names are function names, not variables
        body = re.sub(r"FN\s*[A-Z][A-Z0-9]*", " ", body.upper())
        s = strip_keywords(body)
        # numeric literals (with exponents) are not names; a name can't start with a digit
        s = re.sub(r"(?<![A-Z0-9])(\d+\.?\d*|\.\d+)(E[+-]?\d+)?", " ", s)
        for m in re.finditer(r"([A-Z][A-Z0-9]*)([%$]?)(\(?)", s):
            name = m.group(1)[:2]
            vtype = {"%": "int", "$": "str", "": "real"}[m.group(2)]
            v = Var(name, vtype, m.group(3) == "(")
            if v.array:
                # count subscripts: commas at depth 1 after the '('
                depth, n, i = 0, 1, m.end()
                while i < len(s):
                    ch = s[i]
                    if ch == "(":
                        depth += 1
                    elif ch == ")":
                        if depth == 0:
                            break
                        depth -= 1
                    elif ch == "," and depth == 0:
                        n += 1
                    i += 1
                nsubs.setdefault((name, vtype), n)
            if all((f.name, f.vtype, f.array) != (v.name, v.vtype, v.array) for f in found):
                found.append(v)
    out: list[Var] = []
    for v in found:
        if v.array:
            dims = dimmed.get((v.name, v.vtype)) or (10,) * nsubs.get((v.name, v.vtype), 1)
            v = Var(v.name, v.vtype, True, dims)
        out.append(v)
    return out


def tokenize_line(text: str) -> bytes:
    """Tokenize the body of one program line like the Applesoft PARSE routine.

    Spaces are dropped except inside strings, REM and DATA; keywords match left to
    right, first match in token order, with the AT/ATN/A TO special case.
    """
    out = bytearray()
    s = text.upper()
    i = 0
    in_data = False
    while i < len(s):
        ch = s[i]
        if ch == '"':
            j = s.find('"', i + 1)
            j = len(s) - 1 if j < 0 else j
            out += s[i : j + 1].encode()
            i = j + 1
            continue
        if in_data:
            if ch == ":":
                in_data = False
            out.append(ord(ch))
            i += 1
            continue
        if ch == " ":
            i += 1
            continue
        # keyword match ignoring spaces inside the source
        squeezed = s[i:].replace(" ", "")
        hit = None
        if squeezed.startswith("AT") and len(squeezed) > 2 and squeezed[2] in "NO":
            hit = "ATN" if squeezed[2] == "N" else None
        else:
            for t in TOKENS:
                if squeezed.startswith(t):
                    hit = t
                    break
        if hit is not None:
            # consume len(hit) non-space characters
            n = 0
            while n < len(hit):
                if s[i] != " ":
                    n += 1
                i += 1
            code = 0x80 + TOKENS.index(hit)
            out.append(code)
            if hit in ("REM", "DATA"):  # spaces right after REM/DATA are dropped
                while i < len(s) and s[i] == " ":
                    i += 1
            if hit == "REM":
                out += s[i:].encode()
                break
            if hit == "DATA":
                in_data = True
            continue
        out.append(ord(ch))
        i += 1
    return bytes(out)


def tokenize_program(listing: str) -> bytes:
    """Tokenized program file data (link fields computed for load at $0801)."""
    data = bytearray()
    addr = 0x0801
    for line in listing.splitlines():
        line = line.strip()
        if not line:
            continue
        m = re.match(r"(\d+)\s*(.*)$", line)
        if not m:
            raise ValueError(f"bad line {line!r}")
        body = tokenize_line(m.group(2))
        nxt = addr + 4 + len(body) + 1
        data += bytes([nxt & 0xFF, nxt >> 8]) + int(m.group(1)).to_bytes(2, "little") + body + b"\x00"
        addr = nxt
    data += b"\x00\x00"
    return bytes(data)
