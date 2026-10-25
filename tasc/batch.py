"""Compile many small test programs with the real TASC, in parallel.

Each worker gets a copy of the work image with its share of the sources
tokenized onto it (cp2 import bas), boots once and compiles them one after
another (RUN HELLO between compiles).  Results go to
experiments/<family>/<job id>/ and are cached by a hash of source + options.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
import traceback
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from tasc import disk
from tasc.emu import Pandowdy
from tasc.harness import (
    CompileError, LineEntry, Options, Session, _tail, compile_in_session, parse_line_table, sha256,
)

ROOT = Path(__file__).resolve().parent.parent
BASE = ROOT / "images" / "work" / "tasc201.dsk"
EXPERIMENTS = ROOT / "experiments"
JOBS_PER_DISK = 20


@dataclass(frozen=True)
class Job:
    id: str  # directory name, unique within the family
    source: str  # plain-text listing, one numbered line per line
    options: Options = field(default_factory=Options)

    def key(self) -> str:
        blob = json.dumps({"src": self.source, "opt": asdict(self.options)}, sort_keys=True)
        return hashlib.sha256(blob.encode()).hexdigest()[:16]


@dataclass
class JobResult:
    id: str
    key: str
    source: str
    options: dict[str, Any]
    ok: bool
    error: str = ""
    obj_addr: int = 0
    obj_len: int = 0
    obj_sha256: str = ""
    cycles: int = 0
    line_table: list[LineEntry] = field(default_factory=list)
    info: dict[str, str] = field(default_factory=dict)

    def obj(self, family: str) -> bytes:
        return (EXPERIMENTS / family / self.id / "OBJ.bin").read_bytes()


def load_result(family: str, job_id: str) -> JobResult:
    d = json.loads((EXPERIMENTS / family / job_id / "result.json").read_text())
    d["line_table"] = [LineEntry(**e) for e in d["line_table"]]
    return JobResult(**d)


def _cached(family: str, job: Job) -> JobResult | None:
    p = EXPERIMENTS / family / job.id / "result.json"
    if not p.exists():
        return None
    r = load_result(family, job.id)
    return r if r.key == job.key() and r.ok else None


def _write(family: str, job: Job, res: JobResult, transcript: str, obj: bytes | None) -> None:
    d = EXPERIMENTS / family / job.id
    d.mkdir(parents=True, exist_ok=True)
    (d / "source.txt").write_text(job.source)
    (d / "transcript.txt").write_text(transcript)
    if obj is not None:
        (d / "OBJ.bin").write_bytes(obj)
    (d / "result.json").write_text(json.dumps(asdict(res), indent=1) + "\n")


def _worker(family: str, jobs: list[Job], base: Path) -> list[JobResult]:
    results: list[JobResult] = []
    with tempfile.TemporaryDirectory(prefix="tasc-") as td:
        tdp = Path(td)
        img = tdp / "work.dsk"
        shutil.copyfile(base, img)
        names: dict[str, str] = {}
        for i, job in enumerate(jobs):
            name = f"S{i:03d}"
            names[job.id] = name
            src = tdp / f"{name}.txt"
            src.write_text(job.source if job.source.endswith("\n") else job.source + "\n")
            disk.import_basic(img, src, name)

        pending = list(jobs)
        while pending:
            emu = Pandowdy()
            try:
                emu.boot(img)
                s = Session(emu)
                s.run_to_key(40_000_000)
                while pending:
                    job = pending[0]
                    mark = len(s.transcript.rows)
                    try:
                        cyc = compile_in_session(s, names[job.id], job.options.answers())
                    except (CompileError, Exception) as exc:  # noqa: BLE001 - record and reboot
                        s.finish_transcript()
                        text = "\n".join(s.transcript.rows[mark:]) + "\n"
                        res = JobResult(job.id, job.key(), job.source, asdict(job.options), False,
                                        error=f"{type(exc).__name__}: {exc}")
                        _write(family, job, res, text, None)
                        results.append(res)
                        pending.pop(0)
                        emu.call("save_disk", path=str(img))
                        break  # reboot for the rest
                    end = len(s.transcript.rows)
                    s.transcript.add_screen(s.screen())
                    text = "\n".join(s.transcript.rows[mark:]) + "\n"
                    del s.transcript.rows[end:]  # final screen is re-scrolled later
                    table, info = parse_line_table(text)
                    results.append(JobResult(job.id, job.key(), job.source, asdict(job.options), True,
                                             cycles=cyc, line_table=table, info=info))
                    _write(family, job, results[-1], text, None)
                    pending.pop(0)
                    s.transcript.rows.clear()
                    emu.type("RUN HELLO\n")
                    s.run_to_key(40_000_000)
                    s.expect("SOURCE FILE?")
                else:
                    emu.call("save_disk", path=str(img))
            finally:
                emu.close()

        files = disk.extract_all(img)
        for res in results:
            job = next(j for j in jobs if j.id == res.id)
            if not res.ok:
                continue
            f = files.get(names[res.id] + ".OBJ")
            if f is None:
                res.ok, res.error = False, "object file missing"
            else:
                res.obj_addr, res.obj_len, res.obj_sha256 = f.aux, len(f.data), sha256(f.data)
            d = EXPERIMENTS / family / res.id
            if f is not None:
                (d / "OBJ.bin").write_bytes(f.data)
            (d / "result.json").write_text(json.dumps(asdict(res), indent=1) + "\n")
    return results


def run_family(family: str, jobs: list[Job], workers: int = 8, base: Path = BASE) -> dict[str, JobResult]:
    ids = [j.id for j in jobs]
    if len(set(ids)) != len(ids):
        raise ValueError("duplicate job ids")
    out: dict[str, JobResult] = {}
    todo: list[Job] = []
    for j in jobs:
        c = _cached(family, j)
        if c is not None:
            out[j.id] = c
        else:
            todo.append(j)
    chunks = [todo[i : i + JOBS_PER_DISK] for i in range(0, len(todo), JOBS_PER_DISK)]
    # spread across workers: split big chunks finer when there are spare workers
    if chunks and len(chunks) < workers:
        per = max(1, -(-len(todo) // workers))
        chunks = [todo[i : i + per] for i in range(0, len(todo), per)]
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = [ex.submit(_worker, family, c, base) for c in chunks]
        for f in futs:
            try:
                for r in f.result():
                    out[r.id] = r
            except Exception:
                traceback.print_exc()
    bad = [r for r in out.values() if not r.ok]
    print(f"{family}: {len(jobs)} jobs, {len(todo)} compiled, {len(jobs) - len(todo)} cached, {len(bad)} failed")
    for r in bad:
        print(f"  FAILED {r.id}: {r.error.splitlines()[0] if r.error else ''}")
    return out
