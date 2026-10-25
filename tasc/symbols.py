"""Address-name table: Applesoft ROM, Monitor, zero page (manual App. F), RUNTIME.

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
    0xEB63: "MOVAF", 0xE7AA: "FSUBT",
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
    0x0CC3: "RT.INEG",
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
