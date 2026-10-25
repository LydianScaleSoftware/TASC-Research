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
}

ZERO_PAGE: dict[int, str] = {
    0x12: "DATAPTR", 0x14: "HIGHEST", 0x16: "ZTEMP16",
    0x58: "FLTINTJMP", 0x5B: "ONERRJMP",
    0x67: "TXTTAB", 0x69: "COMBEG1", 0x6B: "NUMCOMEND", 0x6D: "STRCOMEND", 0x6F: "STRBOT1",
    0x73: "MEMSIZ", 0x75: "OBJPC", 0x7B: "LOCBEG1", 0x7D: "LOCNUMEND", 0x7F: "LOCSTREND",
    0x9E: "IACC", 0xAF: "FORPOP",
}

# RUNTIME entry points seen in compiled code (2.01, library at $0803).
RUNTIME: dict[int, str] = {
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
    0x0EC5: 2,
}

DISPATCHERS: dict[int, str] = {0x1764: "real", 0x0D06: "int", 0x0C7F: "str"}


def all_names() -> dict[int, str]:
    d: dict[int, str] = {}
    d.update(ROM)
    d.update(RUNTIME)
    return d
