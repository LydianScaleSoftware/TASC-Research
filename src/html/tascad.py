#!/usr/bin/env python3
"""TASCAD: The AppleSoft Compiler and Decompiler.

A Python reimplementation of Microsoft's TASC 2.01 Applesoft compiler (1981) that
produces the same object files byte for byte, and a decompiler that turns a TASC
object file back into an Applesoft program which compiles to the same bytes.

    tascad compile SOURCE [-o OBJECT] [options]
        SOURCE is a text listing (numbered lines) or a tokenized Applesoft program
        (as saved by DOS, without the 2-byte length). Writes the object file as TASC
        does (the contents of the binary file; its load address is printed).
          --library ADDR --program ADDR|HGR1|HGR2 --variables ADDR   memory layout
          --no-int-arith --no-int-const --resume                     code options
          --compare OBJECT   check the result against an existing object file
          --map              print the line number table (line, address)

    tascad decompile OBJECT [-o LISTING] [--bas PROGRAM] [--load ADDR]
        Reads a TASC object file, works out its load address and memory layout from
        its header, finds the code options by trying them, and writes the Applesoft
        program (a text listing, and with --bas the tokenized program). The result
        is checked by compiling it again: it is reported only if the bytes match.

Files are read from and written to the local filesystem. A file inside a disk image
is named IMAGE::NAME (for example "TASC.dsk::BALL" or -o "WORK.dsk::BALL.OBJ"); disk
images are read and written with CiderPress II's command-line program, found through
--cp2 PATH, the CP2PATH environment variable, or cp2 on the PATH. A binary file read
from an image brings its load address; an object written to an image is a binary file
at its load address, a program (--bas) an Applesoft file. --replace lets a write
replace a file already on the image.

Addresses may be decimal, $hex or 0xhex. Requires Python 3.9 or later (tested on 3.9.6
and 3.14); standard library only.

This file is the whole program: the modules below are loaded from it by the
small import hook at the end. Run it with: python3 tascad.py compile|decompile ...
"""

_MODULES = {}


# ============================================================================
# module tasc (package)
# ============================================================================
_MODULES['tasc'] = (r'''"""TASC reverse-engineering toolkit."""
''', True)


# ============================================================================
# module tasc.options
# ============================================================================
_MODULES['tasc.options'] = (r'''"""TASC compile options (manual 5.1), shared by the compiler, the decompiler and the emulator harness."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Options:
    """TASC compile options (manual 5.1).  None / default values mean <RETURN>.

    library, variables: address as a number.  program: number, 'HGR1' or 'HGR2'.
    """

    library: int | None = None
    program: int | str | None = None
    variables: int | None = None
    listing: bool = True
    pause: bool = True
    int_arith: bool = True
    int_const: bool = True
    resume: bool = False

    def memory_default(self) -> bool:
        return self.library is None and self.program is None and self.variables is None

    def options_default(self) -> bool:
        return (self.listing, self.pause, self.int_arith, self.int_const, self.resume) == (
            True, True, True, True, False)

    def tag(self) -> str:
        """Short id: e.g. 'ia1ic1rd0' plus memory parts when not default."""
        t = f"ia{int(self.int_arith)}ic{int(self.int_const)}rd{int(self.resume)}"
        if not self.memory_default():
            t += f"-L{self.library or ''}P{self.program or ''}V{self.variables or ''}"
        return t

    def answers(self) -> list[tuple[str, str]]:
        def addr(v: int | str | None) -> str:
            return "" if v is None else str(v)

        def yn(v: bool) -> str:
            return "YES" if v else "NO"

        ans: list[tuple[str, str]] = [("(DEFAULT", "")]  # object file name
        if self.memory_default():
            ans.append(("MEMORY USAGE", ""))
        else:
            ans += [
                ("MEMORY USAGE", "NO"),
                ("ADDRESS FOR LIBRARY", addr(self.library)),
                ("END OF LIBRARY)?", addr(self.program)),
                ("ADDRESS FOR VARIABLES", addr(self.variables)),
                ("ADDRESSES CORRECT?", "YES"),
            ]
        if self.options_default():
            ans.append(("OPTIONS:", ""))
        else:
            ans += [
                ("OPTIONS:", "NO"),
                ("COMPILATION LISTING", yn(self.listing)),
                ("PAUSE ON ERRORS", yn(self.pause)),
                ("INTEGER ARITHMETIC", yn(self.int_arith)),
                ("INTEGER CONSTANTS", yn(self.int_const)),
                ("RESUME/DEBUG CODE", yn(self.resume)),
            ]
        return ans
''', False)


# ============================================================================
# module tasc.applesoft
# ============================================================================
_MODULES['tasc.applesoft'] = (r'''"""Applesoft language facts: tokens and variable-name extraction from listings."""

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
''', False)


# ============================================================================
# module tasc.m6502
# ============================================================================
_MODULES['tasc.m6502'] = (r'''"""Minimal deterministic NMOS 6502 decoder (documented opcodes only)."""

from __future__ import annotations

from dataclasses import dataclass

# mode -> (operand length, format)
MODES: dict[str, tuple[int, str]] = {
    "imp": (0, ""),
    "acc": (0, "A"),
    "imm": (1, "#${:02X}"),
    "zp": (1, "${:02X}"),
    "zpx": (1, "${:02X},X"),
    "zpy": (1, "${:02X},Y"),
    "izx": (1, "(${:02X},X)"),
    "izy": (1, "(${:02X}),Y"),
    "abs": (2, "${:04X}"),
    "abx": (2, "${:04X},X"),
    "aby": (2, "${:04X},Y"),
    "ind": (2, "(${:04X})"),
    "rel": (1, "${:04X}"),
}

_TABLE = """
00 BRK imp|01 ORA izx|05 ORA zp|06 ASL zp|08 PHP imp|09 ORA imm|0A ASL acc|0D ORA abs|0E ASL abs
10 BPL rel|11 ORA izy|15 ORA zpx|16 ASL zpx|18 CLC imp|19 ORA aby|1D ORA abx|1E ASL abx
20 JSR abs|21 AND izx|24 BIT zp|25 AND zp|26 ROL zp|28 PLP imp|29 AND imm|2A ROL acc|2C BIT abs|2D AND abs|2E ROL abs
30 BMI rel|31 AND izy|35 AND zpx|36 ROL zpx|38 SEC imp|39 AND aby|3D AND abx|3E ROL abx
40 RTI imp|41 EOR izx|45 EOR zp|46 LSR zp|48 PHA imp|49 EOR imm|4A LSR acc|4C JMP abs|4D EOR abs|4E LSR abs
50 BVC rel|51 EOR izy|55 EOR zpx|56 LSR zpx|58 CLI imp|59 EOR aby|5D EOR abx|5E LSR abx
60 RTS imp|61 ADC izx|65 ADC zp|66 ROR zp|68 PLA imp|69 ADC imm|6A ROR acc|6C JMP ind|6D ADC abs|6E ROR abs
70 BVS rel|71 ADC izy|75 ADC zpx|76 ROR zpx|78 SEI imp|79 ADC aby|7D ADC abx|7E ROR abx
81 STA izx|84 STY zp|85 STA zp|86 STX zp|88 DEY imp|8A TXA imp|8C STY abs|8D STA abs|8E STX abs
90 BCC rel|91 STA izy|94 STY zpx|95 STA zpx|96 STX zpy|98 TYA imp|99 STA aby|9A TXS imp|9D STA abx
A0 LDY imm|A1 LDA izx|A2 LDX imm|A4 LDY zp|A5 LDA zp|A6 LDX zp|A8 TAY imp|A9 LDA imm|AA TAX imp|AC LDY abs|AD LDA abs|AE LDX abs
B0 BCS rel|B1 LDA izy|B4 LDY zpx|B5 LDA zpx|B6 LDX zpy|B8 CLV imp|B9 LDA aby|BA TSX imp|BC LDY abx|BD LDA abx|BE LDX aby
C0 CPY imm|C1 CMP izx|C4 CPY zp|C5 CMP zp|C6 DEC zp|C8 INY imp|C9 CMP imm|CA DEX imp|CC CPY abs|CD CMP abs|CE DEC abs
D0 BNE rel|D1 CMP izy|D5 CMP zpx|D6 DEC zpx|D8 CLD imp|D9 CMP aby|DD CMP abx|DE DEC abx
E0 CPX imm|E1 SBC izx|E4 CPX zp|E5 SBC zp|E6 INC zp|E8 INX imp|E9 SBC imm|EA NOP imp|EC CPX abs|ED SBC abs|EE INC abs
F0 BEQ rel|F1 SBC izy|F5 SBC zpx|F6 INC zpx|F8 SED imp|F9 SBC aby|FD SBC abx|FE INC abx
"""

OPCODES: dict[int, tuple[str, str]] = {}
for _row in _TABLE.split("|"):
    for _item in _row.strip().splitlines():
        _op, _mn, _mode = _item.split()
        OPCODES[int(_op, 16)] = (_mn, _mode)


@dataclass(frozen=True)
class Insn:
    addr: int
    raw: bytes
    mnemonic: str  # '???' for an undefined opcode (shown as .BYTE)
    mode: str
    operand: int | None  # resolved target for rel

    @property
    def length(self) -> int:
        return len(self.raw)

    def text(self, names: dict[int, str] | None = None) -> str:
        if self.mnemonic == "???":
            return f".BYTE ${self.raw[0]:02X}"
        n, fmt = MODES[self.mode]
        if n == 0:
            return f"{self.mnemonic} {fmt}".rstrip()
        assert self.operand is not None
        if names and self.mode in ("abs", "rel", "zp") and self.operand in names:
            return f"{self.mnemonic} {names[self.operand]}"
        return f"{self.mnemonic} {fmt.format(self.operand)}"


def decode(mem: bytes, base: int, addr: int) -> Insn:
    """Decode the instruction at `addr`; mem[0] is at `base`."""
    off = addr - base
    op = mem[off]
    if op not in OPCODES:
        return Insn(addr, mem[off : off + 1], "???", "imp", None)
    mn, mode = OPCODES[op]
    n = MODES[mode][0]
    raw = mem[off : off + 1 + n]
    if len(raw) < 1 + n:
        return Insn(addr, mem[off : off + 1], "???", "imp", None)
    operand: int | None = None
    if n == 1:
        operand = raw[1]
        if mode == "rel":
            operand = (addr + 2 + (raw[1] - 256 if raw[1] >= 128 else raw[1])) & 0xFFFF
    elif n == 2:
        operand = raw[1] | (raw[2] << 8)
    return Insn(addr, raw, mn, mode, operand)


def linear(mem: bytes, base: int, start: int, end: int) -> list[Insn]:
    """Decode linearly from start up to (not including) end.  Only for known code."""
    out: list[Insn] = []
    a = start
    while a < end:
        i = decode(mem, base, a)
        out.append(i)
        a += i.length
    return out


def fmt(i: Insn, names: dict[int, str] | None = None) -> str:
    hexb = " ".join(f"{b:02X}" for b in i.raw)
    return f"{i.addr:04X}: {hexb:<9} {i.text(names)}"
''', False)


