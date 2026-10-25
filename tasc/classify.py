"""Classify every byte of a TASC object file (Phase 2).

Classes: header, code (compiled-template instructions), strlit (inline string
literal data), data (DATA statement blocks), inline (operand bytes read by a
RUNTIME routine after its JSR), const (constant pool), routine (variable access
routines), foreign (anything that does not fit TASC's code vocabulary).

    python -m tasc.classify extracted/tasc201/PASS1#0641f2 [--list]
"""

from __future__ import annotations

import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from tasc import m6502
from tasc.objfile import ObjectFile, parse
from tasc.symbols import INLINE_OPERANDS, all_names

# ON GOTO / ON GOSUB (real and int entries): .BYTE count, .WORD x count
ONLIST = {0x14B0, 0x14B3, 0x14B7, 0x14BA}
# integer FOR init (and its real-expression variant) also carry the variable address
INLINE_EXTRA = {0x09E1: 2, 0x09DE: 2}


@dataclass
class Region:
    start: int
    end: int  # exclusive
    cls: str
    text: str = ""


@dataclass
class Classified:
    name: str
    obj: ObjectFile
    regions: list[Region] = field(default_factory=list)

    def counts(self) -> Counter[str]:
        c: Counter[str] = Counter()
        for r in self.regions:
            c[r.cls] += r.end - r.start
        return c


def _is_data_block(d: bytes, load: int, start: int, target: int) -> bool:
    """[len][text]... $FF [link word] exactly filling start..target."""
    p = start - load
    end = target - load
    while p < end:
        n = d[p]
        if n == 0xFF:
            return p + 3 == end
        p += 1 + n
    return False


def classify(name: str, data: bytes, load: int) -> Classified:
    o = parse(data, load)
    lib = data[1] | data[2] << 8
    delta = lib - 0x0803
    names = all_names(delta)
    inline = {a + delta: n for a, n in INLINE_OPERANDS.items()} | {a + delta: n for a, n in INLINE_EXTRA.items()}
    onlist = {a + delta for a in ONLIST}
    res = Classified(name, o)
    R = res.regions
    R.append(Region(load, load + 20, "header", o.header.describe()))
    a = load + 20
    entries = {e for r in o.routines for e in r.entries}
    while a < o.code_end:
        i = m6502.decode(data, load, a)
        off = a - load
        cls = "code"
        n = i.length
        ok = False
        if i.mnemonic in ("JSR", "JMP") and i.operand is not None:
            ok = True
            if i.mnemonic == "JMP" and a < i.operand <= o.code_end:
                ln = data[off + 3] if off + 3 < len(data) else -1
                if ln == i.operand - a - 4:
                    R.append(Region(a, a + 3, "code", "JMP past literal"))
                    R.append(Region(a + 3, i.operand, "strlit", data[off + 4 : i.operand - load].decode("ascii", "replace")))
                    a = i.operand
                    continue
                if _is_data_block(data, load, a + 3, i.operand):
                    R.append(Region(a, a + 3, "code", "JMP past DATA"))
                    R.append(Region(a + 3, i.operand, "data"))
                    a = i.operand
                    continue
        elif i.mnemonic in ("LDA", "ORA") and i.mode == "abs":
            ok = True  # AND/OR operand test
        elif i.raw in (b"\xA5\x9D", b"\xA5\xA0", b"\x05\xA1", b"\x60", b"\xD0\x03", b"\xF0\x03", b"\xF0\x01"):
            ok = True
        if not ok:
            cls = "foreign"
        text = i.text(names)
        if i.mnemonic in ("JSR", "JMP") and i.operand in entries:
            text = f"{i.mnemonic} routine"
        R.append(Region(a, a + n, cls, text))
        a += n
        if ok and i.mnemonic == "JSR" and i.operand is not None:
            if i.operand in inline:
                k = inline[i.operand]
                R.append(Region(a, a + k, "inline"))
                a += k
            elif i.operand in onlist:
                k = 1 + 2 * data[a - load]
                R.append(Region(a, a + k, "inline", "ON list"))
                a += k
    for k in o.constants:
        R.append(Region(k.addr, k.addr + len(k.raw), "const", f"{k.vtype} {k.value:g}"))
    for r in o.routines:
        R.append(Region(r.addr, r.addr + r.length, "routine", f"{r.vtype}{'()' if r.dims else ''} -> ${r.target:04X}"))
    R.sort(key=lambda x: x.start)
    # coverage check
    pos = load
    for r in R:
        if r.start != pos:
            R.append(Region(pos, r.start, "gap"))
        pos = max(pos, r.end)
    R.sort(key=lambda x: x.start)
    return res


def merged_foreign(c: Classified) -> list[tuple[int, int]]:
    out: list[tuple[int, int]] = []
    for r in c.regions:
        if r.cls == "foreign":
            if out and out[-1][1] == r.start:
                out[-1] = (out[-1][0], r.end)
            else:
                out.append((r.start, r.end))
    return out


def main() -> None:
    path = Path(sys.argv[1])
    data = path.read_bytes()
    load = int(path.name.split("#")[1][2:], 16)
    c = classify(path.name, data, load)
    cnt = c.counts()
    print(path.name, len(data), "bytes:", dict(cnt))
    fr = merged_foreign(c)
    print(f"{len(fr)} foreign runs, {sum(b - a for a, b in fr)} bytes")
    if "--list" in sys.argv:
        for a, b in fr[:60]:
            print(f"  ${a:04X}-${b - 1:04X} ({b - a} bytes)")


if __name__ == "__main__":
    main()
