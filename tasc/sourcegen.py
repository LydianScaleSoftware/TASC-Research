"""Phase 5: generate TASC's recovered source with names, numbering and documentation.

    python -m tasc.sourcegen        write src/PASSn.bas (tokenized), PASSn.txt (listing),
                                     PASSn.DOC.TXT and PASSn.VARS.TXT; check each recompiles

Annotations (development files, docs/lift/annot/*.ann, keyed by address) give each
variable a preferred name, a declaration group and a meaning, each DEF FN a name, and
routines and lines their comments.  Names fall back as the hash order requires (the
VARS file records the preferred name beside a fallback).  The DOC and VARS text is
standalone period documentation; {NAME} in an annotation is replaced by the name the
variable finally got.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from tasc import docview
from tasc.compiler.assemble import compile_program
from tasc.decomp.decompile import Unit, compare, decompile_many, pass_units
from tasc.decomp.render import listing
from tasc.decomp.walk import Sym

ROOT = Path(__file__).resolve().parents[1]
ANNOT = ROOT / "docs" / "lift" / "annot"
SRC = ROOT / "src"


@dataclass
class Annotations:
    names: dict[int, tuple[str, str, str]] = field(default_factory=dict)  # addr -> (name, group, meaning)
    fns: dict[int, tuple[str, str, str]] = field(default_factory=dict)  # body addr -> (name, param, meaning)
    routines: dict[int, str] = field(default_factory=dict)
    lines: dict[int, str] = field(default_factory=dict)
    groups: list[str] = field(default_factory=list)  # in order of first appearance


def load(path: Path, into: Annotations | None = None) -> Annotations:
    a = into or Annotations()
    if not path.exists():
        return a
    section = ""
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1]
            continue
        m = re.match(r"\$([0-9A-Fa-f]{4})\s+(.*)$", line)
        if m is None:
            raise ValueError(f"{path.name}: bad line {raw!r}")
        addr, rest = int(m.group(1), 16), m.group(2)
        if section == "names":
            name, group, meaning = rest.split(None, 2)
            a.names[addr] = (name, group, meaning)
            if group not in a.groups:
                a.groups.append(group)
        elif section == "fns":
            name, param, meaning = rest.split(None, 2)
            a.fns[addr] = (name, param, meaning)
        elif section == "routines":
            a.routines[addr] = rest
        elif section == "lines":
            a.lines[addr] = rest
        else:
            raise ValueError(f"{path.name}: line outside a section")
    return a


def annotations(unit: str) -> Annotations:
    a = load(ANNOT / "COMMON.ann")
    return load(ANNOT / f"{unit}.ann", a)


def configure(u: Unit, a: Annotations) -> None:
    for addr, (name, group, _) in a.names.items():
        base = name.rstrip("$%")
        u.prefs[addr] = (base, a.groups.index(group))
    for addr, (name, param, _) in a.fns.items():
        u.fn_prefs[addr] = name
        u.param_prefs[addr] = param
    u.numbering = "routines"


def generate() -> list[Unit]:
    units = pass_units()
    annots = {u.name: annotations(u.name) for u in units}
    for u in units:
        configure(u, annots[u.name])
    decompile_many(units)
    for u in units:
        write(u, annots[u.name])
    return units


# ---------------------------------------------------------------- documentation

def _subst(text: str, final: dict[str, str]) -> str:
    def one(m: re.Match[str]) -> str:
        key = m.group(1)
        if key not in final:
            raise ValueError(f"unknown name {{{key}}} in an annotation")
        return final[key]
    return re.sub(r"\{([A-Z][A-Z0-9]?\$?)\}", one, text)


def _first_definitions(u: Unit) -> dict[Sym, int]:
    """Line number where each variable is first defined: its declaration line (INTEGER,
    COMMON, DIM) or the first line that stores it."""
    out: dict[Sym, int] = {}
    names = u.names
    for num, body in u.decl_lines:
        text = body.decode("latin-1")
        for s, n in names.items():
            if s not in out and re.search(rf"(?<![A-Z0-9]){re.escape(n)}(?![A-Z0-9%$])", text.split("! ", 1)[-1] if "!" in text else text[1:]):
                out[s] = num
    addr_line = sorted((a, n) for n, a in u.line_addr.items())
    import bisect
    keys = [a for a, _ in addr_line]
    for o in u.lifted.walk.ops:
        s = o.sym
        if s is None or s in out or s not in names:
            continue
        stores = (o.kind == "ent" and o.op in (1, 7)) or (o.kind == "rt" and o.name in ("FOR.INIT", "IFOR.INIT"))
        if stores:
            i = bisect.bisect_right(keys, o.addr) - 1
            if i >= 0:
                out[s] = addr_line[i][1]
    return out


def write(u: Unit, a: Annotations) -> None:
    lf = u.lifted
    w = lf.walk
    final: dict[str, str] = {}
    meaning: dict[Sym, str] = {}
    pref_of: dict[Sym, str] = {}
    for s, n in u.names.items():
        if s.addr in a.names:
            pname, _, mean = a.names[s.addr]
            key = pname if not s.array else pname
            final.setdefault(key, n)
            meaning[s] = mean
            pref_of[s] = pname
    fn_name = {f.addr: u.fn_prefs.get(f.addr, "") for f in lf.fns.values()}
    first = _first_definitions(u)
    doc: list[str] = []
    lines = u.decl_lines + u.body_lines
    num_addr = dict(u.line_addr)
    by_line: dict[int, list[Sym]] = {}
    for s, ln in first.items():
        by_line.setdefault(ln, []).append(s)
    decl_nums = {n for n, _ in u.decl_lines}
    page_entries: dict[int, list[tuple[str, str]]] = {}
    sections: dict[int, str] = {}
    for num, body in lines:
        entries: list[tuple[str, str]] = []
        addr = num_addr.get(num)
        if num in decl_nums:
            txt = body.decode("latin-1")
            if "COMMON" in txt[:14]:
                entries.append(("decl", "COMMON BLOCK, IN THE ORDER IT IS LAID OUT: NUMBERS FIRST, THEN STRINGS. "
                                        "THE PASSES SHARE IT, SO EVERY PASS DECLARES IT THE SAME WAY"))
            elif "INTEGER" in txt[:14]:
                entries.append(("decl", "INTEGER VARIABLES"))
            else:
                entries.append(("decl", "ARRAYS"))
        if addr is not None and addr in a.routines:
            sections[num] = _subst(a.routines[addr], final)
            entries.append(("routine", sections[num]))
        if addr is not None and addr in a.lines:
            entries.append(("line", _subst(a.lines[addr], final)))
        for f in lf.fns.values():  # DEF FN lines
            if addr is not None and f.addr - 3 == addr and f.addr in a.fns:
                nm, param, mean = a.fns[f.addr]
                entries.append(("fn", f"FN {nm}({param}): {_subst(mean, final)}"))
        for s in sorted(by_line.get(num, []), key=lambda s: u.names[s]):
            if s in meaning and not (num in decl_nums and "COMMON" in body.decode("latin-1")[:14]
                                     and s.region == "common" and s.vtype != "str" and first.get(s) != num):
                entries.append(("var", f"{u.names[s]}{'()' if s.array else ''} IS {_subst(meaning[s], final)}"))
        if not entries:
            doc.append(f"{num} REM")
        for _, e in entries:
            doc.append(f"{num} REM {e}")
        page_entries[num] = entries
    # variable compendium
    report: list[str] = []  # development side: preferred name -> name the hash order allowed
    vars_: list[str] = [f"{'NAME':<11}{'TYPE':<11}{'DEFINED':<9}{'COMMON':<8}MEANING"]
    common = sorted((s for s in w.syms.values() if s.region == "common"), key=lambda s: s.addr)
    slot = {s: i + 1 for i, s in enumerate(common)}
    for s in sorted(u.names, key=lambda s: (u.names[s].rstrip("%$"), s.vtype, s.array)):
        n = u.names[s] + ("(" + ",".join(map(str, s.dims)) + ")" if s.array else "")
        ty = {"int": "INTEGER", "real": "REAL", "str": "STRING"}[s.vtype] + ("()" if s.array else "")
        note = meaning.get(s, "")
        if s in pref_of and pref_of[s].rstrip("$") != u.names[s].rstrip("%$"):
            report.append(f"{pref_of[s]:<5} -> {u.names[s]}")
        vars_.append(f"{n:<11}{ty:<11}{first.get(s, ''):<9}{slot.get(s, ''):<8}{_subst(note, final)}".rstrip())
    params_seen: set[str] = set()
    for f in sorted(lf.fns.values(), key=lambda f: f.addr):
        nm, param, mean = a.fns.get(f.addr, (fn_name[f.addr], "", ""))
        vars_.append(f"{'FN ' + nm:<11}{'REAL':<11}{'':<9}{'':<8}{_subst(mean, final)}".rstrip())
        params_seen.add(u.param_prefs.get(f.addr, ""))
    for pm in sorted(x for x in params_seen if x):
        vars_.append(f"{pm:<11}{'REAL':<11}{'':<9}{'':<8}PARAMETER OF THE DEF FN FUNCTIONS (EACH FUNCTION HAS ITS OWN)")
    SRC.mkdir(exist_ok=True)
    (SRC / f"{u.name}.bas").write_bytes(u.program)
    (SRC / f"{u.name}.txt").write_text(listing(lines))
    (SRC / f"{u.name}.DOC.TXT").write_text("\n".join(doc) + "\n")
    (SRC / f"{u.name}.VARS.TXT").write_text("\n".join(vars_) + "\n")
    _write_html(u, lines, page_entries, sections, final, meaning, a, vars_)
    (ANNOT / f"{u.name}.names.txt").write_text(
        "# preferred name -> name the storage (hash) order allowed; generated by tasc.sourcegen\n"
        + "\n".join(sorted(report)) + "\n")


def _write_html(u: Unit, lines: list[tuple[int, bytes]], entries: dict[int, list[tuple[str, str]]],
                sections: dict[int, str], final: dict[str, str], meaning: dict[Sym, str], a: Annotations,
                vars_: list[str]) -> None:
    rows = listing(lines).splitlines()
    page = docview.Page(u.name, [(int(r.split(" ", 1)[0]), r.split(" ", 1)[1]) for r in rows], entries)
    page.sections = dict(sections)
    page.sections.setdefault(lines[0][0], "DECLARATIONS: INTEGER VARIABLES, ARRAYS AND THE COMMON BLOCK")
    ty = {"int": "INTEGER", "real": "REAL", "str": "STRING"}
    for s, n in u.names.items():
        page.names[(n, s.array)] = f"{ty[s.vtype]}{' ARRAY' if s.array else ''}: {_subst(meaning.get(s, ''), final)}"
    for f in u.lifted.fns.values():
        if f.addr in a.fns:
            nm, param, mean = a.fns[f.addr]
            page.fns[nm] = f"FN {nm}({param}): {_subst(mean, final)}"
    widths = (11, 11, 9, 8)
    for r in vars_:
        cells, pos = [], 0
        for wd in widths:
            cells.append(r[pos:pos + wd].strip())
            pos += wd
        cells.append(r[pos:].strip())
        page.vars_rows.append(cells)
    tmpl = ANNOT / f"{u.name}.overview.txt"
    overview = None
    if tmpl.exists():
        addr_line = {ad: n for n, ad in u.line_addr.items()}
        overview = docview.fill(tmpl.read_text(), final, addr_line, f"{u.name}.html")
    docview.write_page(page, overview)


def main() -> None:
    units = generate()
    for u in units:
        fallbacks = sum(1 for s, n in u.names.items() if s.addr in u.prefs and u.prefs[s.addr][0] != n.rstrip("%$"))
        lines = [n for n, _ in u.decl_lines + u.body_lines]
        print(f"{u.name}: {compare(u)}, {len(lines)} lines up to {lines[-1]}, "
              f"{len(u.prefs)} preferred names, {fallbacks} fallbacks")
        assert compile_program(u.program, u.opts).data == u.data


if __name__ == "__main__":
    main()