# ============================================================================
# module tasc.symbols
# ============================================================================
_MODULES['tasc.symbols'] = (r'''"""Address-name table: Applesoft ROM, Monitor, zero page (manual App. F), RUNTIME.

RUNTIME addresses are for the 2.01 RUNTIME loaded at $0803.  Status of each
RUNTIME name is 'observed' until a template test confirms it.
"""

from __future__ import annotations

ROM: dict[int, str] = {
    0xDAFB: "CRDO",  # print carriage return
    0xFC58: "HOME",
    0xFD8B: "CROUT1",
    0xE752: "GETADR",
    0xE10C: "AYINT",  # FAC -> integer (array subscripts)
    0xEB63: "MOVAF", 0xE7AA: "FSUBT", 0xEAF9: "LOAD.FAC.FROM.YA", 0xEB2B: "STORE.FAC.AT.YX.ROUNDED",
    0xE7BE: "FADD", 0xE7A7: "FSUB", 0xE97F: "FMULT", 0xEBB2: "FCOMP", 0xE9E3: "LOAD.ARG.FROM.YA", 0xEA66: "FDIV",
    0xEA69: "FDIVT", 0xD412: "ERROR", 0xDB5C: "OUTDO", 0xD52C: "INLIN", 0xFDED: "COUT", 0xFD0C: "RDKEY",
    0xE941: "LOG", 0xEB90: "SGN", 0xEBAF: "ABS", 0xEC23: "INT", 0xEE8D: "SQR", 0xEE97: "FPWRT",
    0xEED0: "NEGOP", 0xEF09: "EXP", 0xEFAE: "RND", 0xEFEA: "COS", 0xEFF1: "SIN", 0xF03A: "TAN", 0xF09E: "ATN",
    0xF273: "NORMAL", 0xF277: "INVERSE", 0xF280: "FLASH", 0xF390: "GR", 0xF399: "TEXT", 0xF3D8: "HGR2", 0xF3E2: "HGR",
    0x000A: "USRVEC",
}

ZERO_PAGE: dict[int, str] = {
    0x12: "DATAPTR", 0x14: "HIGHEST", 0x16: "ZTEMP16",
    0x58: "FLTINTJMP", 0x5B: "ONERRJMP",
    0x67: "TXTTAB", 0x69: "COMBEG1", 0x6B: "NUMCOMEND", 0x6D: "STRCOMEND", 0x6F: "STRBOT1",
    0x73: "MEMSIZ", 0x75: "OBJPC", 0x7B: "LOCBEG1", 0x7D: "LOCNUMEND", 0x7F: "LOCSTREND",
    0x9E: "IACC", 0xAF: "FORPOP",
}

# RUNTIME entry points seen in compiled code (2.01, library at $0803).  Names are
# provisional, from the statement that calls them (Phase 1); "/I" = integer entry,
# which for statement pairs sits 3 bytes from the real entry.
RUNTIME: dict[int, str] = {
    0x08A7: "RT.CLEARCOMMON", 0x0F0B: "RT.CLEARCHAIN", 0x1423: "RT.DEBUG", 0x1656: "RT.RESUME",
    0x09E1: "RT.IFOR.INIT", 0x09DE: "RT.IFOR.INIT/R", 0x1691: "RT.IFOR.LIMIT", 0x168E: "RT.IFOR.LIMIT/R",
    0x168A: "RT.IFOR.STEP", 0x1687: "RT.IFOR.STEP/R", 0x167E: "RT.IFOR.STEP1", 0x165F: "RT.PUSH.SUBSCRIPT/I",
    0x1675: "RT.IMOVE", 0x10DF: "RT.CONCAT.T", 0x1549: "RT.STRGT", 0x1546: "RT.STRLE", 0x152F: "RT.STRGE",
    0x1298: "RT.INPUT.STR.NEXT", 0x128A: "RT.INPUT.STR.PROMPT", 0x096C: "RT.CHRGET.PATCH(data)",
    0x08AA: "RT.CLEAR", 0x08DB: "RT.HIMEM", 0x0963: "RT.RESTORE", 0x097B: "RT.POP",
    0x09E5: "RT.FOR.INIT/I", 0x09E8: "RT.FOR.INIT", 0x0A31: "RT.NEXT",
    0x0B11: "RT.ARR.REAL", 0x0B14: "RT.ARR.STR", 0x0B17: "RT.ARR.INT", 0x0C6F: "RT.ARR.STORE",
    0x0DD9: "RT.DRAW.AT", 0x0DE0: "RT.XDRAW.AT", 0x0DED: "RT.HPLOT.TO", 0x0DF4: "RT.HPLOT",
    0x0E34: "RT.DRAW", 0x0E3B: "RT.XDRAW", 0x0E77: "RT.COLOR", 0x0E7A: "RT.COLOR/I", 0x0E80: "RT.VAL",
    0x0EAA: "RT.ASC", 0x0EB6: "RT.LEN", 0x0EC2: "RT.STRLIT.PROMPT", 0x0F13: "RT.FRE",
    0x10CC: "RT.GET.STR", 0x10EF: "RT.CONCAT", 0x1135: "RT.PUSHSTR", 0x1192: "RT.CHR", 0x1195: "RT.CHR/I",
    0x11A9: "RT.STR", 0x11C4: "RT.LEFT", 0x11F2: "RT.RIGHT", 0x1227: "RT.MID2", 0x1231: "RT.MID3",
    0x1287: "RT.INPUT.STR", 0x12FD: "RT.INPUT.NUM", 0x1300: "RT.INPUT.NUM.PROMPT", 0x1312: "RT.INPUT.NUM.NEXT",
    0x134B: "RT.STOP", 0x1387: "RT.INPUT.END", 0x1399: "RT.GET.NUM", 0x13A9: "RT.READ.STR", 0x13AC: "RT.READ.NUM",
    0x143F: "RT.PR#", 0x1448: "RT.IN#", 0x1451: "RT.POKE.VAL", 0x1454: "RT.POKE.VAL/I", 0x145A: "RT.WAIT2",
    0x1466: "RT.WAIT3", 0x146F: "RT.TAB", 0x147F: "RT.SPC", 0x148E: "RT.COMMA", 0x149E: "RT.VTAB", 0x14A1: "RT.VTAB/I",
    0x14A7: "RT.HTAB", 0x14B0: "RT.ONGOTO", 0x14B7: "RT.ONGOSUB", 0x14FD: "RT.OR/I", 0x1503: "RT.AND/I",
    0x150B: "RT.OR", 0x1511: "RT.AND", 0x1517: "RT.NE", 0x1519: "RT.GT", 0x151B: "RT.GE", 0x1524: "RT.EQ",
    0x1526: "RT.LE", 0x1528: "RT.LT", 0x1532: "RT.STRLT", 0x1582: "RT.STREQ", 0x15B7: "RT.STRNE",
    0x15BB: "RT.ROT", 0x15C4: "RT.SCALE", 0x15CD: "RT.SAVE.SHAPE", 0x15D6: "RT.SAVE.ARG3", 0x15DF: "RT.PUSH.BYTE",
    0x15E8: "RT.SAVE.HX", 0x15F4: "RT.HCOLOR", 0x15FD: "RT.SAVE.X", 0x1600: "RT.SAVE.X/I", 0x1608: "RT.SAVE.Y",
    0x161E: "RT.SPEED", 0x1627: "RT.INPUT.BEGIN", 0x1637: "RT.ONERR", 0x165C: "RT.PUSH.SUBSCRIPT",
    0x166E: "RT.FLOAT.IACC", 0x16AC: "RT.FOR.STEP1", 0x16B5: "RT.FOR.STEP/I", 0x16B8: "RT.FOR.STEP",
    0x16BC: "RT.FOR.LIMIT/I", 0x16BF: "RT.FOR.LIMIT", 0x16EB: "RT.SCRN", 0x1700: "RT.POS", 0x170A: "RT.PLOT",
    0x170D: "RT.PLOT/I", 0x1716: "RT.HLIN", 0x1722: "RT.VLIN", 0x172B: "RT.PDL", 0x173B: "RT.CALL",
    0x173E: "RT.SAVE.ADDR/I", 0x1741: "RT.SAVE.ADDR", 0x1744: "RT.PEEK/I", 0x1747: "RT.PEEK", 0x175E: "RT.PRINTINT",
    0x0803: "RT.INIT",
    0x1363: "RT.END",
    0x1764: "RT.DISP.REAL",  # per-variable dispatcher, real
    0x0D06: "RT.DISP.INT",  # per-variable dispatcher, integer
    0x0C7F: "RT.DISP.STR",  # per-variable dispatcher, string (C=1 load, C=0 store)
    0x1761: "RT.PRINTNUM",
    0x0EC5: "RT.STRLIT",  # inline 2-byte pointer to [len][text]
    0x0EEE: "RT.PRINTSTR",
    0x0CC3: "RT.INEG", 0x0CDA: "RT.ISUBT",
}

# Routines that read inline operand bytes after the JSR: address -> byte count
INLINE_OPERANDS: dict[int, int] = {
    0x0EC5: 2,  # string literal
    0x0EC2: 2,  # string literal (INPUT prompt)
    0x1637: 2,  # ONERR GOTO: handler address
    0x09E5: 2,  # FOR, int initial value: &loop variable
    0x09E8: 2,  # FOR, real initial value
    0x0A31: 2,  # NEXT: &loop variable
}

DISPATCHERS: dict[int, str] = {0x1764: "real", 0x0D06: "int", 0x0C7F: "str"}


def all_names(delta: int = 0) -> dict[int, str]:
    """ROM and RUNTIME names; delta = library address - $0803 (RUNTIME relocated)."""
    d: dict[int, str] = {}
    d.update(ROM)
    d.update({a + delta: n for a, n in RUNTIME.items()})
    return d
''', False)


