"""Phase 5: RUNTIME as documented 6502 source in the style of Apple's EDASM.

    python -m tasc.rtsource        write src/RUNTIME.S and check that it assembles to RUNTIME

The source comes from the flow disassembly (tasc.rtdis) and the annotations in
docs/lift/annot/RUNTIME.ann: names for the zero page, the ROM and the routines, comment
blocks above routines, end-of-line comments and the data runs.  Every reference inside
RUNTIME is a label.  Bytes that EDASM could not reproduce from an instruction (the BIT
opcode used to skip two bytes, an absolute address on page zero where a zero-page form
exists) are written with DFB and the instruction in the comment.  The check assembles the
text with tasc.edasm and compares every byte with RUNTIME.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from tasc import edasm, m6502, rtdis

ROOT = Path(__file__).resolve().parents[1]
ANN = ROOT / "docs" / "lift" / "annot" / "RUNTIME.ann"
OUT = ROOT / "src" / "RUNTIME.S"
LIB, END, DATA = rtdis.LIB, rtdis.END, rtdis.DATA
WIDTH = 39  # comment column for code lines


@dataclass
class Ann:
    equates: list[tuple[str, int, str]] = field(default_factory=list)
    labels: dict[int, str] = field(default_factory=dict)
    routines: dict[int, str] = field(default_factory=dict)
    lines: dict[int, str] = field(default_factory=dict)
    data: list[tuple[int, int, str, str]] = field(default_factory=list)


def load() -> Ann:
    a = Ann()
    sec = ""
    for raw in ANN.read_text().splitlines():
        s = raw.strip()
        if not s or s.startswith("#"):
            continue
        if s.startswith("["):
            sec = s
            continue
        if sec == "[equates]":
            name, val, comment = (s.split(None, 2) + [""])[:3]
            a.equates.append((name, int(val[1:], 16), comment))
        elif sec == "[labels]":
            addr, name = s.split()
            a.labels[int(addr[1:], 16)] = name
        elif sec in ("[routines]", "[lines]"):
            addr, text = s.split(None, 1)
            (a.routines if sec == "[routines]" else a.lines)[int(addr[1:], 16)] = text
        elif sec == "[data]":
            first, last, kind, comment = s.split(None, 3)
            a.data.append((int(first[1:], 16), int(last[1:], 16), kind, comment))
    return a


@dataclass
class Item:
    addr: int
    size: int
    op: str
    operand: str
    comment: str = ""


def build_items(ann: Ann) -> tuple[list[Item], dict[int, str]]:
    insns, _, _, _ = rtdis.disassemble()
    data_at = {first: (first, last, kind, c) for first, last, kind, c in ann.data}
    in_data = {x for first, last, _, _ in ann.data for x in range(first, last + 1)}
    # unreached runs that are not declared data are decoded as code
    a = LIB
    while a < END:
        if a not in insns and a not in in_data and not any(a in range(s, s + i.length) for s, i in insns.items() if s < a <= s + 2):
            i = m6502.decode(DATA, LIB, a)
            insns[a] = i
            a += i.length
        else:
            a += 1
    starts = set(insns)
    # labels: annotated names, then every internal target
    labels: dict[int, str] = dict(ann.labels)
    targets: set[int] = set()
    for s, i in insns.items():
        if s in in_data:
            continue
        if i.operand is not None and i.mode != "imm" and LIB <= i.operand < END and not _overlapped(s, i, starts):
            targets.add(i.operand)
    for t in sorted(targets):
        if t not in labels and t in starts and t not in in_data:
            labels[t] = ""  # filled below
    _name_locals(labels)
    items: list[Item] = []
    a = LIB
    while a < END:
        if a in data_at:
            first, last, kind, comment = data_at[a]
            items += _data_items(first, last, kind, comment)
            a = last + 1
            continue
        found = insns.get(a)
        if found is None:
            raise ValueError(f"no instruction or data at ${a:04X}")
        insn = found
        inner = [k for k in range(1, insn.length) if a + k in starts]
        if inner:  # BIT used to skip the next instruction
            k = inner[0]
            items.append(Item(a, k, "DFB", ",".join(f"${b:02X}" for b in DATA[a - LIB:a - LIB + k]),
                              "BIT ABSOLUTE: SKIPS THE NEXT 2 BYTES" if DATA[a - LIB] == 0x2C else "SKIPS THE NEXT BYTES"))
            a += k
            continue
        items.append(_insn_item(insn, labels))
        a += insn.length
    return items, labels


def _overlapped(s: int, i: m6502.Insn, starts: set[int]) -> bool:
    return any(s + k in starts for k in range(1, i.length))


def _name_locals(labels: dict[int, str]) -> None:
    used = {n for n in labels.values() if n} | set(EQ.values())
    owner = ""
    count: dict[str, int] = {}
    for addr in sorted(labels):
        if labels[addr]:
            owner = labels[addr]
            continue
        prefix = owner[:6] if len(owner) <= 6 else owner[:5]
        while True:
            count[prefix] = count.get(prefix, 0) + 1
            name = f"{prefix}{count[prefix]}"
            if len(name) > 8:
                prefix = prefix[:-1]
                continue
            if name not in used:
                break
        labels[addr] = name
        used.add(name)


def _data_items(first: int, last: int, kind: str, comment: str) -> list[Item]:
    out: list[Item] = []
    raw = DATA[first - LIB:last - LIB + 1]
    if kind.startswith("code-at="):
        base = int(kind.split("=")[1][1:], 16)
        a = 0
        while a < len(raw):
            i = m6502.decode(raw, base, base + a)
            text = m6502.fmt(i, {}).split("  ", 1)[-1].strip() if False else _plain(i)
            out.append(Item(first + a, i.length, "DFB", ",".join(f"${b:02X}" for b in i.raw), f"${base + a:02X}: {text}"))
            a += i.length
        out[0].comment = out[0].comment
        return out
    for k in range(0, len(raw), 8):
        chunk = raw[k:k + 8]
        txt = "".join(chr(c & 0x7F) if 32 <= (c & 0x7F) < 127 else "." for c in chunk)
        note = f'"{txt}"' if kind == "text" else ""
        out.append(Item(first + k, len(chunk), "DFB", ",".join(f"${b:02X}" for b in chunk), note))
    return out


def _plain(i: m6502.Insn) -> str:
    fmt = m6502.MODES[i.mode][1]
    if i.operand is None:
        return i.mnemonic + (" A" if i.mode == "acc" else "")
    return f"{i.mnemonic} {fmt.format(i.operand)}"


EQ: dict[int, str] = {}
EQ_SORTED: list[tuple[int, str]] = []


def _sym(v: int, labels: dict[int, str]) -> str:
    if LIB <= v < END:
        if v in labels:
            return labels[v]
        base = max(a for a in labels if a < v)
        return f"{labels[base]}+{v - base}"
    if v in EQ:
        return EQ[v]
    # name+offset within a few bytes of an equate on the same page
    near = [(a, n) for a, n in EQ_SORTED if a <= v and v - a <= 5 and (a >> 8) == (v >> 8)]
    if near:
        a, n = near[-1]
        return f"{n}+{v - a}"
    return f"${v:02X}" if v < 0x100 else f"${v:04X}"


def _insn_item(i: m6502.Insn, labels: dict[int, str]) -> Item:
    mn, mode, v = i.mnemonic, i.mode, i.operand
    if mode in ("imp", "acc"):
        return Item(i.addr, i.length, mn, "")
    if mode == "imm":
        assert v is not None
        return Item(i.addr, i.length, mn, f"#${v:02X}")
    assert v is not None
    zp_form = {"abs": "zp", "abx": "zpx", "aby": "zpy"}.get(mode)
    if zp_form and v < 0x100 and zp_form in edasm.TABLE[mn]:
        # EDASM would choose the zero-page form: keep the bytes
        return Item(i.addr, i.length, "DFB", ",".join(f"${b:02X}" for b in i.raw),
                    f"{mn} {m6502.MODES[mode][1].format(v)} (ABSOLUTE ON PURPOSE)")
    s = _sym(v, labels)
    fmt = {"zp": "{}", "abs": "{}", "rel": "{}", "zpx": "{},X", "abx": "{},X", "zpy": "{},Y", "aby": "{},Y",
           "izx": "({},X)", "izy": "({}),Y", "ind": "({})"}[mode]
    return Item(i.addr, i.length, mn, fmt.format(s))


@dataclass
class Row:
    kind: str  # head, equ, org, block, code
    text: str  # the source line (or comment block line)
    addr: int = -1
    raw: bytes = b""
    label: str = ""
    op: str = ""
    operand: str = ""
    comment: str = ""


def rows(ann: Ann) -> tuple[list[Row], dict[int, str]]:
    """The source, line by line, with what each line is."""
    global EQ, EQ_SORTED
    EQ = {v: n for n, v, _ in ann.equates}
    EQ_SORTED = sorted(EQ.items())
    items, labels = build_items(ann)
    out = [Row("head", s) for s in _header()]
    out += [Row("head", s) for s in ("*", "* PAGE ZERO, MEMORY AND ROM ADDRESSES", "*")]
    for name, v, comment in ann.equates:
        val = f"${v:02X}" if v < 0x100 else f"${v:04X}"
        out.append(Row("equ", _line(name, "EQU", val, comment), v, b"", name, "EQU", val, comment))
    out.append(Row("head", "*"))
    out.append(Row("org", _line("", "ORG", "$0803", "THE LIBRARY'S USUAL ADDRESS"), LIB, b"", "", "ORG", "$0803",
                   "THE LIBRARY'S USUAL ADDRESS"))
    for it in items:
        if it.addr in ann.routines:
            block = ["*", "*" + "-" * 38]
            for para in ann.routines[it.addr].split("|"):
                block += ["* " + w for w in _wrap(para.strip(), 66)]
            block.append("*" + "-" * 38)
            out += [Row("block", s, it.addr) for s in block]
        comment = ann.lines.get(it.addr, it.comment)
        if it.comment and it.addr in ann.lines:
            comment = f"{it.comment}; {ann.lines[it.addr]}"
        label = labels.get(it.addr, "")
        out.append(Row("code", _line(label, it.op, it.operand, comment), it.addr,
                       DATA[it.addr - LIB:it.addr - LIB + it.size], label, it.op, it.operand, comment))
    return out, labels


def render(ann: Ann) -> str:
    return "\n".join(r.text for r in rows(ann)[0]) + "\n"


PART_LIMIT = 12 * 1024  # bytes per source file, so each one fits the editor's buffer
PART_DIR = ROOT / "src" / "runtime"


def parts(ann: Ann) -> list[tuple[str, str, int, int]]:
    """The source split for EDASM: (file name, text, first address, last address). Single
    spaced, cut only where a routine's comment block begins, each file at most PART_LIMIT
    bytes; every file but the last ends with CHN and the next file's name."""
    rs, _ = rows(ann)
    segments: list[list[Row]] = [[]]
    for k, r in enumerate(rs):
        starts_block = r.kind == "block" and (k == 0 or rs[k - 1].kind != "block") and r.addr > LIB
        if starts_block and any(x.kind == "code" for x in segments[-1]):
            segments.append([])
        segments[-1].append(r)
    groups: list[list[Row]] = [[]]
    size = 0
    for seg in segments:
        seg_size = len(compact("\n".join(r.text for r in seg)))
        if groups[-1] and size + seg_size + 200 > PART_LIMIT:
            groups.append([])
            size = 0
        groups[-1] += seg
        size += seg_size
    n = len(groups)
    out = []
    for i, g in enumerate(groups, 1):
        codes = [r for r in g if r.kind == "code"]
        first, last = codes[0].addr, codes[-1].addr + len(codes[-1].raw) - 1
        name = f"RUNTIME.S{i}"
        head = [f"* {name}: PART {i} OF {n} OF THE RUNTIME SOURCE, ${first:04X}-${last:04X}",
                f"* ASSEMBLE RUNTIME.S1; EACH PART CHAINS TO THE NEXT WITH CHN"]
        body = compact("\n".join(r.text for r in g))
        tail = f" CHN RUNTIME.S{i + 1}\n" if i < n else ""
        out.append((name, "\n".join(head) + "\n" + body + tail, first, last))
    return out


