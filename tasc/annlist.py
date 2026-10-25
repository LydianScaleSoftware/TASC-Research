"""Address-keyed listing of a generated pass, for writing annotations.

    python -m tasc.annlist PASS1 [FIRST [LAST]]     lines FIRST..LAST (line numbers)

Each line is printed as `$addr  number  text`, with every variable written as its
preferred annotation name in braces ({T}, {SY}(...)), the form [lines] and [routines]
entries use.  Lines that already carry a routine or line comment are marked R or L.
"""

from __future__ import annotations

import re
import sys

from tasc.decomp.decompile import decompile_many, pass_units
from tasc.decomp.render import listing
from tasc.sourcegen import annotations, configure


def main(argv: list[str]) -> None:
    unit = argv[0] if argv else "PASS1"
    lo = int(argv[1]) if len(argv) > 1 else 0
    hi = int(argv[2]) if len(argv) > 2 else 99999
    units = pass_units()
    annots = {u.name: annotations(u.name) for u in units}
    for u in units:
        configure(u, annots[u.name])
    decompile_many(units)
    u = next(x for x in units if x.name == unit)
    a = annots[unit]
    # final name (with array marker) -> preferred name
    back: dict[tuple[str, bool], str] = {}
    for s, n in u.names.items():
        if s.addr in a.names:
            back[(n, s.array)] = a.names[s.addr][0]
    ident = re.compile(r'"[^"]*"?|\bFN [A-Z][A-Z0-9]?|(?<![A-Z0-9])([A-Z][A-Z0-9]?[$%]?)(?![A-Z0-9])(\()?')

    def sub(text: str) -> str:
        if text.lstrip().startswith(("REM", "DATA")):
            return text
        def one(m: re.Match[str]) -> str:
            if m.group(1) is None:
                return m.group(0)
            name, paren = m.group(1), m.group(2) or ""
            p = back.get((name, bool(paren)))
            return f"{{{p}}}{paren}" if p else m.group(0)
        return ident.sub(one, text)

    num_addr = dict(u.line_addr)
    for row in listing(u.decl_lines + u.body_lines).splitlines():
        num = int(row.split(" ", 1)[0])
        if not lo <= num <= hi:
            continue
        addr = num_addr.get(num)
        mark = ("R" if addr in a.routines else " ") + ("L" if addr in a.lines else " ")
        text = row.split(" ", 1)[1]
        print(f"${addr:04X} {mark} {num:>5} {sub(text)}" if addr is not None else f"      {mark} {num:>5} {text}")


if __name__ == "__main__":
    main(sys.argv[1:])