# ============================================================================
# module tasc.objfile
# ============================================================================
_MODULES['tasc.objfile'] = (r'''"""Parse a TASC object file into header, code, constants and variable routines.

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
''', False)


# ============================================================================
# module tasc.compiler (package)
# ============================================================================
_MODULES['tasc.compiler'] = (r'''''', True)


# ============================================================================
# module tasc.compiler.fp
# ============================================================================
_MODULES['tasc.compiler.fp'] = (r'''"""Applesoft 5-byte packed floating point.

Format: exponent byte (bias 128, 0 = zero), then 4 mantissa bytes big-endian
with the implied leading 1 replaced by the sign bit.  Value = 0.1mmm... (binary)
* 2^(exp-128).

pack_decimal() rounds the exact decimal value to nearest (ties away from zero).
Whether that matches the ROM's FIN for every literal is checked against TASC
output in tests; FIN accumulates digits in FAC, so it can differ in the last bit.
"""

from __future__ import annotations

from fractions import Fraction


def pack_fraction(v: Fraction) -> bytes:
    if v == 0:
        return bytes(5)
    neg = v < 0
    a = -v if neg else v
    exp = 0
    # normalise a into [1/2, 1)
    while a >= 1:
        a /= 2
        exp += 1
    while a < Fraction(1, 2):
        a *= 2
        exp -= 1
    m = a * (1 << 32)
    mi = int(m)
    if m - mi >= Fraction(1, 2):
        mi += 1
    if mi == 1 << 32:  # rounding overflowed
        mi >>= 1
        exp += 1
    e = exp + 128
    if not 1 <= e <= 255:
        raise OverflowError(f"value {v} out of Applesoft range")
    b = mi.to_bytes(4, "big")
    first = (b[0] & 0x7F) | (0x80 if neg else 0)
    return bytes([e, first]) + b[1:]


def pack_decimal(text: str) -> bytes:
    """Pack a numeric literal as written (e.g. '1.5', '.001', '1E10')."""
    t = text.upper()
    mant, _, ex = t.partition("E")
    if mant in ("", "."):
        mant = "0"
    v = Fraction(mant if not mant.endswith(".") else mant[:-1] or "0")
    if ex:
        v *= Fraction(10) ** int(ex)
    return pack_fraction(v)


def literal_value(text: str) -> Fraction:
    t = text.upper()
    mant, _, ex = t.partition("E")
    if mant in ("", "."):
        mant = "0"
    v = Fraction(mant if not mant.endswith(".") else mant[:-1] or "0")
    if ex:
        v *= Fraction(10) ** int(ex)
    return v


def unpack(raw: bytes) -> float:
    if raw[0] == 0:
        return 0.0
    m = int.from_bytes(bytes([raw[1] | 0x80]) + raw[2:5], "big")
    v = m / 2.0**32 * 2.0 ** (raw[0] - 128)
    return -v if raw[1] & 0x80 else v
''', False)