def compact(text: str) -> str:
    """The same source with single spaces between the fields, as kept on disk."""
    out = []
    for line in text.splitlines():
        if not line.strip() or line.startswith("*"):
            out.append(line)
            continue
        code, sep, comment = line.partition(";")
        fields = code.split()
        label = "" if line[0] == " " else fields.pop(0)
        s = label + " " + " ".join(fields)
        out.append(s + (" ;" + comment.strip() if sep else ""))
    return "\n".join(out) + "\n"


def _header() -> list[str]:
    return [
        "*" * 40,
        "*",
        "* RUNTIME",
        "* THE LIBRARY OF THE TASC COMPILER, VERSION 2.01",
        "* COPYRIGHT (C) 1981 MICROSOFT",
        "*",
        "* COMPILED PROGRAMS CALL THESE ROUTINES FOR ALMOST EVERY",
        "* STATEMENT. IT LOADS AT $0803 BY DEFAULT ($0803-$17AF,",
        "* 4013 BYTES).",
        "*",
        "*" * 40,
    ]


def _wrap(text: str, width: int) -> list[str]:
    words, lines, cur = text.split(), [], ""
    for w in words:
        if cur and len(cur) + 1 + len(w) > width:
            lines.append(cur)
            cur = w
        else:
            cur = f"{cur} {w}" if cur else w
    return lines + ([cur] if cur else [])


