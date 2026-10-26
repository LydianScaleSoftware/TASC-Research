"""HTML views of the recovered sources: an annotated listing and an overview per program.

    python -m tasc.docview          write src/html/ from the files in src/ (MAKE RUNTIME;
                                    the passes are written by tasc.sourcegen)

The listing groups the program into sections (routines); each section's comment stands
above it and each line's comments beside it.  Variables show their meaning when pointed
at, and line numbers after GOTO, GOSUB, THEN and ON lists are links.  The overview is
written by hand (docs/lift/annot/<PASS>.overview.txt, a small Markdown dialect) with
{NAME} for a variable's name and [[$addr]] for "line N" (a link into the listing) of the
line that starts at an object address; both are filled in when the page is written, so
the text follows renaming and renumbering.  Like the DOC and VARS files, the pages are
standalone period documentation.
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
OUT = SRC / "html"

TITLES = {"PASS0": "PASS0", "PASS1": "PASS1", "PASS2": "PASS2", "MAKE_RUNTIME": "MAKE RUNTIME", "RUNTIME": "RUNTIME"}
PURPOSE = {
    "PASS0": "Pass 0: dialog, DOS patches, tables, then runs pass 1",
    "PASS1": "Pass 1: parsing, symbol table and code generation",
    "PASS2": "Pass 2: constants, variable routines, backpatching, header and report",
    "MAKE_RUNTIME": "Builds the RUNTIME library file from DATA statements",
    "RUNTIME": "The machine language library compiled programs call (6502 source)",
}


@dataclass
class Page:
    name: str
    lines: list[tuple[int, str]]  # (number, listing text)
    entries: dict[int, list[tuple[str, str]]] = field(default_factory=dict)  # number -> (kind, text)
    sections: dict[int, str] = field(default_factory=dict)  # first line number -> title
    names: dict[tuple[str, bool], str] = field(default_factory=dict)  # (name, array) -> tooltip
    fns: dict[str, str] = field(default_factory=dict)  # FN name -> tooltip
    vars_rows: list[list[str]] = field(default_factory=list)  # compendium rows (header first)
    collapse: set[int] = field(default_factory=set)  # sections shown folded (long DATA blocks)


CSS = """
:root{--bg:#fbfaf7;--fg:#1d1d1b;--muted:#6b6a64;--line:#e4e1d8;--code:#f2efe7;--sect:#eef3f8;
--accent:#1f5f99;--kw:#7a3e00;--str:#2f6b2f;--num:#555;--rem:#8a4a8a;--hl:#fff3b0}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){--bg:#161615;--fg:#e8e6e0;
--muted:#9a978e;--line:#2f2e2a;--code:#1f1e1c;--sect:#1b2430;--accent:#7fb2e5;--kw:#e0a060;
--str:#8fc98f;--num:#b0aea8;--rem:#d0a0d0;--hl:#4a4320}}
:root[data-theme="dark"]{--bg:#161615;--fg:#e8e6e0;--muted:#9a978e;--line:#2f2e2a;--code:#1f1e1c;
--sect:#1b2430;--accent:#7fb2e5;--kw:#e0a060;--str:#8fc98f;--num:#b0aea8;--rem:#d0a0d0;--hl:#4a4320}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 -apple-system,"Segoe UI",Helvetica,Arial,sans-serif}
main{max-width:1180px;margin:0 auto;padding:16px}
header.top{display:flex;flex-wrap:wrap;gap:8px 20px;align-items:baseline;border-bottom:1px solid var(--line);padding-bottom:8px}
header.top h1{font-size:22px;margin:0}
header.top nav a{margin-right:14px}
a{color:var(--accent);text-decoration:none}a:hover{text-decoration:underline}
.muted{color:var(--muted)}
details.toc{margin:12px 0;border:1px solid var(--line);border-radius:6px;padding:6px 10px;background:var(--code)}
details.toc ol{columns:2 320px;margin:6px 0;padding-left:22px;font-size:13px}
section.r{margin:18px 0;border:1px solid var(--line);border-radius:6px;overflow:hidden}
section.r>.h{background:var(--sect);padding:8px 12px;border-bottom:1px solid var(--line)}
section.r>.h p{margin:2px 0}
section.r>.h .ln{font:600 13px ui-monospace,Menlo,Consolas,monospace;color:var(--muted);margin-right:8px}
.row{display:grid;grid-template-columns:minmax(0,1.15fr) minmax(0,1fr);border-top:1px solid var(--line)}
.row:first-child{border-top:0}
.src{font:13px/1.45 ui-monospace,Menlo,Consolas,monospace;padding:3px 10px;background:var(--code);white-space:pre-wrap;overflow-wrap:anywhere}
.src .n{display:inline-block;min-width:3.6em;color:var(--muted)}
.cm{padding:3px 10px;font-size:13px;color:var(--fg)}
.cm p{margin:0}.cm p.v{color:var(--muted)}.cm p.d{color:var(--muted);font-style:italic}
.k{color:var(--kw);font-weight:600}.s{color:var(--str)}.r{color:var(--rem)}
abbr{text-decoration:underline dotted;cursor:help}
.row:target,.row.hl{background:var(--hl)}.row:target .src{background:var(--hl)}
details.fold>summary{padding:6px 12px;cursor:pointer;color:var(--muted);font-size:13px}
table.vars{border-collapse:collapse;width:100%;font-size:13px}
table.vars th,table.vars td{border-bottom:1px solid var(--line);padding:4px 6px;text-align:left;vertical-align:top}
table.vars td:first-child{font-family:ui-monospace,Menlo,Consolas,monospace;white-space:nowrap}
.foot{margin-top:32px;padding-top:10px;border-top:1px solid var(--line);font-size:12.5px;color:var(--muted)}
.notice{margin-top:28px;border:1px solid var(--line);border-radius:6px;padding:4px 14px;background:var(--code);max-width:860px}
.notice h2{font-size:16px;margin:10px 0 4px}
.notice p{font-size:14px}
.ov{max-width:860px}
.ov td a{white-space:nowrap}
table.asm{border-collapse:collapse;width:100%;font:12.5px/1.45 ui-monospace,Menlo,Consolas,monospace}
table.asm td{padding:1px 6px;vertical-align:top;white-space:pre}
table.asm td.a{color:var(--muted)}table.asm td.b{color:var(--muted)}
table.asm td.l{color:var(--accent);font-weight:600}table.asm td.o{color:var(--kw);font-weight:600}
table.asm td.c{white-space:pre-wrap;font-family:-apple-system,"Segoe UI",Helvetica,Arial,sans-serif;font-size:12.5px}
table.asm tr:target td,table.asm tr.hl td{background:var(--hl)}
.wrap{overflow-x:auto}
.ov h2{margin-top:28px;border-bottom:1px solid var(--line);padding-bottom:4px}
.ov code,.ov pre{font-family:ui-monospace,Menlo,Consolas,monospace;background:var(--code);border-radius:4px}
.ov code{padding:1px 4px;font-size:13px}.ov pre{padding:10px;overflow-x:auto;font-size:13px}
.ov table{border-collapse:collapse;margin:8px 0;font-size:14px}
.ov th,.ov td{border:1px solid var(--line);padding:4px 8px;text-align:left;vertical-align:top}
@media (max-width:760px){.row{grid-template-columns:1fr}.cm{padding-left:22px}}
"""

KEYWORDS = sorted(
    "END FOR NEXT DATA INPUT DEL DIM READ GR TEXT PR# IN# CALL PLOT HLIN VLIN HGR2 HGR HCOLOR= HPLOT DRAW XDRAW "
    "HTAB HOME ROT= SCALE= SHLOAD TRACE NOTRACE NORMAL INVERSE FLASH COLOR= POP VTAB HIMEM: LOMEM: ONERR RESUME "
    "RECALL STORE SPEED= LET GOTO RUN IF RESTORE GOSUB RETURN REM STOP ON WAIT LOAD SAVE DEF POKE PRINT CONT LIST "
    "CLEAR GET NEW TAB( TO FN SPC( THEN AT NOT STEP AND OR SGN INT ABS USR FRE SCRN( PDL POS SQR RND LOG EXP COS "
    "SIN TAN ATN PEEK LEN STR$ VAL ASC CHR$ LEFT$ RIGHT$ MID$".split(), key=len, reverse=True)
_kw = "|".join(re.escape(k) for k in KEYWORDS)
_TOKEN = re.compile(rf'(?P<str>"[^"]*"?)|(?P<fn>\bFN [A-Z][A-Z0-9]?)|(?P<kw>(?<![A-Z0-9])(?:{_kw}))'
                    rf'|(?P<id>(?<![A-Z0-9])[A-Z][A-Z0-9]?[$%]?(?![A-Z0-9]))(?P<par>\()?')
_JUMP = re.compile(r"\b(GOTO|GOSUB|THEN) (\d+(?:,\d+)*)")


FOOTER = ('<footer class="foot">TASC and RUNTIME are copyright &copy; 1981 Microsoft. Shown for educational and '
          'historical purposes only; see the <a href="index.html#copyright">copyright and use notice</a>.</footer>')


def _anchor(num: int) -> str:
    return f"L{num}"


def render_code(text: str, page: Page, numbers: set[int]) -> str:
    """One listing line as HTML: keywords, strings, names with their meanings, jump links."""
    if text.startswith(("REM", "DATA")):
        kw = text.split(" ", 1)[0]
        rest = text[len(kw):]
        cls = "r" if kw == "REM" else "num"
        return f'<span class="k">{kw}</span><span class="{cls}">{html.escape(rest)}</span>'
    # jump targets become placeholders first so the number links survive the tokenising
    links: list[str] = []

    def jump(m: re.Match[str]) -> str:
        parts = []
        for t in m.group(2).split(","):
            n = int(t)
            target = f'<a href="#{_anchor(n)}">{n}</a>' if n in numbers else str(n)
            links.append(target)
            parts.append(f"\x00{len(links) - 1}\x00")
        return f"{m.group(1)} " + ",".join(parts)

    text = _JUMP.sub(jump, text)
    out: list[str] = []
    pos = 0
    for m in _TOKEN.finditer(text):
        out.append(html.escape(text[pos:m.start()]))
        pos = m.end()
        if m.group("str"):
            out.append(f'<span class="s">{html.escape(m.group("str"))}</span>')
        elif m.group("fn"):
            nm = m.group("fn")[3:]
            tip = page.fns.get(nm)
            body = f'<span class="k">FN</span> {nm}'
            out.append(f'<abbr title="{html.escape(tip)}">{body}</abbr>' if tip else body)
        elif m.group("kw"):
            out.append(f'<span class="k">{html.escape(m.group("kw"))}</span>')
        else:
            nm, par = m.group("id"), m.group("par") or ""
            tip = page.names.get((nm, bool(par)))
            out.append((f'<abbr title="{html.escape(tip)}">{nm}</abbr>' if tip else nm) + par)
    out.append(html.escape(text[pos:]))
    res = "".join(out)
    return re.sub("\x00(\\d+)\x00", lambda m: links[int(m.group(1))], res)


def _head(title: str, desc: str) -> str:
    return (f'<!doctype html>\n<html lang="en"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>{html.escape(title)}</title><meta name="description" content="{html.escape(desc)}">'
            f"<style>{CSS}</style></head><body><main>\n")


def _nav(name: str, here: str) -> str:
    t = TITLES[name]
    links = [("index.html", "All programs"), (f"{name}.html", f"{t} listing"), (f"{name}.OVERVIEW.html", f"{t} overview")]
    nav = " ".join(f'<a href="{h}">{html.escape(x)}</a>' if h != here else f"<strong>{html.escape(x)}</strong>"
                   for h, x in links)
    return f'<header class="top"><h1>{html.escape(t)}</h1><nav>{nav}</nav></header>\n'


def listing_html(page: Page) -> str:
    numbers = {n for n, _ in page.lines}
    starts = sorted(page.sections)
    if not starts or starts[0] != page.lines[0][0]:
        starts.insert(0, page.lines[0][0])
        page.sections.setdefault(page.lines[0][0], "")
    groups: list[tuple[int, list[tuple[int, str]]]] = []
    for num, text in page.lines:
        if num in page.sections:
            groups.append((num, []))
        groups[-1][1].append((num, text))
    title = TITLES[page.name]
    parts = [_head(f"{title} listing", PURPOSE[page.name]), _nav(page.name, f"{page.name}.html")]
    parts.append(f'<p class="muted">{html.escape(PURPOSE[page.name])}. '
                 "Each section's comment stands above it, each line's comments beside it; point at a name "
                 "for its meaning; line numbers after GOTO, GOSUB and THEN are links.</p>\n")
    toc = []
    for num, _ in groups:
        t = page.sections.get(num, "") or "(declarations)"
        first = t.split(":")[0] if len(t) > 70 else t
        toc.append(f'<li><a href="#{_anchor(num)}">{num}</a> {html.escape(first[:90])}</li>')
    parts.append(f'<details class="toc" open><summary>Sections ({len(groups)})</summary><ol>{"".join(toc)}</ol></details>\n')
    for num, rows in groups:
        head = page.sections.get(num, "")
        hs = f'<div class="h"><p><span class="ln">{num}</span>{html.escape(head)}</p></div>' if head else ""
        body = []
        for n, text in rows:
            ents = [e for e in page.entries.get(n, []) if not (n == num and e[1] == head)]
            cm = "".join(f'<p class="{ {"var": "v", "decl": "d"}.get(k, "")}">{html.escape(t)}</p>' for k, t in ents)
            body.append(f'<div class="row" id="{_anchor(n)}"><div class="src"><span class="n">{n}</span>'
                        f'{render_code(text, page, numbers)}</div><div class="cm">{cm}</div></div>')
        inner = "".join(body)
        if num in page.collapse:
            inner = f'<details class="fold"><summary>{len(rows)} lines</summary>{inner}</details>'
        parts.append(f'<section class="r">{hs}{inner}</section>\n')
    if page.vars_rows:
        hdr, *rows_ = page.vars_rows
        th = "".join(f"<th>{html.escape(h)}</th>" for h in hdr)
        trs = []
        for r in rows_:
            cells = []
            for i, c in enumerate(r):
                if i == 2 and c.isdigit() and int(c) in numbers:
                    cells.append(f'<td><a href="#{_anchor(int(c))}">{c}</a></td>')
                else:
                    cells.append(f"<td>{html.escape(c)}</td>")
            trs.append("<tr>" + "".join(cells) + "</tr>")
        parts.append(f'<h2 id="vars">Variables</h2><table class="vars"><tr>{th}</tr>{"".join(trs)}</table>\n')
    parts.append(FOOTER + "</main></body></html>\n")
    return "".join(parts)


# ---------------------------------------------------------------- overview (small Markdown dialect)

def _inline(s: str) -> str:
    s = html.escape(s, quote=False)
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    s = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"(?<![\w*])\*([^*]+)\*(?![\w*])", r"<em>\1</em>", s)
    s = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', s)
    return s


def markdown(text: str) -> str:
    out: list[str] = []
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        ln = lines[i]
        if not ln.strip():
            i += 1
            continue
        if ln.startswith("```"):
            j = i + 1
            while j < len(lines) and not lines[j].startswith("```"):
                j += 1
            out.append("<pre>" + html.escape("\n".join(lines[i + 1:j])) + "</pre>")
            i = j + 1
            continue
        m = re.match(r"(#{1,4}) (.*)", ln)
        if m:
            lvl = len(m.group(1))
            slug = re.sub(r"[^a-z0-9]+", "-", m.group(2).lower()).strip("-")
            out.append(f'<h{lvl} id="{slug}">{_inline(m.group(2))}</h{lvl}>')
            i += 1
            continue
        if ln.startswith("|"):
            rows = []
            while i < len(lines) and lines[i].startswith("|"):
                cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                if not all(re.fullmatch(r":?-+:?", c) for c in cells):
                    rows.append(cells)
                i += 1
            th = "".join(f"<th>{_inline(c)}</th>" for c in rows[0])
            tb = "".join("<tr>" + "".join(f"<td>{_inline(c)}</td>" for c in r) + "</tr>" for r in rows[1:])
            out.append(f"<table><tr>{th}</tr>{tb}</table>")
            continue
        if re.match(r"(\s*)([-*]|\d+\.) ", ln):
            ordered = bool(re.match(r"\s*\d+\. ", ln))
            items: list[str] = []
            while i < len(lines) and lines[i].strip() and (re.match(r"\s*([-*]|\d+\.) ", lines[i]) or lines[i].startswith("  ")):
                if re.match(r"\s*([-*]|\d+\.) ", lines[i]):
                    items.append(re.sub(r"\s*([-*]|\d+\.) ", "", lines[i], count=1))
                else:
                    items[-1] += " " + lines[i].strip()
                i += 1
            tag = "ol" if ordered else "ul"
            out.append(f"<{tag}>" + "".join(f"<li>{_inline(x)}</li>" for x in items) + f"</{tag}>")
            continue
        para = []
        while i < len(lines) and lines[i].strip() and not re.match(r"(#{1,4} |```|\||\s*([-*]|\d+\.) )", lines[i]):
            para.append(lines[i].strip())
            i += 1
        out.append(f"<p>{_inline(' '.join(para))}</p>")
    return "\n".join(out)


def fill(template: str, final: dict[str, str], addr_line: dict[int, int], listing: str) -> str:
    """{NAME} -> the variable's name; [[$addr]] -> a link "line N" into the listing."""
    def name(m: re.Match[str]) -> str:
        key = m.group(1)
        if key not in final:
            raise ValueError(f"unknown name {{{key}}} in an overview")
        return final[key]

    def line(m: re.Match[str]) -> str:
        a = int(m.group(1), 16)
        if a not in addr_line:
            raise ValueError(f"[[${a:04X}]] is not the start of a line")
        n = addr_line[a]
        label = m.group(2) or f"line {n}"
        return f"[{label}]({listing}#L{n})"

    text = re.sub(r"\{([A-Z][A-Z0-9]?\$?)\}", name, template)
    return re.sub(r"\[\[\$([0-9A-Fa-f]{4})(?:\|([^\]]+))?\]\]", line, text)


def overview_html(name: str, body_md: str) -> str:
    t = TITLES[name]
    return (_head(f"{t} overview", PURPOSE[name]) + _nav(name, f"{name}.OVERVIEW.html")
            + '<article class="ov">' + markdown(body_md) + "</article>" + FOOTER + "</main></body></html>\n")


# disk images offered for download from the index: (published name, source, description)
DISKS = [
    ("TASC-2.01.dsk", ROOT / "images" / "original" / "TASC 2.01 (Microsoft 1981).dsk",
     "The TASC 2.01 disk as distributed: PASS0, PASS1, PASS2, RUNTIME and the BALL demonstration (boots into the compiler)"),
    ("TASC-2.01-SOURCE.dsk", ROOT / "images" / "source" / "TASC 2.01 SOURCE.dsk",
     "The source disk: PASS0, PASS1 and PASS2 as Applesoft programs, MAKE RUNTIME, and the RUNTIME source "
     "(RUNTIME.S1-S6 for the DOS Tool Kit assembler)"),
]


def copy_disks() -> list[tuple[str, int, str, str]]:
    """Copy the disk images next to the pages; return (name, size, sha256, description)."""
    import hashlib
    import shutil
    (OUT / "disks").mkdir(parents=True, exist_ok=True)
    out = []
    for name, src, desc in DISKS:
        dst = OUT / "disks" / name
        shutil.copyfile(src, dst)
        data = dst.read_bytes()
        out.append((name, len(data), hashlib.sha256(data).hexdigest(), desc))
    return out


def write_index() -> None:
    OUT.mkdir(exist_ok=True)
    (OUT / "index.html").write_text(index_html(copy_disks()))


def index_html(disks: list[tuple[str, int, str, str]] | None = None) -> str:
    rows = "".join(
        f'<tr><td><strong>{TITLES[n]}</strong></td><td>{html.escape(PURPOSE[n])}</td>'
        f'<td><a href="{n}.OVERVIEW.html">overview</a></td><td><a href="{n}.html">listing</a></td></tr>'
        for n in TITLES)
    return (_head("TASC sources", "The Applesoft sources of the TASC compiler passes, annotated")
            + '<header class="top"><h1>TASC compiler sources</h1></header>'
            + '<p class="muted">Microsoft TASC 2.01. TASC runs as three Applesoft programs compiled by TASC itself, '
              'sharing a COMMON block: PASS0 asks the questions and sets up, PASS1 compiles, PASS2 finishes the '
              'object file. RUNTIME is the machine language library compiled programs call; MAKE RUNTIME builds it.</p>'
            + f'<table class="vars"><tr><th>Program</th><th>What it does</th><th></th><th></th></tr>{rows}</table>'
            + _disks_html(disks or [])
            + '<section class="notice" id="copyright"><h2>Copyright and use</h2>'
              '<p>TASC, its compiler passes and the RUNTIME library are the copyrighted work of Microsoft '
              '(Copyright &copy; 1981 Microsoft), and Microsoft&rsquo;s ownership of this code is respected. '
              'The sources, listings and documentation here are prepared with the intent of staying within the '
              'bounds of fair use, and are for educational and historical purposes only: to study and preserve '
              'how an early Apple&nbsp;II compiler worked. They are not offered for sale or for any commercial '
              'use.</p>'
              '<p>Any takedown or removal request from the copyright holder will be respected and acted on '
              'promptly.</p></section>'
            + "</main></body></html>\n")


def _disks_html(disks: list[tuple[str, int, str, str]]) -> str:
    if not disks:
        return ""
    rows = "".join(
        f'<tr><td><a href="disks/{n}" download>{n}</a></td><td>{html.escape(d)}</td><td>{size:,} bytes</td>'
        f'<td><code>{sha[:16]}&hellip;</code></td></tr>' for n, size, sha, d in disks)
    return ('<h2>Disk images</h2><p class="muted">140K DOS 3.3 disk images (16 sectors, DOS order) for an Apple II '
            'or an emulator. To compile a pass, boot the TASC disk with the source disk in drive 2 and answer '
            '<code>PASS1,D2</code> at the source file question and <code>PASS1.OBJ,D1</code> at the object file question '
            '(the source disk has no room for object files).</p>'
            f'<table class="vars"><tr><th>Image</th><th>Contents</th><th>Size</th><th>SHA-256</th></tr>{rows}</table>')


def write_page(page: Page, overview_md: str | None) -> None:
    OUT.mkdir(exist_ok=True)
    (OUT / f"{page.name}.html").write_text(listing_html(page))
    if overview_md is not None:
        (SRC / f"{page.name}.OVERVIEW.TXT").write_text(overview_md)
        (OUT / f"{page.name}.OVERVIEW.html").write_text(overview_html(page.name, overview_md))
    write_index()


# ---------------------------------------------------------------- MAKE RUNTIME (not generated by sourcegen)

def make_runtime_page() -> Page:
    lines = []
    for row in (SRC / "MAKE_RUNTIME.txt").read_text().splitlines():
        n, _, text = row.partition(" ")
        lines.append((int(n), text))
    entries: dict[int, list[tuple[str, str]]] = {}
    for row in (SRC / "MAKE_RUNTIME.DOC.TXT").read_text().splitlines():
        n, _, rest = row.partition(" REM")
        if rest.strip():
            entries.setdefault(int(n), []).append(("line", rest.strip()))
    names = {}
    vrows = [["NAME", "TYPE", "MEANING"]]
    for row in (SRC / "MAKE_RUNTIME.VARS.TXT").read_text().splitlines():
        nm, ty, mean = row.split(None, 2)
        names[(nm, False)] = f"{ty}: {mean}"
        vrows.append([nm, ty, mean])
    page = Page("MAKE_RUNTIME", lines, entries, names=names, vars_rows=vrows)
    page.sections = {10: "MOVE THE PROGRAM OUT OF THE WAY IF NEEDED, COPY THE LIBRARY INTO PLACE AND SAVE IT",
                     100: "THE 4013 BYTES OF THE LIBRARY, 25 TO A LINE"}
    page.collapse = {100}
    return page


def main() -> None:
    tmpl = ROOT / "docs" / "lift" / "annot" / "MAKE_RUNTIME.overview.txt"
    write_page(make_runtime_page(), tmpl.read_text() if tmpl.exists() else None)


if __name__ == "__main__":
    main()


# ---------------------------------------------------------------- RUNTIME (6502 source)

def _asm_operand(operand: str, labels: dict[str, int], equ: dict[str, str]) -> str:
    def one(m: re.Match[str]) -> str:
        w = m.group(0)
        if w in labels:
            return f'<a href="#A{labels[w]:04X}">{w}</a>'
        if w in equ:
            return f'<a href="#E_{w}" title="{html.escape(equ[w])}">{w}</a>'
        return html.escape(w)
    return re.sub(r"[A-Z][A-Z0-9]*|[^A-Z]+", one, operand)


def write_runtime(rows: list, labels: dict[int, str], ann: object,
                  files: list[tuple[str, int, int, int]] | None = None) -> None:
    """src/html/RUNTIME.html (the source as an assembler listing) and its overview."""
    by_name = {n: a for a, n in labels.items()}
    equ = {n: c for n, _, c in ann.equates}  # type: ignore[attr-defined]
    parts = [_head("RUNTIME source", PURPOSE["RUNTIME"]), _nav("RUNTIME", "RUNTIME.html")]
    parts.append('<p class="muted">The library as 6502 source in the style of Apple\'s DOS Toolkit assembler. '
                 "Address and bytes on the left; labels in operands link to their definitions; point at a name from "
                 'the equates for its meaning. The source assembles to the library byte for byte. '
                 '<a href="#equates">Equates</a></p>\n')
    # sections: header, then one per routine block
    sections: list[tuple[int, list[str], list]] = [(-1, [], [])]
    for r in rows:
        if r.kind == "block":
            if not sections[-1][2] or sections[-1][0] != r.addr:
                if sections[-1][0] != r.addr:
                    sections.append((r.addr, [], []))
            if r.text.strip("*- ") :
                sections[-1][1].append(r.text[2:])
            continue
        sections[-1][2].append(r)
    toc = []
    for addr, block, _ in sections[1:]:
        name = labels.get(addr, f"${addr:04X}")
        first = " ".join(block)[:110]
        toc.append(f'<li><a href="#A{addr:04X}">{name}</a> <span class="muted">{html.escape(first)}</span></li>')
    parts.append(f'<details class="toc"><summary>Routines ({len(sections) - 1})</summary><ol>{"".join(toc)}</ol></details>\n')
    eq_rows = []
    for addr, block, items in sections:
        body = []
        for r in items:
            if r.kind == "head":
                continue
            if r.kind == "equ":
                eq_rows.append(f'<tr id="E_{r.label}"><td>{r.label}</td><td>{html.escape(r.operand)}</td>'
                               f'<td>{html.escape(r.comment)}</td></tr>')
                continue
            a = f"{r.addr:04X}" if r.kind == "code" else ""
            rid = f' id="A{r.addr:04X}"' if r.kind == "code" else ""
            body.append(f'<tr{rid}><td class="a">{a}</td><td class="b">{r.raw.hex(" ").upper()}</td>'
                        f'<td class="l">{r.label}</td><td class="o">{r.op}</td>'
                        f'<td>{_asm_operand(r.operand, by_name, equ)}</td><td class="c">{html.escape(r.comment)}</td></tr>')
        if not body:
            continue
        hs = ""
        if block:
            text = " ".join(block)
            paras = "".join(f"<p>{html.escape(p.strip())}</p>" for p in ann.routines.get(addr, text).split("|"))  # type: ignore[attr-defined]
            hs = f'<div class="h"><p><span class="ln">{labels.get(addr, "")}</span></p>{paras}</div>'
        parts.append(f'<section class="r">{hs}<div class="wrap"><table class="asm">{"".join(body)}</table></div></section>\n')
    parts.append(f'<h2 id="equates">Equates</h2><table class="vars"><tr><th>Name</th><th>Value</th><th>Meaning</th></tr>'
                 f'{"".join(eq_rows)}</table>\n' + FOOTER + '</main></body></html>\n')
    OUT.mkdir(exist_ok=True)
    (OUT / "RUNTIME.html").write_text("".join(parts))
    tmpl = ROOT / "docs" / "lift" / "annot" / "RUNTIME.overview.txt"
    if tmpl.exists():
        def link(m: re.Match[str]) -> str:
            a = int(m.group(1), 16)
            if a not in labels:
                raise ValueError(f"[[${a:04X}]] has no label in RUNTIME")
            return f"[{m.group(2) or labels[a]}](RUNTIME.html#A{a:04X})"
        md = re.sub(r"\[\[\$([0-9A-Fa-f]{4})(?:\|([^\]]+))?\]\]", link, tmpl.read_text())
        table = "\n".join(f"| {n} | ${f:04X}-${l:04X} | {size} |" for n, size, f, l in files or [])
        md = md.replace("[[FILES]]", "| File | Addresses | Characters |\n|---|---|---|\n" + table)
        (SRC / "RUNTIME.OVERVIEW.TXT").write_text(md)
        (OUT / "RUNTIME.OVERVIEW.html").write_text(overview_html("RUNTIME", md))
    write_index()