# ============================================================================
# module tasc.compiler.fin
# ============================================================================
_MODULES['tasc.compiler.fin'] = (r'''"""Bit-exact translation of the Applesoft ROM number input (FIN, $EC4A) and the
floating-point routines it uses.

TASC packs numeric constants as the ROM does (verified: 3.14159 -> 82 49 0F CF 82,
one ulp above the correctly rounded value).  Each routine below follows the ROM
listing instruction by instruction (labels from Bob Sander-Cederlof's commented
source), operating on a zero-page model, so rounding behaves exactly as on the
Apple II.
"""

from __future__ import annotations

FAC, ARG = 0x9D, 0xA5  # exponent, mantissa 1..4, sign
FAC_EXT, ARG_EXT, SGNCPR, SHIFT_SIGN_EXT = 0xAC, 0x92, 0xAB, 0xA4
RESULT = 0x62
TMPEXP, EXPON, DPFLG, EXPSGN, SERLEN = 0x99, 0x9A, 0x9B, 0x9C, 0xA3


class FPError(Exception):
    pass


class FP:
    def __init__(self) -> None:
        self.m = bytearray(256)
        self.a = self.x = self.y = 0
        self.c = False

    # -- 6502 helpers --------------------------------------------------
    def adc(self, v: int) -> int:
        r = self.a + v + (1 if self.c else 0)
        self.c = r > 0xFF
        self.a = r & 0xFF
        return self.a

    def sbc(self, v: int) -> int:
        r = self.a - v - (0 if self.c else 1)
        self.c = r >= 0
        self.a = r & 0xFF
        return self.a

    def rol(self, addr: int) -> int:
        v = (self.m[addr] << 1) | (1 if self.c else 0)
        self.c = v > 0xFF
        self.m[addr] = v & 0xFF
        return self.m[addr]

    def ror(self, addr: int) -> int:
        v = self.m[addr] | (0x100 if self.c else 0)
        self.c = bool(v & 1)
        self.m[addr] = v >> 1
        return self.m[addr]

    def asl(self, addr: int) -> int:
        v = self.m[addr] << 1
        self.c = v > 0xFF
        self.m[addr] = v & 0xFF
        return self.m[addr]

    def lsr(self, addr: int) -> int:
        v = self.m[addr]
        self.c = bool(v & 1)
        self.m[addr] = v >> 1
        return self.m[addr]

    # -- FADD family ($E7C1) -----------------------------------------------
    def faddt(self) -> None:
        """FAC = ARG + FAC; caller set SGNCPR; entered with Z from FAC exponent."""
        if self.m[FAC] == 0:
            self.copy_arg_to_fac()
            return
        self.m[ARG_EXT] = self.m[FAC_EXT]
        self.x = ARG
        self.a = self.m[ARG]
        self.fadd_2()

    def fadd_2(self) -> None:
        self.y = self.a
        if self.y == 0:
            return  # RTS.10: ARG = 0
        self.c = True
        self.sbc(self.m[FAC])
        if self.a == 0:
            self.fadd_3()
            return
        if not self.c:  # ARG has the smaller exponent
            self.y = 0
            self.m[FAC_EXT] = 0
        else:  # FAC has the smaller exponent
            self.m[FAC] = self.y
            self.m[FAC + 5] = self.m[ARG + 5]  # sign
            self.a ^= 0xFF
            self.adc(0)  # carry was set
            self.y = 0
            self.m[ARG_EXT] = 0
            self.x = FAC
        # .2: CMP #$F9 / BMI FADD.1 (more than 7 bits to shift)
        self.c = self.a >= 0xF9
        if (self.a - 0xF9) & 0x80:
            self.shift_right()  # FADD.1
            self.fadd_3()
            return
        self.y = self.a
        self.a = self.m[FAC_EXT]
        self.lsr(self.x + 1)
        self.shift_right_4()
        self.fadd_3()

    @staticmethod
    def _signed(v: int) -> int:
        return v - 256 if v & 0x80 else v

    def fadd_3(self) -> None:
        if not (self.m[SGNCPR] & 0x80):  # BIT SGNCPR / BPL: same signs
            self.fadd_4()
            return
        yreg = FAC if self.x == ARG else ARG  # subtract the unadjusted one minus the adjusted one
        self.c = True
        self.a ^= 0xFF
        self.adc(self.m[ARG_EXT])
        self.m[FAC_EXT] = self.a
        for i in (4, 3, 2, 1):
            self.a = self.m[yreg + i]
            self.sbc(self.m[self.x + i])
            self.m[FAC + i] = self.a
        self.normalize_fac_1()

    def fadd_4(self) -> None:
        self.adc(self.m[ARG_EXT])
        self.m[FAC_EXT] = self.a
        for i in (4, 3, 2, 1):
            self.a = self.m[FAC + i]
            self.adc(self.m[ARG + i])
            self.m[FAC + i] = self.a
        self.normalize_fac_5()

    # -- normalize ($E829) ------------------------------------------------
    def normalize_fac_1(self) -> None:
        if not self.c:
            self.complement_fac()
        self.normalize_fac_2()

    def normalize_fac_2(self) -> None:
        self.y = 0
        self.a = 0
        self.c = False
        while True:
            if self.m[FAC + 1] != 0:
                self.normalize_fac_4()
                return
            self.m[FAC + 1] = self.m[FAC + 2]
            self.m[FAC + 2] = self.m[FAC + 3]
            self.m[FAC + 3] = self.m[FAC + 4]
            self.m[FAC + 4] = self.m[FAC_EXT]
            self.m[FAC_EXT] = 0
            self.adc(8)
            if self.a == 32:
                self.zero_fac()
                return

    def zero_fac(self) -> None:
        self.m[FAC] = 0
        self.m[FAC + 5] = 0

    def normalize_fac_4(self) -> None:
        # loop: NORMALIZE.FAC.3 / .4 with X = FAC+1 tested via N flag of last op
        n = self.m[FAC + 1] & 0x80
        while not n:
            self.adc(1)
            self.asl(FAC_EXT)
            self.rol(FAC + 4)
            self.rol(FAC + 3)
            self.rol(FAC + 2)
            n = self.rol(FAC + 1) & 0x80
        self.c = True
        self.sbc(self.m[FAC])
        if self.c:
            self.zero_fac()  # underflow
            return
        self.a ^= 0xFF
        self.adc(1)
        self.m[FAC] = self.a
        self.normalize_fac_5()

    def normalize_fac_5(self) -> None:
        if not self.c:
            return
        self.normalize_fac_6()

    def normalize_fac_6(self) -> None:
        self.m[FAC] = (self.m[FAC] + 1) & 0xFF
        if self.m[FAC] == 0:
            raise FPError("OVERFLOW")
        for addr in (FAC + 1, FAC + 2, FAC + 3, FAC + 4, FAC_EXT):
            self.ror(addr)

    def complement_fac(self) -> None:
        self.m[FAC + 5] ^= 0xFF
        self.complement_fac_mantissa()

    def complement_fac_mantissa(self) -> None:
        for addr in (FAC + 1, FAC + 2, FAC + 3, FAC + 4, FAC_EXT):
            self.m[addr] ^= 0xFF
        self.m[FAC_EXT] = (self.m[FAC_EXT] + 1) & 0xFF
        if self.m[FAC_EXT] != 0:
            return
        self.increment_fac_mantissa()

    def increment_fac_mantissa(self) -> int:
        """Returns the last incremented byte (for the BNE that follows)."""
        for addr in (FAC + 4, FAC + 3, FAC + 2):
            self.m[addr] = (self.m[addr] + 1) & 0xFF
            if self.m[addr] != 0:
                return self.m[addr]
        self.m[FAC + 1] = (self.m[FAC + 1] + 1) & 0xFF
        return self.m[FAC + 1]

    # -- shifter ($E8DA) ----------------------------------------------------
    def shift_right(self) -> None:
        """SHIFT.RIGHT: A = negative shift count, X = base, carry as left by the caller.
        Returns extension bits in A, C=0."""
        while True:
            self.adc(8)
            if self.a & 0x80 or self.a == 0:  # BMI / BEQ SHIFT.RIGHT.2 (then falls back here)
                self.shift_right_2()
                continue
            break
        self.sbc(8)  # undo the ADC (carry from the ADC is significant)
        self.y = self.a
        self.a = self.m[FAC_EXT]
        if self.c:  # BCS SHIFT.RIGHT.5
            self.c = False
            return
        self._shift_right_3_loop()

    def shift_right_2(self) -> None:
        x = self.x
        self.m[FAC_EXT] = self.m[x + 4]
        self.m[x + 4] = self.m[x + 3]
        self.m[x + 3] = self.m[x + 2]
        self.m[x + 2] = self.m[x + 1]
        self.m[x + 1] = self.m[SHIFT_SIGN_EXT]

    def _shift_right_3_loop(self) -> None:
        while self.y != 0:
            x = self.x
            self.asl(x + 1)
            if self.c:
                self.m[x + 1] = (self.m[x + 1] + 1) & 0xFF
            self.ror(x + 1)
            self.ror(x + 1)
            self.ror(x + 2)
            self.ror(x + 3)
            self.ror(x + 4)
            self._ror_a()
            self.y = (self.y + 1) & 0xFF
        self.c = False

    def _ror_a(self) -> None:
        v = self.a | (0x100 if self.c else 0)
        self.c = bool(v & 1)
        self.a = v >> 1

    def shift_right_4(self) -> None:
        """Entry with the first ROR of byte 1 already done (Y = negative count)."""
        x = self.x
        self.ror(x + 2)
        self.ror(x + 3)
        self.ror(x + 4)
        self._ror_a()
        self.y = (self.y + 1) & 0xFF
        self._shift_right_3_loop()

    # -- moves and rounding ($EB2B..$EB7F) ------------------------------------
    def round_fac(self) -> None:
        if self.m[FAC] == 0:
            return
        self.asl(FAC_EXT)
        if not self.c:
            return
        if self.increment_fac_mantissa() != 0:
            return
        self.normalize_fac_6()

    def copy_fac_to_arg_rounded(self) -> None:
        self.round_fac()
        for i in range(6):
            self.m[ARG + i] = self.m[FAC + i]
        self.m[FAC_EXT] = 0
        self.a = self.m[FAC]  # last byte copied is FAC exponent (LDA FAC-1+1)

    def copy_arg_to_fac(self) -> None:
        for i in range(6):
            self.m[FAC + i] = self.m[ARG + i]
        self.m[FAC_EXT] = 0

    def load_fac(self, packed: bytes) -> None:
        self.m[FAC + 4] = packed[4]
        self.m[FAC + 3] = packed[3]
        self.m[FAC + 2] = packed[2]
        self.m[FAC + 5] = packed[1]
        self.m[FAC + 1] = packed[1] | 0x80
        self.m[FAC] = packed[0]
        self.m[FAC_EXT] = 0

    def packed(self) -> bytes:
        """STORE.FAC.AT.YX.ROUNDED."""
        self.round_fac()
        out = bytes([self.m[FAC], (self.m[FAC + 5] | 0x7F) & self.m[FAC + 1], self.m[FAC + 2], self.m[FAC + 3],
                     self.m[FAC + 4]])
        self.m[FAC_EXT] = 0
        return out

    def float_a(self, v: int) -> None:
        """FLOAT: signed byte in A -> FAC."""
        self.m[FAC + 1] = v
        self.m[FAC + 2] = 0
        self.x = 0x88
        self.a = self.m[FAC + 1] ^ 0xFF
        self.c = bool(self.a & 0x80)  # ROL: carry <- bit 7
        self.a = ((self.a << 1) & 0xFF)
        self.m[FAC + 4] = 0
        self.m[FAC + 3] = 0
        self.m[FAC] = self.x
        self.m[FAC_EXT] = 0
        self.m[FAC + 5] = 0
        self.normalize_fac_1()

    # -- multiply/divide by ten ($EA39, $EA55) -------------------------------
    def mul10(self) -> None:
        self.copy_fac_to_arg_rounded()
        if self.a == 0:
            return
        self.c = False
        self.adc(2)
        if self.c:
            raise FPError("OVERFLOW")
        self.m[SGNCPR] = 0
        self.fadd_2()  # A = exponent+2 -> FAC*5 (ARG*4 + FAC)
        self.m[FAC] = (self.m[FAC] + 1) & 0xFF
        if self.m[FAC] == 0:
            raise FPError("OVERFLOW")

    def div10(self) -> None:
        self.copy_fac_to_arg_rounded()
        self.m[SGNCPR] = 0
        self.load_fac(bytes([0x84, 0x20, 0, 0, 0]))
        self.fdivt()

    def add_exponents(self) -> None:
        self.a = self.m[ARG]
        if self.a == 0:
            self.zero_fac()
            raise _Zero()
        self.c = False
        self.adc(self.m[FAC])
        if self.c:
            if self.a & 0x80:
                raise FPError("OVERFLOW")
            self.c = False
            # skip the BPL ZERO
        else:
            if not (self.a & 0x80):
                self.zero_fac()
                raise _Zero()
        self.adc(0x80)
        self.m[FAC] = self.a
        if self.a == 0:
            self.m[FAC + 5] = 0
            return
        self.m[FAC + 5] = self.m[SGNCPR]

    def fdivt(self) -> None:
        if self.m[FAC] == 0:
            raise FPError("DIVISION BY ZERO")
        self.round_fac()
        self.a = 0
        self.c = True
        self.sbc(self.m[FAC])
        self.m[FAC] = self.a
        try:
            self.add_exponents()
        except _Zero:
            return
        self.m[FAC] = (self.m[FAC] + 1) & 0xFF
        if self.m[FAC] == 0:
            raise FPError("OVERFLOW")
        x = -4
        a = 1  # sentinel
        state = "cmp"  # label .1
        res = [0, 0, 0, 0]
        while True:
            if state == "cmp":
                ge = True
                for i in (1, 2, 3, 4):
                    if self.m[ARG + i] != self.m[FAC + i]:
                        ge = self.m[ARG + i] > self.m[FAC + i]
                        break
                c_cmp = ge
                state = "roll"
            if state == "roll":  # .2 : PHP / ROL
                saved = c_cmp
                v = (a << 1) | (1 if c_cmp else 0)
                carry_out = v > 0xFF
                a = v & 0xFF
                if carry_out:
                    x += 1
                    if x <= 0:
                        res[x + 3] = a  # STA RESULT+3,X
                    if x == 0:
                        a = 0x40  # .6: a few extension bits
                        c_cmp = saved
                        # fall to .3 with the saved compare
                    elif x > 0:  # .7 final exit (X=1)
                        a = (a << 6) & 0xFF
                        self.m[FAC_EXT] = a
                        for i in range(4):
                            self.m[FAC + 1 + i] = res[i]
                        self.normalize_fac_2()
                        return
                    else:
                        a = 1
                # .3: PLP -> carry = saved compare
                if saved:  # .5: subtract FAC from ARG
                    self.c = True
                    for i in (4, 3, 2, 1):
                        self.a = self.m[ARG + i]
                        self.sbc(self.m[FAC + i])
                        self.m[ARG + i] = self.a
                # .4: shift ARG left
                self.c = False
                self.asl(ARG + 4)
                self.rol(ARG + 3)
                self.rol(ARG + 2)
                top = self.rol(ARG + 1)
                if self.c:
                    c_cmp = True
                    state = "roll"
                elif top & 0x80:
                    state = "cmp"
                else:
                    c_cmp = False
                    state = "roll"


class _Zero(Exception):
    pass


def fin(text: str) -> bytes:
    """Convert a numeric literal as typed (digits, '.', E, exponent sign) to packed
    bytes exactly as the ROM's FIN + STORE.FAC.AT.YX.ROUNDED would."""
    f = FP()
    s = text.upper()
    i = 0
    tmpexp = expon = 0
    dpflg = False
    expneg = False

    def addacc(d: int) -> None:
        f.copy_fac_to_arg_rounded()
        f.float_a(d)
        f.m[SGNCPR] = f.m[ARG + 5] ^ f.m[FAC + 5]
        f.faddt()

    while i < len(s):
        ch = s[i]
        if ch.isdigit():
            if dpflg:
                tmpexp += 1
            f.mul10()
            addacc(int(ch))
            i += 1
            continue
        if ch == ".":
            if dpflg:
                break
            dpflg = True
            i += 1
            continue
        if ch == "E":
            i += 1
            if i < len(s) and s[i] in "+-":
                expneg = s[i] == "-"
                i += 1
            while i < len(s) and s[i].isdigit():
                if expon >= 10:  # GETEXP: more than two digits
                    if expneg:
                        expon = 100
                    else:
                        raise FPError("OVERFLOW")
                else:
                    expon = (expon * 10 + int(s[i])) & 0xFF
                i += 1
            break
        break
    e = ((-expon if expneg else expon) - tmpexp) & 0xFF  # EXPON is one byte
    if e & 0x80:
        for _ in range(256 - e):
            f.div10()
    else:
        for _ in range(e):
            f.mul10()
    return f.packed()
''', False)


