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

    def __str__(self) -> str:
        return self.name + {"real": "", "int": "%", "str": "$"}[self.vtype] + ("()" if self.array else "")


def variables(listing: str) -> list[Var]:
    """Variables referenced in a plain-text listing (simple programs only).

    Removes string literals, REM/DATA tails and keywords, the way the Applesoft
    tokenizer would see them; names are cut to two characters.
    """
    found: list[Var] = []
    for line in listing.splitlines():
        body = re.sub(r"^\s*\d+\s*", "", line)
        body = re.sub(r'"[^"]*"?', " ", body)
        body = re.split(r"\bREM\b|\bDATA\b", body)[0]
        s = strip_keywords(body)
        for m in re.finditer(r"([A-Z][A-Z0-9]*)([%$]?)(\(?)", s):
            name = m.group(1)[:2]
            vtype = {"%": "int", "$": "str", "": "real"}[m.group(2)]
            v = Var(name, vtype, m.group(3) == "(")
            if v not in found:
                found.append(v)
    return found
