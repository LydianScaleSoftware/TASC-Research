# TASC reverse engineering: project notes

Entry point for any new session. Phase 3 handoff: `docs/handoff_phase3.md` (Phases 3 and 4 now closed). Read this first, then the handoff prompt
(`../TASC_handoff_prompt.md`) for the full mission and rules. RAG collection
**`TASC project`** holds findings as chunks (status in brackets in each title).

## Status (2026-10-25, end of session 5)

- Phases 0, 1, 2, R: done (sessions 1-3; details in RAG phase0/1/2, runtime*).
- **Phase 3: closed (2026-10-25, agreed with Mark).** Exit criterion met: the
  Python compiler (`tasc/compiler/`) matches real TASC byte for byte on every
  recorded program, 1,954 compiles including BALL, and rejects all 237 programs
  TASC rejects (`python -m tasc.predict_check`). Rules are lifted from PASS1/PASS2
  where read (`docs/lift/PASS1.md`, `PASS2.md`; RAG `phase3-lift.md`); no GUESS
  markers left. Real-TASC case lists: `python -m tasc.lift_checks [--unsup | --then]`.
- **Phase 4: closed (2026-10-25, agreed with Mark).** Exit criterion met: the
  decompiler (`tasc/decomp/`) round-trips all 1,954 recorded compiles and BALL.OBJ
  (`python -m tasc.decomp.decompile --corpus`, pytest tests/test_decomp.py).
- **Phase 5: next.** Already done: PASS0/1/2 decompiled jointly (shared COMMON
  names); the real TASC compiles the regenerated sources (`src/generated/PASSn.bas`)
  into files identical to the originals (`python -m tasc.selfcompile`). To do:
  meaningful names within the hash constraints, line-mirrored DOC files and VARS
  compendiums (section 6b) with their pytest checkers, re-run the self-compile
  proof after renaming. Carried into Phase 5 as background reading: the PASS1
  parser corners (functions 4270-4440, arrays 3285-3500, DATA/INPUT details) and
  PASS0. Open decisions for Mark (see below).
- Housekeeping: mypy strict (~35 errors in tasc/decomp, ~31 older in tasc/compiler).

### How the predictor is debugged
`python -m tasc.predict_check [family]` (summary), `python -m tasc.linediff
<family> <job>` (first differing source line, symbolic, address-normalised),
scratch `tokdiff.py` (token-level diff of that line). Random programs:
`python -m tasc.gen_random <family> <n> <seed> [--v2]` compiles them with the
real TASC (12 parallel emulators, ~2 s/program wall).

### Remaining unknowns
- None known in the compiler; the GUESS markers were resolved from PASS1's code
  (session 5). New behaviour can still surface in untested corners: compare with
  real TASC (`tasc.lift_checks`, `tasc.gen_random`) before trusting it.

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

- **Phase 5 integer declarations (Mark, 2026-10-25):** declare every integer
  scalar and array with `REM! INTEGER` (option 1), grouping related variables in
  the declaration lines where the hash-order constraints allow (option 3);
  INTEGER lines come before the COMMON declaration. Evidence: integer FOR loops in
  PASS1/PASS2 require INTEGER-declared names; reals in every pass rule out
  `INTEGER *`; PASS1's integers in first-use order would need 38 hash buckets.
- **Phase 5 line numbers (Mark, 2026-10-25):** steps of 10; a subroutine starts at
  the smallest multiple of 100 that is not the very next line number (after a
  routine ending at 90 the next starts at 200, after 150 at 200, after 190 at
  300). A GOSUB target that the previous line falls into (an alternate entry)
  stays inside its routine but skips one line number (previous line 50 -> entry
  at 70, not 60). Statement handlers reached by GOTO (PASS1's ON token-127 GOTO
  dispatcher targets) follow the same rules: a hundred boundary unless the
  previous line falls into them, then the skip-one-number rule. Range check: PASS1 ends near 18,500-20,300, PASS2 near 6,000, PASS0 near
  3,200 (Applesoft max 63,999). Numbers do not affect the object; only line
  boundaries are constrained. One statement per line except forced groupings.
  Frozen once Phase 5's DOC/VARS files are published; later changes carry
  documentation over by object address.

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
- Batch compiles: `tasc.batch.run_family(family, jobs)`; 12 workers ≈ 1 compile/s.
  Results cached by hash(source+options) in `experiments/<family>/<job>/`
  (source.txt, OBJ.bin, transcript.txt, result.json).