# ============================================================================
# module tasc.compiler.parse
# ============================================================================
_MODULES['tasc.compiler.parse'] = (r'''"""Applesoft program reader and parser (tokenized bytes -> AST).

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
''', False)


# ============================================================================
# module tasc.compiler.codegen
# ============================================================================
_MODULES['tasc.compiler.codegen'] = (r'''"""TASC code generation (Phase 1 predictor; seed of the Python compiler).

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
from tasc.options import Options

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
''', False)


# ============================================================================
# module tasc.compiler.assemble
# ============================================================================
_MODULES['tasc.compiler.assemble'] = (r'''"""Lay out and assemble a compiled program into TASC object file bytes."""

from __future__ import annotations

from dataclasses import dataclass

from tasc.compiler.codegen import RT_RANGE, Compiler, CompileError, Item, Ref, Sym, parse_program
from tasc.options import Options

LIB_SIZE = 4013  # RUNTIME 2.01
DISP = {"real": 0x1764, "int": 0x0D06, "str": 0x0C7F}
ARR_DISP = {"real": 0x0B11, "str": 0x0B14, "int": 0x0B17}


@dataclass
class Result:
    load: int
    data: bytes
    line_addr: dict[int, int]
    compiler: Compiler


def _symbol_order(syms: list[Sym]) -> list[Sym]:
    return sorted(syms, key=lambda s: (s.bucket, s.seq))


def assemble(c: Compiler, opts: Options) -> Result:
    lib = opts.library if isinstance(opts.library, int) else 0x0803
    delta = lib - 0x0803
    if isinstance(opts.program, int):
        prog_start = opts.program
    elif opts.program == "HGR1":
        prog_start = 0x4000
    elif opts.program == "HGR2":
        prog_start = 0x6000
    else:
        prog_start = lib + LIB_SIZE

    # COMMON block at program start: numeric then string, declaration order
    a = prog_start
    for s in c.common:
        if s.vtype != "str":
            s.addr, a = a, a + s.size()
    numcomend = a - 1
    for s in c.common:
        if s.vtype == "str":
            s.addr, a = a, a + s.size()
    strcomend = a - 1
    load = a

    # code addresses
    pc = load + 20
    labels: dict[str, int] = {}
    line_addr: dict[int, int] = {}
    pending_lines: list[int] = []
    for it in c.items:
        if it.line is not None:
            pending_lines.append(it.line)
            continue
        if it.label is not None:
            labels[it.label] = pc
            continue
        for ln in pending_lines:
            line_addr[ln] = pc
        pending_lines = []
        pc += it.size()
    for ln in pending_lines:
        line_addr[ln] = pc
    code_end = pc
    if c.common_last_line is not None:
        # observed (manual 8.2.4): lines up to the last COMMON declaration keep the address
        # the code had before COMMON moved it up, i.e. a jump there lands in the COMMON block
        for ln in list(line_addr):
            if 0 <= ln <= c.common_last_line:
                line_addr[ln] = prog_start + 20

    # constant pool
    # PASS2 505-515 (confirmed p3_rand5): a real constant is written to the pool before the
    # "never referenced -> unlink" test, so only unreferenced integer constants are dropped
    consts = _symbol_order([k for k in c.consts.values() if k.ops or k.used or k.vtype == "real"])
    for k in consts:
        k.addr, pc = pc, pc + len(k.raw)

    # symbols: temps, FN params, named variables
    temps = [t for vt in ("int", "real") for t in c.temps[vt]]  # observed in BALL: int temp before real temp
    # observed (PASS1): FN parameters and FN-body temps share one list in creation order
    # (main temps: int first)
    fn_syms = sorted(c.params + [t for vt in ("real", "int") for t in c.fn_temps[vt]], key=lambda t: t.seq)
    stemps = c.temps["str"]
    named = list(c.syms.values())
    num_scalars = _symbol_order([s for s in named if not s.array and s.vtype != "str"])
    num_arrays = _symbol_order([s for s in named if s.array and s.vtype != "str"])
    # observed: string scalars and string arrays share one hash order (numerics are grouped)
    strings = _symbol_order([s for s in named if s.vtype == "str"])

    # routines: numeric (temps, params, scalars), constants, strings, arrays   (order partly GUESS)
    # observed: numeric scalars, constants, numeric arrays, string scalars, string arrays
    # (arrays always get a routine)
    rtn_order = ([s for s in temps + fn_syms + num_scalars if s.ops] + [k for k in consts if k.ops] + num_arrays
                 # PASS2 pass 3 (lines 845-1350, 1105): every string symbol gets a routine,
                 # used or not (confirmed p3_lift fre_str, pos_str)
                 + stemps + c.fn_temps["str"] + strings)
    entry: dict[tuple[int, int], int] = {}
    for s in rtn_order:
        s.rtn = pc
        if s.array:
            entry[(id(s), 0)], entry[(id(s), 1)] = pc, pc + 2
            pc += 9 + 2 * len(s.dims)
        elif s.vtype == "str":
            entry[(id(s), 0)], entry[(id(s), 1)] = pc, pc + 2
            pc += 10
        else:
            for i, op in enumerate(sorted(s.ops, reverse=True)):
                entry[(id(s), op)] = pc + 3 * i
            pc += 3 * len(s.ops) + 6
    obj_end = pc

    # local variables
    var_start = opts.variables if isinstance(opts.variables, int) else obj_end
    a = var_start
    for s in temps + fn_syms + [s for s in num_scalars + num_arrays if s.common is None]:
        s.addr, a = a, a + s.size()
    locnumend = a - 1
    for s in stemps + c.fn_temps["str"] + [s for s in strings if s.common is None]:
        s.addr, a = a, a + s.size()
    locstrend = a - 1

    # data block chain
    data_first = [labels[f] for f in c.data_blocks]

    def resolve(ref: Ref) -> int:
        if ref.kind == "abs":
            return int(ref.a)  # type: ignore[arg-type]
        if ref.kind == "rt":
            v = int(ref.a)  # type: ignore[arg-type]
            if not (RT_RANGE[0] <= v < RT_RANGE[1]):
                raise CompileError(f"RUNTIME address out of range {v:04X}")
            return v + delta
        if ref.kind == "entry":
            s = ref.a
            assert isinstance(s, Sym)
            return entry[(id(s), ref.b)]
        if ref.kind == "line":
            n = int(ref.a)  # type: ignore[arg-type]
            if n not in line_addr:
                raise CompileError(f"undefined line {n}")
            return line_addr[n]
        if ref.kind == "label":
            return labels[str(ref.a)]
        if ref.kind == "store":
            s = ref.a
            assert isinstance(s, Sym)
            return s.addr + ref.b
        if ref.kind == "datalink":
            i = int(ref.a)  # type: ignore[arg-type]
            return data_first[i + 1] if i + 1 < len(data_first) else 0
        raise CompileError(f"ref {ref.kind}")

    out = bytearray()
    for it in c.items:
        if it.op is not None:
            assert it.ref is not None
            v = resolve(it.ref)
            out += bytes([it.op, v & 0xFF, v >> 8])
        elif it.word:
            assert it.ref is not None
            v = resolve(it.ref)
            out += bytes([v & 0xFF, v >> 8])
        else:
            out += it.raw
    for k in consts:
        out += k.raw
    for s in rtn_order:
        if s.array:
            disp = ARR_DISP[s.vtype] + delta
            out += bytes([0x38, 0xA9, 0x18, 0x20, disp & 0xFF, disp >> 8, s.addr & 0xFF, s.addr >> 8, len(s.dims)])
            for d in reversed(s.dims):  # observed: rightmost subscript first
                out += bytes([d & 0xFF, d >> 8])
        elif s.vtype == "str":
            disp = DISP["str"] + delta
            out += bytes([0x38, 0xA9, 0x18, 0xA0, s.addr >> 8, 0xA9, s.addr & 0xFF, 0x4C, disp & 0xFF, disp >> 8])
        else:
            ops = sorted(s.ops, reverse=True)
            for op in ops[:-1]:
                out += bytes([0xA2, op, 0xAD])
            disp = DISP[s.vtype] + delta
            out += bytes([0xA2, ops[-1], 0xA0, s.addr >> 8, 0xA9, s.addr & 0xFF, 0x4C, disp & 0xFF, disp >> 8])

    locbeg1 = var_start - 1
    highest = max(obj_end - 1, locstrend, strcomend)
    comb1 = prog_start - 1
    hdr = [data_first[0] if data_first else 0, highest, comb1, numcomend, strcomend, locbeg1, locnumend, locstrend]
    head = bytearray([0x20, lib & 0xFF, lib >> 8])
    for w in hdr:
        head += bytes([w & 0xFF, w >> 8])
    head.append(c.common_flag)
    data = bytes(head) + bytes(out)
    if len(data) != obj_end - load:
        raise CompileError(f"size mismatch {len(data)} vs {obj_end - load}")
    return Result(load, data, line_addr, c)


def compile_program(program: bytes, opts: Options | None = None) -> Result:
    opts = opts or Options()
    c = Compiler(opts)
    c.compile_lines(parse_program(program))
    return assemble(c, opts)
''', False)


