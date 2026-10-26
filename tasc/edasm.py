"""A small two-pass 6502 assembler for the EDASM-style source subset used in src/RUNTIME.S.

    python -m tasc.edasm FILE        assemble FILE and print the length and SHA-256

It accepts exactly what the generated RUNTIME source uses, with the rules of Apple's
DOS Toolkit assembler (EDASM) that decide the bytes:

- a label starts in column 1 (at most 8 characters, a letter first, then letters and
  digits); `*` in column 1 is a comment line; `;` starts an end-of-line comment;
- directives ORG, EQU and DFB (bytes, separated by commas);
- operands: `#expr`, `expr`, `expr,X`, `expr,Y`, `(expr,X)`, `(expr),Y`, `(expr)`; an
  opcode alone is implied or accumulator mode (`ASL`);
- expressions: `$hex`, decimal, symbols and `*` combined with `+` and `-`;
- a zero-page form is used whenever the operand's value is known in pass 1, is below
  $100 and the instruction has one; otherwise the absolute form.  This is why the source
  writes the few absolute references to page zero as DFB.
"""

from __future__ import annotations

import hashlib
import re
import sys
from dataclasses import dataclass
from pathlib import Path

from tasc.m6502 import OPCODES

# mnemonic -> mode -> opcode
TABLE: dict[str, dict[str, int]] = {}
for _op, (_mn, _mode) in OPCODES.items():
    TABLE.setdefault(_mn, {})[_mode] = _op
LENGTH = {"imp": 1, "acc": 1, "imm": 2, "zp": 2, "zpx": 2, "zpy": 2, "izx": 2, "izy": 2,
          "abs": 3, "abx": 3, "aby": 3, "ind": 3, "rel": 2}
LABEL = re.compile(r"^[A-Z][A-Z0-9]{0,7}$")


class AsmError(Exception):
    pass


@dataclass
class Line:
    number: int
    label: str
    op: str
    operand: str


def parse(text: str) -> list[Line]:
    out: list[Line] = []
    for n, raw in enumerate(text.splitlines(), 1):
        if not raw.strip() or raw.startswith("*"):
            continue
        code = raw.split(";", 1)[0].rstrip()
        label = ""
        if not code[:1].isspace():
            label, _, code = code.partition(" ")
            if not LABEL.match(label):
                raise AsmError(f"line {n}: bad label {label!r}")
        parts = code.split(None, 1)
        op = parts[0] if parts else ""
        operand = parts[1].strip() if len(parts) > 1 else ""
        out.append(Line(n, label, op, operand))
    return out


def value(expr: str, sym: dict[str, int], pc: int, strict: bool) -> int | None:
    """Value of an expression, or None when a symbol is not known yet (pass 1)."""
    total = 0
    for sign, term in re.findall(r"([+-]?)\s*([^+-]+)", expr.replace(" ", "")):
        if term.startswith("$"):
            v = int(term[1:], 16)
        elif term.isdigit():
            v = int(term)
        elif term == "*":
            v = pc
        elif term in sym:
            v = sym[term]
        elif strict:
            raise AsmError(f"undefined symbol {term!r}")
        else:
            return None
        total += -v if sign == "-" else v
    return total


def mode_of(mn: str, operand: str, v: int | None) -> tuple[str, str]:
    """Addressing mode and the expression inside the operand."""
    modes = TABLE[mn]
    if not operand or operand == "A":
        return ("acc" if "acc" in modes else "imp"), ""
    if operand.startswith("#"):
        return "imm", operand[1:]
    if "rel" in modes:
        return "rel", operand
    m = re.fullmatch(r"\((.+),X\)", operand)
    if m:
        return "izx", m.group(1)
    m = re.fullmatch(r"\((.+)\),Y", operand)
    if m:
        return "izy", m.group(1)
    m = re.fullmatch(r"\((.+)\)", operand)
    if m:
        return "ind", m.group(1)
    m = re.fullmatch(r"(.+),([XY])", operand)
    expr, idx = (m.group(1), m.group(2)) if m else (operand, "")
    zp = {"": "zp", "X": "zpx", "Y": "zpy"}[idx]
    ab = {"": "abs", "X": "abx", "Y": "aby"}[idx]
    if v is not None and v < 0x100 and zp in modes:
        return zp, expr
    return ab, expr


def assemble(text: str) -> tuple[int, bytes, dict[str, int]]:
    lines = parse(text)
    sym: dict[str, int] = {}
    org: int | None = None
    # pass 1: addresses
    pc = 0
    sizes: dict[int, int] = {}
    for ln in lines:
        if ln.op == "ORG":
            pc = value(ln.operand, sym, pc, True) or 0
            org = pc if org is None else org
            continue
        if ln.op == "EQU":
            sym[ln.label] = value(ln.operand, sym, pc, True) or 0
            continue
        if ln.label:
            if ln.label in sym:
                raise AsmError(f"line {ln.number}: {ln.label} defined twice")
            sym[ln.label] = pc
        if ln.op == "DFB":
            size = len(ln.operand.split(","))
        elif ln.op in TABLE:
            v = value(_core(ln.operand), sym, pc, False) if ln.operand and ln.operand != "A" else None
            size = LENGTH[mode_of(ln.op, ln.operand, v)[0]]
        else:
            raise AsmError(f"line {ln.number}: unknown opcode {ln.op!r}")
        sizes[ln.number] = size
        pc += size
    # pass 2: bytes
    out = bytearray()
    pc = org or 0
    for ln in lines:
        if ln.op in ("ORG", "EQU"):
            continue
        if ln.op == "DFB":
            for e in ln.operand.split(","):
                v = value(e, sym, pc, True)
                assert v is not None
                out.append(v & 0xFF)
            pc += sizes[ln.number]
            continue
        mode, expr = mode_of(ln.op, ln.operand, value(_core(ln.operand), sym, pc, False) if ln.operand else None)
        if LENGTH[mode] != sizes[ln.number]:
            raise AsmError(f"line {ln.number}: size changed between passes")
        op = TABLE[ln.op].get(mode)
        if op is None:
            raise AsmError(f"line {ln.number}: {ln.op} has no {mode} mode")
        out.append(op)
        if mode in ("imp", "acc"):
            pass
        else:
            v = value(expr, sym, pc, True)
            assert v is not None
            if mode == "rel":
                d = v - (pc + 2)
                if not -128 <= d <= 127:
                    raise AsmError(f"line {ln.number}: branch out of range")
                out.append(d & 0xFF)
            elif LENGTH[mode] == 2:
                if mode != "imm" and v > 0xFF:
                    raise AsmError(f"line {ln.number}: operand too large")
                out.append(v & 0xFF)
            else:
                out += bytes((v & 0xFF, (v >> 8) & 0xFF))
        pc += sizes[ln.number]
    return org or 0, bytes(out), sym


def _core(operand: str) -> str:
    s = operand.lstrip("#")
    s = re.sub(r"^\((.*)\),Y$", r"\1", s)
    s = re.sub(r"^\((.*),X\)$", r"\1", s)
    s = re.sub(r"^\((.*)\)$", r"\1", s)
    return re.sub(r",[XY]$", "", s)


def main() -> None:
    org, data, _ = assemble(Path(sys.argv[1]).read_text())
    print(f"${org:04X}, {len(data)} bytes, sha256 {hashlib.sha256(data).hexdigest()}")


if __name__ == "__main__":
    main()
