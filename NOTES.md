# TASC reverse engineering: project notes

Entry point for any new session. Read this first, then the handoff prompt
(`../TASC_handoff_prompt.md`) for the full mission and rules. RAG collection
**`TASC project`** holds findings as chunks (status in brackets in each title).

## Status (2026-10-24, session 1)

- **Phase 0: done.** Exit criterion met: `python -m tasc.phase0` runs the whole
  loop (inventory, detokenize, compile BALL, line table, run BALL.OBJ,
  determinism check) in about 40 s with no manual steps.
- Next: **Phase 1** (empirical templates). First need: drive the non-default
  MEMORY USAGE and OPTIONS dialogues (prompts not yet seen) and a generator
  that tokenizes test programs onto a work image with `cp2 import bas`.

## Environment

- cp2: CiderPress II v2.0.0-dev3 (`~/.local/bin/cp2`). Override: `TASC_CP2`.
- Pandowdy MCP: commit `0a3f63f` (matches the handoff). Installed DLL
  `~/.local/share/pandowdy-mcp/Pandowdy.Mcp.dll`. Override: `TASC_PANDOWDY`.
  Apple IIe enhanced ROM, 65C02.
- Python 3.14.7; dev tools in `.venv` (pytest 9.1.1, mypy 2.4.0, strict).
  `.venv/bin/pytest` (fast) / `.venv/bin/pytest -m emu` (emulator, ~10 s) /
  `.venv/bin/mypy`.

### Pandowdy capability check (handoff section 4 list)
Verified against the README and the live tool list:
run N / trace in one call: yes (`step` count ≤10000, `run` max_instructions,
`get_trace` last 4096). Conditional breakpoints: yes. Read/write watchpoints:
yes (ranges, no conditions). Bulk memory read/write: yes (`read_memory` up to
64K, `save_memory`, `load_binary`). Snapshot/restore: **no**. Mount/eject:
yes. Reset and cold boot: yes. Keystroke injection: yes. Text screen as text:
yes. Not a blocker: fresh boots are cycle-identical, and a TASC compile from
boot takes about 10 s of wall time.

## Decisions

- Repo `tasc-re/` under the project folder; git; originals read-only in
  `images/original/`; the working image is `images/work/tasc201.dsk` (copy of 2.01).
- Reference version: **TASC 2.01** (only disk with BALL; boots straight into PASS0).
- **The harness spawns its own Pandowdy over stdio** (`tasc/emu.py`), so
  experiments run from Python without the model. Claude's own Pandowdy instance
  is for interactive poking only.
- Screen capture = breakpoints at Monitor SCROLL $FC70 and HOME $FC58
  (`tasc.emu.run_capturing`). All waits are key waits; never compare state at
  `until_text` stops (see the RAG dead-end chunk).
- `disk.extract_all` (a whole-disk extract) is the robust path: cp2 can't name
  files containing `/` individually; it escapes them as `%2f`.
- Experiment layout: `experiments/<family>/<run>/` with `work.dsk`,
  `after.dsk` (git-ignored), `<SRC>.OBJ`, `transcript.txt`, `result.json`.
- Golden files in `tests/golden/` (BALL.OBJ, BALL transcript).

## Hypotheses

| | Status | Evidence / note |
|---|---|---|
| H1 shared RUNTIME/config | observed (supporting) | PASS0/1/2 all load $41F2; headers give library end $17AF and COMMON $41D9..$41F1 |
| H2 options inferable | open | object start likely HGR1 ($4000) + 498-byte COMMON block |
| H3 hand-written parts identifiable | open | |
| H4 deterministic | **confirmed** | phase0 runs A/B/C identical (C in a dirty session over an existing BALL.OBJ) |
| H5 names/line numbers lost | open | |
| H6 RUNTIME hand-written | open | init code at $0803 looks hand-written (PLA/ADC #$11 inline skip) |
| H7 how ML was joined | open | PASS files start with a compiled string literal ("COPYRIGHT…"), so no prefix blob |

## Facts established (details in RAG `phase0.md`)

- Object file = `JSR $0803` + 17-byte inline parameter block + code. Line 10 of
  BALL is at load+20.
- String literals are inline: `JMP` over `[len][text]`.
- BALL.OBJ (defaults): $17B0, 1485 bytes, sha `7a37f061…`; 40-entry line table.
- CLINENUM is left as a 1-byte file after a compile.
- PASS1 is identical in 2.0 and 2.01; PASS0, PASS2 and RUNTIME differ (same
  lengths for PASS2 and RUNTIME).

## Open questions for Mark

- None blocking.

## Layout

```
tasc/disk.py       cp2 wrapper          tasc/emu.py      Pandowdy stdio client + screen capture
tasc/harness.py    compile driver       tasc/inventory.py  extract + hash all images
tasc/phase0.py     Phase 0 loop         docs/inventory.md  file table
docs/rag/*.md      RAG sources (push the whole file after editing)
src/launchers/     detokenized small Applesoft programs
extracted/<img>/   exact file data, NAPS-suffixed names (#TTAAAA)
```