# ============================================================================
# module tasc.decomp (package)
# ============================================================================
_MODULES['tasc.decomp'] = (r'''''', True)


# ============================================================================
# module tasc.decomp.walk
# ============================================================================
_MODULES['tasc.decomp.walk'] = (r'''"""Decompiler front end, step 1: walk a TASC object file into semantic ops.

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
    accepted: set[int] = set()  # unreferenced literals that are real (a FRE/POS literal argument)
    w = _walk(data, load, forced)
    while True:
        refs = {o.words[0] for o in w.ops if o.kind == "rt" and o.name in ("STRLIT", "STRLIT.PROMPT")}
        bad = {o.addr for o in w.ops if o.kind == "lit" and o.addr + 3 not in refs and o.addr not in accepted}
        chain = _data_chain(data, load)
        bad |= {o.addr for o in w.ops if o.kind == "data" and o.addr + 3 not in chain}
        if not bad:
            return w
        a = min(bad)
        try:
            w = _walk(data, load, forced | {a})
            forced.add(a)
        except WalkError:
            accepted.add(a)  # as a jump the bytes do not decode: keep the literal


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
                after_branch = bool(ops) and ops[-1].kind in ("bne3", "beq3")  # IF: always a jump
                if not jsr and t > a + 3 and a not in forced and not after_branch:
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
        elif ops and ops[-1].kind == "end":
            # the appended final JMP END: the constant pool may start with real constants that
            # nothing references (PASS2 keeps them), so no routine marks the pool's start
            end = a
            obj.code_end = a
            break
        else:
            raise WalkError(f"${a:04X}: unexpected byte ${b:02X}")
    # ORA marks an integer operand
    for k, o in enumerate(ops):
        if o.kind == "ora" and o.sym is not None and o.target == o.sym.addr + 1:
            o.sym.vtype = "int" if o.sym.vtype == "real" and o.sym.routine is None else o.sym.vtype
            if o.sym.region == "const" and not o.sym.routine:
                o.sym.const = data[o.sym.addr - load : o.sym.addr - load + 2]
    # pool gaps: unreferenced real constants (5 bytes each; unreferenced ints are dropped)
    rstart = obj.routines[0].addr if obj.routines else load + len(data)
    known = sorted(x.addr for x in syms.values() if x.region == "const")
    pos = obj.code_end
    for ka in known + [rstart]:
        while pos < ka:
            if pos + 5 > ka:
                raise WalkError(f"constant pool gap ${pos:04X}-${ka - 1:04X}")
            k = Sym(pos, "real", region="const", kind="const", const=data[pos - load : pos - load + 5])
            syms[pos] = k
            pos += 5
        if ka in syms:
            pos = ka + len(syms[ka].const)
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
''', False)


# ============================================================================
# module tasc.decomp.lift
# ============================================================================
_MODULES['tasc.decomp.lift'] = (r'''"""Decompiler step 2: abstract interpretation of the op stream into statements.

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
    addr: int = 0  # address of the FRE/POS call
    lit: bytes | None = None  # a string literal argument (its data emitted at scan time)


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
    free_lits: list[Op] = field(default_factory=list)  # literal data no STRLIT uses (FRE/POS argument)
    fre_decisions: list[int] = field(default_factory=list)  # FRE/POS that took a pending string


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
        self.fre_choice: dict[int, bool] = {}
        # string temp stores that are FRE/POS's own (unconsumed) argument: FRE/POS follows and
        # the temp is not read before it is written again
        self.fre_spills: set[int] = set()
        ops = w.ops
        for k, o in enumerate(ops[:-1]):
            if (o.kind == "ent" and o.op == 1 and o.sym in temps and o.sym.vtype == "str"
                    and ops[k + 1].kind == "rt" and ops[k + 1].name in ("FRE", "POS")):
                nxt = next((x for x in ops[k + 1:] if x.sym is o.sym), None)
                if nxt is None or (nxt.kind == "ent" and nxt.op == 1):
                    self.fre_spills.add(o.addr)
        self.fre_decisions: list[int] = []
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
        self.last_val = ""  # what the previous op produced: num / stack / load / spill / ''
        self.spilled: Node | None = None
        self.spill_val: Node | None = None

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
        before = (id(self.num), id(self.sstack[-1]) if self.sstack else 0, id(self.sload))
        self.spilled = None
        keep = self.last_val
        nxt = self._step(ops, i, o)
        if (o.kind == "rt" and o.name == "FLOAT") or (o.kind == "rom" and o.name == "AYINT"):
            self.last_val = keep  # conversions leave the value in the accumulator
        elif self.spilled is not None:
            self.last_val = "spill"
            self.spill_val = self.spilled
        elif self.num is not None and id(self.num) != before[0] and not (isinstance(self.num, Leaf) and self.num.peep):
            self.last_val = "num"
        elif self.sstack and id(self.sstack[-1]) != before[1]:
            self.last_val = "stack"
        elif self.sload is not None and id(self.sload) != before[2] and not (isinstance(self.sload, Leaf) and self.sload.peep):
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
                    if o.addr in self.fre_spills:
                        self.spilled = v  # spilled FRE/POS argument (PASS1 6330-6375)
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
            if self.last_val == "spill":
                self.num = CallN(n, [self.spill_val])
            elif self.last_val == "num":
                self.num = CallN(n, [self.take_num(o)])
            elif self.last_val in ("stack", "load") and self.fre_choice.get(o.addr, True):
                # the pending string may instead belong to a later consumer: lift() retries
                # with this choice flipped if the rest does not lift
                self.fre_decisions.append(o.addr)
                self.num = CallN(n, [self.take_str(o)])
            else:
                u = Unknown(addr=o.addr)
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
            if self.stmts and self.stmts[-1].kind == "IF" and self.stmts[-1].end == o.addr:
                # the first statement after THEN gets no debug call unless something reset the
                # flag in between: an empty statement (THEN :, PASS1 2435 -> 310) has no code
                self.stmts.append(Stmt("EMPTY", [], o.addr, o.addr))
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
    if o.kind == "lit":
        return True  # literal data is emitted when an expression is scanned, before its code
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
                prv = ops[k - 1] if k else None
                if prv is not None and prv.kind == "rt" and prv.name.split(".")[0] in ("READ", "GET", "INPUT"):
                    return False  # stored by READ/GET/INPUT: a variable, never a temp
                nxt = ops[k + 1] if k + 1 < len(ops) else None
                if (nxt is not None and nxt.kind == "rt" and nxt.name in ("FRE", "POS") and s.vtype == "str"):
                    # PASS1 6330-6375: a string result left unconsumed by FRE/POS, spilled to a
                    # temp that is never read
                    reads += 1
                    continue
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


def lift(w: Walk, choice: dict[int, bool] | None = None) -> Lifted:
    """Lift, retrying FRE/POS string-argument choices (latest first) when a lift fails.
    `choice` presets decisions (address -> consume the pending string)."""
    choice = dict(choice or {})
    for _ in range(64):
        try:
            lf = _lift(w, choice)
            lf.fre_decisions = list(dict.fromkeys(lf.fre_decisions))
            return lf
        except _Retry as r:
            choice[r.addr] = False
    raise LiftError("FRE/POS argument choices exhausted")


class _Retry(Exception):
    def __init__(self, addr: int) -> None:
        self.addr = addr


def _lift(w: Walk, choice: dict[int, bool]) -> Lifted:
    fns = find_fns(w)
    starts = line_targets(w) - set(fns)
    temps = find_temps(w, fns, starts)
    m = Machine(w, temps, fns)
    m.fre_choice = choice
    try:
        return _lift_run(w, m, fns, starts, temps)
    except LiftError:
        open_ = [a for a in m.fre_decisions if choice.get(a, True)]
        if open_:
            raise _Retry(open_[-1])
        raise


def _lift_run(w: Walk, m: "Machine", fns: dict[int, FnDef], starts: set[int], temps: set[Sym]) -> Lifted:
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
    refs = {o.words[0] for o in ops if o.kind == "rt" and o.name in ("STRLIT", "STRLIT.PROMPT")}
    free = [o for o in ops if o.kind == "lit" and o.addr + 3 not in refs]
    return Lifted(w, m.stmts, fns, temps, starts, m.unknowns, free, list(m.fre_decisions))
''', False)


