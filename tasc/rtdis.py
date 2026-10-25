"""Flow-following disassembly of RUNTIME (Phase R).

Seeds: TASC's own entry table (PASS0/PASS2 DATA), the named entries in
tasc.symbols and the integer/real partner entries used by compiled code.
Follows JSR/JMP/branches inside RUNTIME; stops at RTS/RTI/JMP/BRK and
indirect jumps.  Bytes reached as instruction starts are 'code'; a byte that
is both an operand and an instruction start (BIT-skip tricks) is 'overlap'.

    python -m tasc.rtdis [--listing out.txt]
"""

from __future__ import annotations

import glob
import json
import sys
from collections import Counter
from pathlib import Path

from tasc import m6502
from tasc.symbols import ROM, RUNTIME

ROOT = Path(__file__).resolve().parent.parent
LIB = 0x0803
DATA = Path(glob.glob(str(ROOT / "extracted/tasc201/RUNTIME#*"))[0]).read_bytes()
END = LIB + len(DATA)
PARTNERS = {0x09E5, 0x09E8, 0x09E1, 0x09DE, 0x1691, 0x168E, 0x168A, 0x1687, 0x167E, 0x16BC, 0x16BF, 0x16B5, 0x16B8,
            0x16AC, 0x165C, 0x165F, 0x1675, 0x0CDA}


def seeds() -> dict[int, str]:
    s: dict[int, str] = {LIB: "RT.INIT"}
    j = json.loads((ROOT / "docs/runtime_entries.json").read_text())
    for a in j["table"]:
        s.setdefault(a, f"T_{a:04X}")
    for a, n in RUNTIME.items():
        s[a] = n
        for d in (3, -3):
            if a + d in j["table"] or a + d in j["observed"]:
                s.setdefault(a + d, n + ("/I" if d == 3 else "/R"))
    for a in PARTNERS:
        s.setdefault(a, f"E_{a:04X}")
    return s


def disassemble() -> tuple[dict[int, m6502.Insn], Counter[int], dict[int, str], set[int]]:
    names = seeds()
    insns: dict[int, m6502.Insn] = {}
    owner: Counter[int] = Counter()
    work = list(names)
    jsr_targets: set[int] = set()
    while work:
        a = work.pop()
        while LIB <= a < END and a not in insns:
            i = m6502.decode(DATA, LIB, a)
            insns[a] = i
            for k in range(i.length):
                owner[a + k] += 1
            mn = i.mnemonic
            if mn == "???" or mn == "BRK":
                break
            if mn in ("JSR", "JMP") and i.mode == "abs" and i.operand is not None:
                if LIB <= i.operand < END:
                    work.append(i.operand)
                    if mn == "JSR":
                        jsr_targets.add(i.operand)
                        names.setdefault(i.operand, f"S_{i.operand:04X}")
                    else:
                        names.setdefault(i.operand, f"L_{i.operand:04X}")
                if mn == "JMP":
                    break
            if i.mode == "rel" and i.operand is not None:
                work.append(i.operand)
                names.setdefault(i.operand, f"L_{i.operand:04X}")
            if mn in ("RTS", "RTI") or (mn == "JMP" and i.mode == "ind"):
                break
            a += i.length
    return insns, owner, names, jsr_targets


def main() -> None:
    insns, owner, names, jsrt = disassemble()
    code = {b for b in owner}
    overlap = {a for a, i in insns.items() if any(owner[a + k] > 1 for k in range(i.length))}
    print(f"RUNTIME {len(DATA)} bytes ${LIB:04X}-${END - 1:04X}: {len(code)} reached as code, "
          f"{len(insns)} instructions, {len(overlap)} instructions overlap (BIT tricks), "
          f"{len(DATA) - len(code)} bytes not reached")
    gaps: list[tuple[int, int]] = []
    a = LIB
    while a < END:
        if a not in code:
            b = a
            while b < END and b not in code:
                b += 1
            gaps.append((a, b))
            a = b
        else:
            a += 1
    print(f"{len(gaps)} unreached runs:", ", ".join(f"${s:04X}-${e - 1:04X}({e - s})" for s, e in gaps[:60]))
    if "--listing" in sys.argv:
        out = Path(sys.argv[sys.argv.index("--listing") + 1])
        nm = {**ROM, **names}
        lines = []
        a = LIB
        while a < END:
            if a in insns:
                i = insns[a]
                if a in names:
                    lines.append(f"{names[a]}:")
                lines.append("  " + m6502.fmt(i, nm) + ("   ; overlap" if a in overlap else ""))
                a += i.length if a + i.length <= END else 1
            else:
                b = a
                while b < END and b not in insns:
                    b += 1
                for s in range(a, b, 16):
                    chunk = DATA[s - LIB : min(b, s + 16) - LIB]
                    lines.append(f"  {s:04X}: .HS {chunk.hex(' ').upper():<48} ; {''.join(chr(c & 0x7F) if 32 <= (c & 0x7F) < 127 else '.' for c in chunk)}")
                a = b
        out.write_text("\n".join(lines) + "\n")
        print("listing ->", out)


if __name__ == "__main__":
    main()
