"""Section 6b checkers for the recovered TASC sources in src/ (Phase 5).

DOC files mirror the source's line numbers; every variable is in the compendium and has
a first-definition comment; no name contains a keyword or collides within its type.
Passes are listed in DOCUMENTED once their annotations are complete.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from tasc.compiler.parse import TOK, read_program
from tasc.decomp.names import RESERVED

SRC = Path(__file__).parents[1] / "src"
DOCUMENTED = ["PASS0", "PASS1", "PASS2"]
KEYWORD_PARTS = ("AT", "TO", "ON", "OR", "FN", "IF")


def source_lines(name: str) -> list[tuple[int, bytes]]:
    return [(ln.number, ln.body) for ln in read_program((SRC / f"{name}.bas").read_bytes())]


def names_in(body: bytes) -> list[str]:
    """Variable and FN names of a tokenized line (REM! declarations included)."""
    out: list[str] = []
    rem = TOK["REM"]
    if body[:1] == bytes([rem]):
        text = body[1:].decode("latin-1")
        if not text.lstrip().startswith("!"):
            return out
        words = re.sub(r"\(\d+(,\d+)*\)", "()", text.lstrip()[1:].strip())
        kw = re.match(r"(INTEGER|DEFCOMMON|USECOMMON)\s*", words)
        if kw:
            out += re.findall(r"[A-Z][A-Z0-9]*[%$]?(?:\(\))?", words[kw.end():])
        return out
    i = 0
    fn_next = False
    while i < len(body):
        b = body[i]
        if b == 0x22:
            j = body.find(b'"', i + 1)
            i = len(body) if j < 0 else j + 1
            continue
        if b in (rem, TOK["DATA"]):
            if b == rem:
                break
            while i < len(body) and body[i] != 0x3A:
                i += 1
            continue
        if b == TOK["FN"]:
            fn_next = True
            i += 1
            continue
        if 65 <= b <= 90:
            j = i
            while j < len(body) and (65 <= body[j] <= 90 or 48 <= body[j] <= 57):
                j += 1
            nm = body[i:j].decode()
            if j < len(body) and body[j] in (0x24, 0x25):
                nm += chr(body[j])
                j += 1
            if fn_next:
                out.append("FN " + nm)
                fn_next = False
            else:
                out.append(nm + ("()" if j < len(body) and body[j] == 0x28 else ""))
            i = j
            continue
        i += 1
    return out


@pytest.mark.parametrize("name", DOCUMENTED + ["MAKE_RUNTIME"])
def test_doc_mirrors_source(name: str) -> None:
    if name == "MAKE_RUNTIME":
        src = [int(l.split()[0]) for l in (SRC / "MAKE_RUNTIME.txt").read_text().splitlines()]
    else:
        src = [n for n, _ in source_lines(name)]
    doc = [int(l.split()[0]) for l in (SRC / f"{name}.DOC.TXT").read_text().splitlines()]
    dedup = [n for i, n in enumerate(doc) if i == 0 or doc[i - 1] != n]
    assert dedup == src
    assert all(l.split()[1] == "REM" for l in (SRC / f"{name}.DOC.TXT").read_text().splitlines())


@pytest.mark.parametrize("name", DOCUMENTED)
def test_variables_documented(name: str) -> None:
    lines = source_lines(name)
    used: set[str] = set()
    for _, body in lines:
        used |= set(names_in(body))
    vars_text = (SRC / f"{name}.VARS.TXT").read_text().splitlines()[1:]
    listed = set()
    for row in vars_text:
        key = " ".join(row.split()[:2]) if row.startswith("FN ") else row.split()[0]
        listed.add(re.sub(r"\(\d+(,\d+)*\)", "()", key))
    missing = sorted(u for u in used if u not in listed)
    assert not missing, missing
    doc = (SRC / f"{name}.DOC.TXT").read_text()
    fns = {u for u in used if u.startswith("FN ")}
    params = {row.split()[0] for row in vars_text if "PARAMETER OF THE DEF FN" in row}
    for u in sorted(used - fns - params):
        assert re.search(rf"^\d+ REM {re.escape(u)} IS ", doc, re.M), f"no first-definition comment for {u}"
    for f in sorted(fns):
        assert f"REM {f}(" in doc, f"no comment for {f}"


@pytest.mark.parametrize("name", ["PASS0", "PASS1", "PASS2"])
def test_names_are_safe(name: str) -> None:
    seen: dict[tuple[str, str, bool], str] = {}
    for _, body in source_lines(name):
        for u in names_in(body):
            if u.startswith("FN "):
                continue
            base = u.rstrip("()").rstrip("%$")
            assert len(base) <= 2, u
            assert base not in RESERVED and not any(k in base for k in KEYWORD_PARTS), u
            key = (base[:2], u.rstrip("()")[len(base):], u.endswith("()"))
            assert seen.setdefault(key, u) == u, f"{u} collides with {seen[key]}"


@pytest.mark.parametrize("name", ["PASS0", "PASS1", "PASS2"])
def test_listing_retokenizes(name: str, tmp_path: Path) -> None:
    """The plain listing, typed in again (tokenized as the ROM does), gives the same program."""
    import shutil

    from tasc import disk

    image = tmp_path / "t.dsk"
    shutil.copyfile(Path(__file__).parents[1] / "images" / "work" / "tasc201.dsk", image)
    disk.import_basic(image, SRC / f"{name}.txt", "LISTING")
    got = [(ln.number, ln.body) for ln in read_program(disk.extract(image, "LISTING").data)]
    want = source_lines(name)
    bad = [n for (n, a), (_, b) in zip(want, got) if a != b]
    assert len(got) == len(want) and not bad, f"lines that tokenize differently: {bad}"
