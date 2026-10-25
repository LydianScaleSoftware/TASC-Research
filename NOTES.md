# TASC reverse engineering: project notes

Entry point for any new session. Read this first, then the handoff prompt
(`../TASC_handoff_prompt.md`) for the full mission and rules. RAG collection
**`TASC project`** holds findings as chunks (status in brackets in each title).

## Status (2026-10-25, session 2)

- **Phase 0: done** (session 1). `python -m tasc.phase0`.
- **Phase 1: exit criterion met (2026-10-25).** The Python predictor
  `tasc/compiler/` reproduces BALL.OBJ byte for byte and all 1,528 recorded
  real-TASC compiles, including 603 random programs in four batches
  (`python -m tasc.predict_check`, pytest `tests/test_compiler.py`). The last
  two fresh batches matched 197/200 and 199/200 on first contact before fixes.
  The predictor code (with its comments) is now the authoritative template
  set; `tasc/templates/core.json` is an earlier summary.
- **Phase 2: started (session 3).** Every byte of PASS0/1/2 classified
  (`python -m tasc.classify`): all template output, zero foreign bytes (H3).
  The only hand-written code in the PASS files is an 89-byte page-3 block
  POKEd from PASS0 DATA ($0377-$03CF, `ml/pass0_page3.hex`; H7). PASS0 also
  patches DOS 3.3 at $A633/$A649/$A7C4/$A96C (originals saved and verified).
- **Phase R: main areas documented (session 3).** `python -m tasc.rtdis`
  flow-disassembles RUNTIME (3,925/4,013 bytes code; rest classified; H6
  confirmed). Documented in RAG runtime.md / runtime-routines.md: RT.INIT,
  entry table, all three dispatchers, integer multiply, arrays, FOR/NEXT
  frames (measured in Pandowdy) and the RETURN-unwinds-FOR trick, POP,
  strings (literals in place, two string slots, compacting GC), INPUT/READ/
  GET, STOP/END, RESUME/Debug, ONERR/RESUME. DOS patches explained: they let
  TASC READ the tokenized source as a text file and use byte offsets > 32767.
- Open in Phase R: exact ONERR trigger path through the CHRGET patch (trace an
  error), per-routine notes for the graphics/statement entries, the PASS0
  operator table ($5005). Optional (Mark): reassemblable RUNTIME source.
- Next: Phase 3, lifting PASS1/PASS2 with the object parser and predictor.
  Cleanup: mypy.

### How the predictor is debugged
`python -m tasc.predict_check [family]` (summary), `python -m tasc.linediff
<family> <job>` (first differing source line, symbolic, address-normalised),
scratch `tokdiff.py` (token-level diff of that line). Random programs:
`python -m tasc.gen_random <family> <n> <seed> [--v2]` compiles them with the
real TASC (12 parallel emulators, ~2 s/program wall).

### Remaining unknowns (GUESS markers in tasc/compiler/codegen.py)
- String comparison with a simple left and complex right (swap assumed);
  RESUME/Debug list beyond the statements tested; temp naming (why main temps
  are int-first while FN temps follow creation order: probably hashed temp
  names; PASS1's code will tell).

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
| H2 options inferable | open | object start = default (right after COMMON), not HGR1 (session-1 reading corrected) |
| H3 hand-written parts identifiable | **confirmed** | none inside compiled code; tasc.classify: 0 foreign bytes in PASS0/1/2 |
| H4 deterministic | **confirmed** | phase0 runs A/B/C identical (C in a dirty session over an existing BALL.OBJ) |
| H5 names/line numbers lost | open | |
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