- Object parsing: `tasc.objfile.parse(obj, load, source)` renders code
  symbolically (`JSR X.op1`, `K(5%)`), naming variables via the allocation
  rule; `python -m tasc.explore <family> <job...>` prints listings.
- Family definitions live in `tasc/families.py`.

## Hypotheses

| | Status | Evidence / note |
|---|---|---|
| H1 shared RUNTIME/config | observed (supporting) | PASS0/1/2 load $41F2; headers: library end $17AF, one COMMON block $17B0-$41F1 (PASS0 defines, PASS1/2 use) |
| H2 options inferable | observed | all defaults: int arithmetic on (int ops on int vars), int constants on, RESUME/Debug off (no JSR $1423), library $0803, program right after COMMON |
| H3 hand-written parts identifiable | **confirmed** | none inside compiled code; tasc.classify: 0 foreign bytes in PASS0/1/2 |
| H4 deterministic | **confirmed** | phase0 runs A/B/C identical (C in a dirty session over an existing BALL.OBJ) |
| H5 names/line numbers lost | **confirmed** | no line table, debug calls or names in PASS files; regenerated names/numbers recompile identically |
| H6 RUNTIME hand-written | **confirmed** | no template patterns; flow analysis covers 3,925/4,013 bytes as hand code |
| H7 how ML was joined | **confirmed** | POKEd from DATA (PASS0: 89 bytes to $0377); recovering the source reproduces it |

## Facts established (details in RAG `phase0.md`, `phase1.md`)

- Object file = `JSR $0803` + 17-byte header (copied to zero page $12,$14,
  $69-$6E,$7B-$80,$16; confirmed from RUNTIME init) + code + constant pool
  + variable routines. Line 10 is at load+20.
- Variables/constants ordered by a 32-bucket hash, insertion order within.
  Names: h=(3*(c1-1)+c2+T)&31, T real 0/str 1/int 2, arrays +22; INTEGER-
  declared names keep T=0 and are entered at the declaration. Constants:
  low byte (int) / exponent (real) &31, entered at scan time with their
  natural type; other-typed forms entered when first generated.
- Constants are packed by the ROM's FIN (not correctly rounded): 3.14159 ->
  82 49 0F CF 82. `tasc/compiler/fin.py` is a bit-exact translation.
- Dead code: after GOTO / THEN line / RETURN / END / STOP / NEW the rest of
  the line's keyword statements are skipped unparsed; implicit assignments
  and DATA are still compiled. Quirk: `IF X THEN RETURN:Y=1` runs Y=1 when X
  is false.
- Expression codegen follows TASC's bottom-up parse: literal data and
  constant-table entries at scan time, code at reductions, one numeric and
  one string accumulator, pending results spilled to typed temps.
- String literals are inline: `JMP` over `[len][text]`.
- BALL.OBJ (defaults): $17B0, 1485 bytes, sha `7a37f061…`; 40-entry line table.
- CLINENUM is left as a 1-byte file after a compile.
- PASS1 is identical in 2.0 and 2.01; PASS0, PASS2 and RUNTIME differ (same
  lengths for PASS2 and RUNTIME).

## Open questions for Mark

- Phase 5 defaults still to confirm: how far names may
  stray from mnemonic when the hash forces it; the page-3 ML block stays in
  PASS0's DATA statements as in the original.

## Layout

```
tasc/disk.py       cp2 wrapper          tasc/emu.py      Pandowdy stdio client + screen capture
tasc/harness.py    compile driver       tasc/inventory.py  extract + hash all images
tasc/phase0.py     Phase 0 loop         docs/inventory.md  file table
docs/rag/*.md      RAG sources (push the whole file after editing)
src/launchers/     detokenized small Applesoft programs
extracted/<img>/   exact file data, NAPS-suffixed names (#TTAAAA)
```