def _line(label: str, op: str, operand: str, comment: str) -> str:
    s = f"{label:<9}{op:<5}{operand}"
    if comment:
        s = f"{s:<{WIDTH}} ;{comment}" if len(s) < WIDTH else f"{s} ;{comment}"
    return s.rstrip()


def check(text: str, load: Callable[[str], str] | None = None) -> list[str]:
    org, data, _ = edasm.assemble(text, load)
    problems = []
    if org != LIB:
        problems.append(f"ORG ${org:04X}")
    if data != DATA:
        off = next((k for k in range(min(len(data), len(DATA))) if data[k] != DATA[k]), None)
        problems.append(f"{len(data)} bytes, first difference at {off if off is None else f'${LIB + off:04X}'}")
    return problems


def addressed() -> list[str]:
    """The code lines with their addresses in front (for writing annotations)."""
    ann = load()
    global EQ, EQ_SORTED
    EQ = {v: n for n, v, _ in ann.equates}
    EQ_SORTED = sorted(EQ.items())
    items, labels = build_items(ann)
    return [f"${it.addr:04X} {'R' if it.addr in ann.routines else ' '}{'L' if it.addr in ann.lines else ' '} "
            + _line(labels.get(it.addr, ''), it.op, it.operand, it.comment) for it in items]


def main() -> None:
    import sys
    if "--addr" in sys.argv:
        print("\n".join(addressed()))
        return
    ann = load()
    text = render(ann)
    OUT.write_text(text)
    for name, src in (("src/RUNTIME.S", text), ("the disk copy (single-spaced)", compact(text))):
        problems = check(src)
        print(f"{name}: {src.count(chr(10))} lines, {len(src)} characters;",
              "assembles to RUNTIME byte for byte" if not problems else "DIFFERS: " + "; ".join(problems))
    pieces = parts(ann)
    PART_DIR.mkdir(exist_ok=True)
    for old in PART_DIR.glob("RUNTIME.S*"):
        old.unlink()
    files = {name: text for name, text, _, _ in pieces}
    for name, text in files.items():
        (PART_DIR / name).write_text(text)
    problems = check(files["RUNTIME.S1"], files.__getitem__)
    print(f"src/runtime/: {len(pieces)} files of at most {max(len(x) for x in files.values())} characters;",
          "the chain assembles to RUNTIME byte for byte" if not problems else "DIFFERS: " + "; ".join(problems))
    from tasc import docview
    docview.write_runtime(*rows(ann), ann, [(n, len(x), f, l) for n, x, f, l in pieces])


if __name__ == "__main__":
    main()
