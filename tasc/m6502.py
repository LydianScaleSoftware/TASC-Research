"""Minimal deterministic NMOS 6502 decoder (documented opcodes only)."""

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
