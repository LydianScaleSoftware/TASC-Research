"""Compile Applesoft programs with the real TASC in Pandowdy and collect the results.

A Session wraps one emulator instance.  It captures everything printed to the
text screen (lines scrolled off the top, plus screens cleared by HOME) so the
compile listing and the line-number reference table are never lost.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from tasc import disk
from tasc.emu import EmuError, Pandowdy, Transcript, install_capture, run_capturing
from tasc.options import Options

COMPILE_CYCLES = 2_000_000_000  # BALL needs ~150M; PASS-sized sources need far more
ERROR_PROMPT = "TYPE CNTRL-C TO ABORT"  # pause-on-errors prompt; not seen by the key-wait heuristic


class CompileError(RuntimeError):
    pass


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


@dataclass
class LineEntry:
    line: int
    addr: int


@dataclass
class CompileResult:
    source: str
    obj_name: str
    obj_addr: int
    obj_len: int
    obj_sha256: str
    cycles: int
    line_table: list[LineEntry]
    info: dict[str, str] = field(default_factory=dict)


def _tail(rows: list[str], n: int) -> list[str]:
    """The last n rows up to and including the last non-blank one."""
    end = len(rows)
    while end and not rows[end - 1].strip():
        end -= 1
    return rows[max(0, end - n) : end]


class Session:
    def __init__(self, emu: Pandowdy) -> None:
        self.emu = emu
        self.transcript = Transcript()
        install_capture(emu)

    def run_to_key(self, max_cycles: int = 50_000_000) -> dict[str, Any]:
        r = run_capturing(self.emu, self.transcript, max_cycles)
        if r["stop_reason"] != "waiting_for_key":
            raise EmuError(f"expected key wait, got {r['stop_reason']} at {r['cpu']['pc']}")
        return r

    def screen(self) -> list[str]:
        return self.emu.screen_rows()

    def finish_transcript(self) -> None:
        self.transcript.add_screen(self.screen())

    def expect(self, text: str) -> None:
        rows = self.screen()
        if not any(text in r for r in _tail(rows, 6)):
            raise CompileError(f"expected {text!r} near the bottom of the screen:\n" + "\n".join(rows))

    def answer(self, prompt: str, reply: str) -> None:
        self.expect(prompt)
        self.emu.type(reply + "\n")


DEFAULT_ANSWERS = Options().answers()


def compile_in_session(
    s: Session, source: str, answers: list[tuple[str, str]] | None = None, line_table: bool = True
) -> int:
    """From the SOURCE FILE? prompt, compile `source`.  Returns cycles used.

    Leaves the machine at the Applesoft prompt after *****COMPILATION COMPLETE.
    """
    start = s.emu.call("get_state")["total_cycles"]
    s.answer("SOURCE FILE?", source)
    for prompt, reply in answers if answers is not None else DEFAULT_ANSWERS:
        s.run_to_key()
        s.answer(prompt, reply)
    asked = False
    while True:
        r = run_capturing(s.emu, s.transcript, COMPILE_CYCLES, until_text=ERROR_PROMPT)
        if r["stop_reason"] == "text_match":
            if any(row.startswith(ERROR_PROMPT) for row in s.screen()):
                raise CompileError("compile error:\n" + "\n".join(_tail(s.screen(), 8)))
            # the prompt text inside a listed source line (TASC's own PRINT statements):
            # run on until it has scrolled away
            while ERROR_PROMPT in "\n".join(s.screen()):
                r = run_capturing(s.emu, s.transcript, 2_000_000)
                if r["stop_reason"] == "waiting_for_key":
                    break
            if r["stop_reason"] != "waiting_for_key":
                continue
        if r["stop_reason"] != "waiting_for_key":
            raise CompileError(f"compile stopped: {r['stop_reason']} at {r['cpu']['pc']}")
        rows = s.screen()
        bottom = "\n".join(_tail(rows, 4))
        if "COMPILATION COMPLETE" in bottom and _tail(rows, 1)[0].startswith("]"):
            break
        if not asked and "REFERENCE TABLE?" in bottom:
            s.emu.type("YES\n" if line_table else "NO\n")
            asked = True
            continue
        raise CompileError("unexpected input wait during compile:\n" + "\n".join(rows))
    return int(s.emu.call("get_state")["total_cycles"]) - int(start)


_PAIR = re.compile(r"(\d+)\s+(\d+)")


def parse_line_table(text: str) -> tuple[list[LineEntry], dict[str, str]]:
    lines = text.splitlines()
    entries: list[LineEntry] = []
    info: dict[str, str] = {}
    try:
        start = max(i for i, l in enumerate(lines) if l.startswith("LINE# ADDR"))
    except ValueError:
        return entries, info
    for l in lines[:start]:
        m = re.match(r"^([A-Z][A-Z .]+?)(?: OCCUPIES| OCCUPY|:)\s*(.+)$", l)
        if m and "SOURCE FILE" not in l:
            info[m.group(1).strip()] = m.group(2).strip()
    for l in lines[start + 1 :]:
        if not l.strip():
            continue
        if l.startswith("*****"):
            break
        pairs = _PAIR.findall(l)
        if not pairs:
            break
        entries.extend(LineEntry(int(a), int(b)) for a, b in pairs)
    return entries, info


def compile_file(
    base_image: Path,
    source: str,
    outdir: Path,
    answers: list[tuple[str, str]] | None = None,
) -> CompileResult:
    """Fresh boot of a copy of `base_image`, compile `source`, save everything to outdir."""
    outdir.mkdir(parents=True, exist_ok=True)
    work = outdir / "work.dsk"
    shutil.copyfile(base_image, work)
    with Pandowdy() as emu:
        emu.boot(work)
        s = Session(emu)
        s.run_to_key(40_000_000)
        cycles = compile_in_session(s, source, answers)
        s.finish_transcript()
        emu.call("save_disk", path=str((outdir / "after.dsk").resolve()))
    return collect(outdir, source, s.transcript, cycles)


def collect(outdir: Path, source: str, transcript: Transcript, cycles: int) -> CompileResult:
    text = transcript.text()
    (outdir / "transcript.txt").write_text(text)
    files = disk.extract_all(outdir / "after.dsk")
    obj_name = source + ".OBJ"
    if obj_name not in files:
        raise CompileError(f"{obj_name} not found on disk after compile")
    obj = files[obj_name]
    (outdir / obj_name.replace(" ", "_")).write_bytes(obj.data)
    if "CLINENUM" in files:
        (outdir / "CLINENUM").write_bytes(files["CLINENUM"].data)
    table, info = parse_line_table(text)
    res = CompileResult(
        source=source,
        obj_name=obj_name,
        obj_addr=obj.aux,
        obj_len=len(obj.data),
        obj_sha256=sha256(obj.data),
        cycles=cycles,
        line_table=table,
        info=info,
    )
    (outdir / "result.json").write_text(json.dumps(asdict(res), indent=1) + "\n")
    return res