# ============================================================================
# module tasc.decomp.names
# ============================================================================
_MODULES['tasc.decomp.names'] = (r'''"""Decompiler step 4: variable names that reproduce TASC's allocation order.

TASC orders symbols by a 32-bucket hash of the name, h = (3*(c1-1) + c2 + T)
mod 32 (T: real 0, string 1, int 2, +22 for arrays; INTEGER-declared names
keep T=0), with ties in insertion order.  Local storage and the routine list
are both projections of that order, so the names must be chosen to match
them.  Insertion order (seq) comes from the source we generate; the solver
merges the address and routine orders into one sequence and starts a new
bucket wherever seq goes down.
"""

from __future__ import annotations

from dataclasses import dataclass

from tasc.applesoft import TOKENS
from tasc.decomp.walk import Sym

LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
SECOND = [""] + list(LETTERS) + list("0123456789")
# two-letter keywords and names that would tokenize badly
RESERVED = {t for t in TOKENS if len(t) <= 2} | {"AT", "TO", "ON", "OR", "FN", "IF", "GR", "PI"}


def code(ch: str) -> int:
    return ord(ch) & 0x1F if ch else 0


def bucket(name: str, t: int) -> int:
    return (3 * (code(name[0]) - 1) + code(name[1:2]) + t) % 32


def type_hash(s: Sym, decl_int: bool) -> int:
    t = 0 if s.vtype == "real" or (s.vtype == "int" and decl_int) else (1 if s.vtype == "str" else 2)
    return (t + 22) % 32 if s.array else t


def suffix(s: Sym, decl_int: bool) -> str:
    if s.vtype == "str":
        return "$"
    if s.vtype == "int" and not decl_int:
        return "%"
    return ""


def _ok(name: str) -> bool:
    if name in RESERVED:
        return False
    # a final A or T joins a following keyword when the line is typed in again:
    # VA THEN reads as V AT HEN, KT OR as K TO R
    if name.endswith(("A", "T")):
        return False
    return not any(t in name for t in ("AT", "TO", "ON", "OR", "FN", "IF"))


@dataclass
class NamePool:
    used: set[tuple[str, str, bool]]

    def take(self, b: int | None, t: int, suf: str, array: bool, prefer: str = "") -> str:
        cands = [c1 + c2 for c1 in LETTERS for c2 in SECOND]
        if prefer:
            cands.sort(key=lambda n: (not n.startswith(prefer), len(n)))
        for n in cands:
            if not _ok(n) or (n, suf, array) in self.used:
                continue
            if b is not None and bucket(n, t) != b:
                continue
            self.used.add((n, suf, array))
            return n
        raise ValueError(f"no free name in bucket {b}")


def merge_orders(nodes: list[Sym], chains: list[list[Sym]], seq: dict[Sym, int]) -> list[Sym]:
    """Linear extension of the chains' orders that keeps seq increasing as long as possible."""
    succ: dict[Sym, set[Sym]] = {n: set() for n in nodes}
    indeg = {n: 0 for n in nodes}
    for ch in chains:
        for a, b in zip(ch, ch[1:]):
            if b not in succ[a]:
                succ[a].add(b)
                indeg[b] += 1
    ready = [n for n in nodes if indeg[n] == 0]
    out: list[Sym] = []
    last = -1
    while ready:
        up = [n for n in ready if seq[n] > last]
        pick = min(up or ready, key=lambda n: seq[n])
        ready.remove(pick)
        out.append(pick)
        last = seq[pick]
        for m in succ[pick]:
            indeg[m] -= 1
            if indeg[m] == 0:
                ready.append(m)
    if len(out) != len(nodes):
        raise ValueError("cyclic order constraints")
    return out


def buckets_for(order: list[Sym], seq: dict[Sym, int]) -> dict[Sym, int]:
    out: dict[Sym, int] = {}
    b = 0
    for i, s in enumerate(order):
        if i and seq[s] < seq[order[i - 1]]:
            b += 1
        out[s] = b
    if b > 31:
        raise ValueError(f"{b + 1} buckets needed")
    return out
''', False)


# ============================================================================
# module tasc.decomp.render
# ============================================================================
_MODULES['tasc.decomp.render'] = (r'''"""Decompiler step 3: lay statements out in lines and render tokenized Applesoft.

Lines are rendered straight to tokenized bytes (keywords as tokens), so string
literals and DATA items may hold any byte.  `listing()` gives a readable text
form with non-printing bytes escaped as {$xx}.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from tasc.compiler.fin import fin
from tasc.compiler.parse import TOK
from tasc.decomp.lift import (
    SWAP, BinN, CallN, Elem, FnN, Leaf, Lifted, Lit, Node, Stmt, UnN, Unknown,
)
from tasc.decomp.walk import Sym
from tasc.objfile import int_value, real_value

PRIO = {"OR": 0x46, "AND": 0x50, "=": 0x64, "<": 0x64, ">": 0x64, "<=": 0x64, ">=": 0x64, "<>": 0x64,
        "+": 0x79, "-": 0x79, "*": 0x7B, "/": 0x7B, "^": 0x7D}
ENDS_LINE = {"GOTO", "IFGOTO", "IFRETURN", "RETURN", "END", "STOP", "NEW", "ONERR", "RESUME", "RUN"}


class RenderError(Exception):
    pass


def _plain(t: str) -> str:
    """Decimal text without an exponent, Applesoft style (.5, not 0.5)."""
    from decimal import Decimal
    d = format(Decimal(t), "f")
    if "." in d:
        d = d.rstrip("0").rstrip(".")
    if d.startswith("0."):
        d = d[1:]
    elif d.startswith("-0."):
        d = "-" + d[2:]
    return d


def real_text(raw: bytes) -> str:
    """Shortest decimal text that the ROM's FIN packs to exactly `raw` (plain decimal
    preferred; exponent form when it is shorter)."""
    v = real_value(raw)
    if v == 0:
        return "0"
    for p in range(1, 18):
        g = f"{v:.{p}G}"
        cands = [_plain(g)]
        if "E" in g:
            m, e = g.split("E")
            cands.append(f"{m}E{int(e)}")
        for t in sorted(cands, key=len):
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
    filler: bytes = b"0"  # FRE/POS argument when no unreferenced local needs one

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
            if n.lit is not None:
                return b'"' + n.lit + b'"'
            return self.name(n.sym) if n.sym is not None else self.filler
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
            op, left, right_ = n.op, n.l, n.r
            if n.flip:
                op, left, right_ = SWAP.get(op, op), n.r, n.l
            p = PRIO[op]
            opb = _rel(op) if p == 0x64 else bytes([TOK[op]])
            s = self.expr(left, p, False) + opb + self.expr(right_, p, True)
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
        if k == "EMPTY":
            return b""
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
        # spacing is normalised outside quotes only; string literals keep their text
        parts = "".join(s).split('"')
        for i in range(0, len(parts), 2):
            p = parts[i]
            while "  " in p:
                p = p.replace("  ", " ")
            for a, b in (("< =", "<="), ("> =", ">="), ("< >", "<>"), ("> <", "><"), ("= <", "=<"), ("= >", "=>")):
                p = p.replace(a, b)
            parts[i] = p
        text = '"'.join(parts).strip()
        out.append(f"{num} {text}")
    return "\n".join(out) + "\n"
''', False)


# ============================================================================
# module tasc.decomp.decompile
# ============================================================================
_MODULES['tasc.decomp.decompile'] = (r'''"""Decompile TASC object files to tokenized Applesoft and verify by recompiling.

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
from tasc.options import Options

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
    for i, n in enumerate(order):
        per: dict[int, tuple[int, str]] = {}
        target = i * 32 // len(order)
        for sc, c in options(n):
            b = N.bucket(c, n.t)
            if n.key not in prefs:
                sc = -abs(b - target)  # no preference: spread over the buckets (room for names)
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
''', False)


# ============================================================================
# module tasc.tascad
# ============================================================================
_MODULES['tasc.tascad'] = (r'''"""TASCAD: The AppleSoft Compiler and Decompiler.

A Python reimplementation of Microsoft's TASC 2.01 Applesoft compiler (1981) that
produces the same object files byte for byte, and a decompiler that turns a TASC
object file back into an Applesoft program which compiles to the same bytes.

    tascad compile SOURCE [-o OBJECT] [options]
        SOURCE is a text listing (numbered lines) or a tokenized Applesoft program
        (as saved by DOS, without the 2-byte length). Writes the object file as TASC
        does (the contents of the binary file; its load address is printed).
          --library ADDR --program ADDR|HGR1|HGR2 --variables ADDR   memory layout
          --no-int-arith --no-int-const --resume                     code options
          --compare OBJECT   check the result against an existing object file
          --map              print the line number table (line, address)

    tascad decompile OBJECT [-o LISTING] [--bas PROGRAM] [--load ADDR]
        Reads a TASC object file, works out its load address and memory layout from
        its header, finds the code options by trying them, and writes the Applesoft
        program (a text listing, and with --bas the tokenized program). The result
        is checked by compiling it again: it is reported only if the bytes match.

Files are read from and written to the local filesystem. A file inside a disk image
is named IMAGE::NAME (for example "TASC.dsk::BALL" or -o "WORK.dsk::BALL.OBJ"); disk
images are read and written with CiderPress II's command-line program, found through
--cp2 PATH, the CP2PATH environment variable, or cp2 on the PATH. A binary file read
from an image brings its load address; an object written to an image is a binary file
at its load address, a program (--bas) an Applesoft file. --replace lets a write
replace a file already on the image.

Addresses may be decimal, $hex or 0xhex. Requires Python 3.9 or later (tested on 3.9.6
and 3.14); standard library only.
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import os
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

from tasc.applesoft import tokenize_program
from tasc.compiler.assemble import compile_program
from tasc.options import Options

LIBRARY = 0x0803
LIBRARY_LEN = 4013


# ---------------------------------------------------------------- files: local or inside a disk image

CP2 = "cp2"
TYPES = {"A": 0xFC, "B": 0x06}


@dataclass
class File:
    data: bytes
    load: int | None = None  # a binary file's address, when it came from a disk image


def _image(spec: str) -> tuple[str, str] | None:
    if "::" in spec:
        image, name = spec.split("::", 1)
        return image, name
    return None


def _cp2(*args: str, cwd: str | None = None) -> str:
    try:
        p = subprocess.run([CP2, *args], cwd=cwd, capture_output=True, text=True, check=False)
    except FileNotFoundError:
        raise SystemExit(f"tascad: CiderPress II not found as {CP2!r}; give --cp2 PATH or set CP2PATH") from None
    if p.returncode != 0:
        raise SystemExit(f"tascad: cp2 {' '.join(args)} failed:\n{p.stderr}{p.stdout}")
    return p.stdout


def read_file(spec: str) -> File:
    img = _image(spec)
    if img is None:
        return File(Path(spec).read_bytes())
    image, name = img
    with tempfile.TemporaryDirectory() as td:
        _cp2("extract", "--preserve=naps", "--overwrite", str(Path(image).resolve()), name, cwd=td)
        files = [f for f in Path(td).rglob("*") if f.is_file()]
        if len(files) != 1:
            raise SystemExit(f"tascad: {name} not found on {image}")
        m = re.search(r"#([0-9a-fA-F]{2})([0-9a-fA-F]{4})$", files[0].name)
        load = int(m.group(2), 16) if m and int(m.group(1), 16) == 0x06 else None
        return File(files[0].read_bytes(), load)


def write_file(spec: str, data: bytes, kind: str, load: int = 0x0801, replace: bool = False) -> None:
    """Write data locally, or to a disk image as a file of the given kind (A or B)."""
    img = _image(spec)
    if img is None:
        Path(spec).write_bytes(data)
        return
    image, name = img
    path = str(Path(image).resolve())
    # cp2 add skips a name that is already there without saying so: check first
    on_disk = any(re.search(r"[ *]" + re.escape(name) + r"$", line.rstrip())
                  for line in _cp2("catalog", path).splitlines())
    if on_disk and not replace:
        raise SystemExit(f"tascad: {name} is already on {image}; give --replace to replace it")
    with tempfile.TemporaryDirectory() as td:
        host = Path(td) / f"{name}#{TYPES[kind]:02x}{load:04x}"
        host.write_bytes(data)
        _cp2("add", "--overwrite", path, host.name, cwd=td) if on_disk else _cp2("add", path, host.name, cwd=td)


def _addr(text: str) -> int:
    t = text.strip()
    if t.startswith("$"):
        return int(t[1:], 16)
    return int(t, 0)


def read_source(spec: str) -> bytes:
    """A text listing is tokenized; anything else is taken as a tokenized program."""
    raw = read_file(spec).data
    try:
        text = raw.decode("ascii")
        first = next(line for line in text.splitlines() if line.strip())
        if first.strip()[:1].isdigit():
            return tokenize_program(text)
    except (UnicodeDecodeError, StopIteration):
        pass
    return raw


def _word(data: bytes, i: int) -> int:
    return data[i] | data[i + 1] << 8


def header(data: bytes) -> dict[str, int]:
    """The object's JSR to the library and the header INIT copies to page zero."""
    if len(data) < 20 or data[0] != 0x20:
        raise ValueError("not a TASC object file (it must start with JSR to the library)")
    w = [_word(data, 3 + 2 * k) for k in range(8)]
    return {"library": _word(data, 1), "data": w[0], "highest": w[1], "common": w[2] + 1,
            "load": w[4] + 1, "locals": w[5] + 1, "flag": data[19]}


def candidate_options(h: dict[str, int]) -> list[Options]:
    """Options to try for a decompile: the memory layout from the header, the code
    options in every combination, the defaults first."""
    lib = None if h["library"] == LIBRARY else h["library"]
    prog = None if h["common"] == h["library"] + LIBRARY_LEN else h["common"]
    out = []
    for variables in (None, h["locals"]):
        for ia, ic, rd in itertools.product((True, False), (True, False), (False, True)):
            out.append(Options(library=lib, program=prog, variables=variables,
                               int_arith=ia, int_const=ic, resume=rd))
    return out


def cmd_compile(a: argparse.Namespace) -> int:
    program = read_source(a.source)
    prog: int | str | None = None
    if a.program:
        prog = a.program.upper() if a.program.upper() in ("HGR1", "HGR2") else _addr(a.program)
    opts = Options(library=_addr(a.library) if a.library else None, program=prog,
                   variables=_addr(a.variables) if a.variables else None,
                   int_arith=not a.no_int_arith, int_const=not a.no_int_const, resume=a.resume)
    res = compile_program(program, opts)
    out = a.output or (a.source + ".OBJ" if _image(a.source) else str(Path(a.source).with_suffix(".OBJ")))
    write_file(out, res.data, "B", res.load, a.replace)
    print(f"{out}: load ${res.load:04X}, {len(res.data)} bytes, sha256 {hashlib.sha256(res.data).hexdigest()}")
    if a.map:
        for n, ad in sorted(res.line_addr.items()):
            if n >= 0:
                print(f"{n:>6} ${ad:04X}")
    if a.compare:
        other = read_file(a.compare).data
        if other == res.data:
            print(f"identical to {a.compare}")
        else:
            off = next((k for k in range(min(len(other), len(res.data))) if other[k] != res.data[k]),
                       min(len(other), len(res.data)))
            print(f"differs from {a.compare} at ${res.load + off:04X} (byte {off}); "
                  f"{len(res.data)} vs {len(other)} bytes")
            return 1
    return 0


def cmd_decompile(a: argparse.Namespace) -> int:
    from tasc.decomp.decompile import compare, decompile
    obj = read_file(a.object)
    data = obj.data
    h = header(data)
    load = _addr(a.load) if a.load else obj.load or h["load"]
    for opts in candidate_options(h):
        try:
            u = decompile(data, load, opts)
        except Exception:  # noqa: BLE001  (another option set may fit)
            continue
        if compare(u) != "identical":
            continue
        listing = u.text if u.text.endswith("\n") else u.text + "\n"
        if a.output:
            write_file(a.output, listing.encode("ascii"), "A", replace=a.replace) if _image(a.output) is None \
                else write_file(a.output, u.program, "A", replace=a.replace)
        else:
            sys.stdout.write(listing)
        if a.bas:
            write_file(a.bas, u.program, "A", replace=a.replace)
        flags = [k for k, on in (("integer arithmetic", opts.int_arith), ("integer constants", opts.int_const),
                                 ("RESUME/debug code", opts.resume)) if on]
        print(f"decompiled: load ${load:04X}, library ${h['library']:04X}, options: "
              f"{', '.join(flags) or 'none'}; the program compiles back to the same {len(data)} bytes",
              file=sys.stderr)
        return 0
    print("no Applesoft program found that compiles back to these bytes", file=sys.stderr)
    return 1


def main(argv: list[str] | None = None) -> int:
    global CP2
    p = argparse.ArgumentParser(prog="tascad", description="The AppleSoft Compiler and Decompiler (TASC 2.01)")
    p.add_argument("--cp2", help="CiderPress II command-line program, for disk images (default: $CP2PATH or cp2)")
    sub = p.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("compile", help="compile an Applesoft program as TASC 2.01 does")
    c.add_argument("source")
    c.add_argument("-o", "--output")
    c.add_argument("--library")
    c.add_argument("--program")
    c.add_argument("--variables")
    c.add_argument("--no-int-arith", action="store_true")
    c.add_argument("--no-int-const", action="store_true")
    c.add_argument("--resume", action="store_true")
    c.add_argument("--compare")
    c.add_argument("--map", action="store_true")
    c.add_argument("--replace", action="store_true")
    d = sub.add_parser("decompile", help="turn a TASC object file back into an Applesoft program")
    d.add_argument("object")
    d.add_argument("-o", "--output")
    d.add_argument("--bas")
    d.add_argument("--load")
    d.add_argument("--replace", action="store_true")
    a = p.parse_args(argv)
    CP2 = a.cp2 or os.environ.get("CP2PATH") or "cp2"
    return cmd_compile(a) if a.cmd == "compile" else cmd_decompile(a)


if __name__ == "__main__":
    raise SystemExit(main())
''', False)

# ---------------------------------------------------------------- loader
import importlib.abc
import importlib.util
import linecache
import sys


class _Bundle(importlib.abc.MetaPathFinder, importlib.abc.Loader):
    """Imports the modules above from this file."""

    def find_spec(self, name, path=None, target=None):  # type: ignore[no-untyped-def]
        if name in _MODULES:
            return importlib.util.spec_from_loader(name, self, is_package=_MODULES[name][1])
        return None

    def create_module(self, spec):  # type: ignore[no-untyped-def]
        return None

    def exec_module(self, module):  # type: ignore[no-untyped-def]
        source = _MODULES[module.__name__][0]
        filename = f"<tascad:{module.__name__}>"
        linecache.cache[filename] = (len(source), None, source.splitlines(True), filename)
        exec(compile(source, filename, "exec"), module.__dict__)


sys.meta_path.insert(0, _Bundle())

if __name__ == "__main__":
    from tasc.tascad import main
    raise SystemExit(main())
