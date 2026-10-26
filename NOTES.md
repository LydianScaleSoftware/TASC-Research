# TASC reverse engineering: project notes

Entry point for any new session. **Current handoff: `docs/handoff_phase5.md`** (Phase 5 in progress; Phases 3 and 4 closed; older: `docs/handoff_phase3.md`). Read this first, then the handoff prompt
(`../TASC_handoff_prompt.md`) for the full mission and rules. RAG collection
**`TASC project`** holds findings as chunks (status in brackets in each title).

## Status (2026-10-25, session 6)

- **Session 6: PASS1 statement-level commentary done** (PASS1.ann ~1,000 [lines]; 287 bare DOC lines left, all trivial). New tool `python -m tasc.annlist <PASS> [first [last]]`. Annotation fixes: IL = 1 for a REAL FOR variable; SG = value must be real; EC ($0947) resets the stack and DATA pointer.
- **Session 6: PASS0 annotated** (docs/lift/annot/PASS0.ann: its 22 local variables, 3 DEF FNs, routine headers, ~110 line comments; PASS0 added to DOCUMENTED). COMMON DP(I,0) holds the address as a signed word (FN SW), not address-32767.
- **Session 6: listings now round-trip.** Two defects found in the shipped .txt listings (present since session 5): the renderer collapsed double spaces inside string literals (PASS0 430/440), and names ending in A or T joined a following keyword when the listing is tokenized again (`VA THEN` -> V AT HEN, `KT OR` -> K TO R; real ROM behaviour). Fixed in tasc/decomp/render.py and names._ok (no name ends in A or T); pytest test_listing_retokenizes imports each PASSn.txt with cp2 and compares with PASSn.bas. Names are solved jointly over the passes (COMMON), so PASS0's preferences and the new rule changed names in all three passes; see the proof line below.
- **Session 6: PASS2 annotated** (docs/lift/annot/PASS2.ann: all 35 locals, 6 DEF FNs, ~40 routine headers, ~200 line comments; PASS2 added to DOCUMENTED, so all three passes are documented). All PASS2 routines are explained in the DOC: reference pairs and the shell sort, CLINENUM lookup, undefined line/FN reports, constant pool, COMMON allocation, routine-area size, the three routine/local passes (routine byte layouts), page-by-page backpatching (DATA chain, line/FN pairs, numeric op groups incl. FOR/NEXT and AND/OR, string/array routines), header, report. The standalone-documentation test now allows a word H1-H7 when it is a variable listed in that file's VARS compendium (the solver named a PASS2 variable H4). docs/lift/PASS2.md corrected: real constants are always written.
- **Session 6: HTML views and overviews.** tasc/docview.py writes src/html/: per program an annotated listing (routine sections with their comment above, line comments beside, variable meanings on hover, GOTO/GOSUB/THEN links, the compendium at the end) and an overview page; src/PASSn.OVERVIEW.TXT is the overview text. Overviews are hand-written templates in docs/lift/annot/<PASS>.overview.txt with {NAME} and [[$addr]] (a line link by object address), filled at generation so they follow renaming and renumbering; sourcegen writes the pass pages, `python -m tasc.docview` the MAKE RUNTIME pages. The standalone test covers the new files (HTML checked on its visible text). Preview: the `tasc-html` entry in /Users/mlong/RAG/.claude/launch.json serves src/html on port 8766.
- **Session 6: source disk.** `images/source/TASC 2.01 SOURCE.dsk` (built by `python -m tasc.sourcedisk`): bootable DOS 3.3 (cp2 `cdi ... 35trk dos` writes the DOS image), HELLO (banner + CATALOG), MAKE RUNTIME, PASS0, PASS1, PASS2 as tokenized A files identical to src/PASSn.bas; 289 sectors free. Checked in Pandowdy: boots, each program LOADs (PASS1 20,780 bytes, 15,571 free). `python -m tasc.sourcedisk --compile`: real TASC in drive 1 compiles each pass from the source disk in drive 2 (`PASSn,D2`, object to drive 2) into files identical to PASS0/1/2 (experiments/p5_sourcedisk/*/summary.json).
- **Session 6: RUNTIME source.** `python -m tasc.rtsource` writes src/RUNTIME.S (EDASM-style 6502 source, Mark's choice of syntax: labels <= 8 chars, ORG/EQU/DFB, `*` and `;` comments) from the flow disassembly and docs/lift/annot/RUNTIME.ann (equates for page zero/ROM, labels for every entry and internal target, 66 routine blocks, ~450 line comments, data runs), and checks it with tasc/edasm.py, a two-pass assembler for that subset with EDASM's zero-page rule: it assembles to RUNTIME byte for byte (pytest test_runtime_source_assembles). BIT-skip bytes and four absolute-on-page-zero instructions (LDA/CMP $00F1/$00F2/$00FF,X: stack-page access) are DFB. Findings: $109B-$10C7 is leftover assembler text (the BCS before it is always taken; the old notes started it at $109E); $0947 is RESETSTK (bottom-of-stack return into NORET); $1413 ERREXIT is the common error exit; CLEAR CHAIN returns into CLEAR. HTML: src/html/RUNTIME.html (assembler listing with links) and RUNTIME.OVERVIEW.html. Mark: EDASM cannot assemble a source that large, so (his choice) the disk copy is split into src/runtime/RUNTIME.S1-S6, single-spaced, at most 12K each (PART_LIMIT), cut at routine blocks; S1 holds the equates and ORG and each part ends with `CHN RUNTIME.Sn+1` (tasc/edasm.py follows CHN with one symbol table). src/RUNTIME.S stays as the combined reading copy. The source disk holds the six parts as DOS text files (20 sectors left); the check reads them back and assembles the chain to RUNTIME; DOS reads them line by line (checked in Pandowdy). With no room left for objects, `--compile` now writes the object to drive 1.
- **Session 6: verified with the real EDASM.** Mark supplied the DOS Tool Kit (images/original/DOSToolkit.dsk, 143,488 bytes = a 140K DOS 3.3 disk plus a 128-byte trailer `AF EC EE 00...`; images/work/dostoolkit.dsk is the trimmed 140K copy). EDITOR-ASSEMBLER 1.0 (1979, ASSM at $1200, EDITOR at $11FF); directives EQU ORG OBJ LST DFB PAGE ASC DCI DW MSB DDB DS REP CHR SKP DSECT DEND DO ELSE FIN CHN REL EXTRN ENTRY SBTL (CHN yes, no INCLUDE); editor commands include DRIVE, LOAD/SAVE, TLOAD/TSAVE, LENGTH; the editor buffer holds 30,208 bytes; keys typed ahead are dropped. `python -m tasc.edasmrun` boots the Tool Kit with the source disk in drive 2, RUN EDASM, DRIVE 2, ASM RUNTIME.S1: first run 13 errors because EDASM needs `ASL A` (a bare ASL/LSR/ROL/ROR is an error assembled as 3 bytes); after the fix: SUCCESSFUL ASSEMBLY: NO ERRORS, RUNTIME.S1.OBJ0 = RUNTIME byte for byte (sha256 3982a702...; experiments/p5_edasm/summary.json). tasc/edasm.py now rejects a bare accumulator opcode too. EDASM writes the screen with its own routine, so the harness's scroll capture keeps only the last screen.
- **Proof (session 6, final names after PASS2):** `python -m tasc.selfcompile PASS0/PASS1/PASS2`: real TASC compiles the regenerated sources (306, 1,345 and 504 lines) into files identical to PASS0/1/2 (sha256 e500a1ff..., 71768885..., 218d8a5b...; experiments/p3_selfcompile/*/summary.json). Full pytest 24 passed. Next: Mark's review of the DOC/VARS files; then the final proof for goal 5 (already passing) and freezing the numbering.


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
- **Phase 5: started.** MAKE RUNTIME done: `src/MAKE_RUNTIME.txt` (+ DOC/VARS)
  rebuilds RUNTIME byte for byte in Pandowdy (`python -m tasc.makeruntime`; RAG
  phase5.md). Sources: `python -m tasc.sourcegen` writes `src/PASSn.bas`
  (tokenized), `.txt` (listing), `.DOC.TXT`, `.VARS.TXT` from address-keyed
  annotations in `docs/lift/annot/` (COMMON.ann shared, PASS1.ann done for
  names, FNs, routine headers and key lines; PASS0/PASS2 locals not yet). Names:
  dynamic programming over the hash order maximises name quality; fallbacks are
  listed in `docs/lift/annot/PASSn.names.txt` (development side only). Checkers:
  pytest tests/test_source.py (DOC mirror, variables documented, safe names;
  DOCUMENTED = PASS1). `src/generated/` is the older raw decompiler output. Already done: PASS0/1/2 decompiled jointly (shared COMMON
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
- **Phase 5 variable names (Mark, 2026-10-25):** the ideal name conveys the
  variable's usage or meaning, from analysis of what the program does; keep that
  goal, and where the hash order forbids it fall back to a similar first letter
  with a second letter or digit chosen to fit the logic; never a keyword.
  Finding (2026-10-25): the storage order is determined by the names, so along
  each pass's allocation order the names' hash buckets must not decrease; with
  about 100 integers in PASS1 over 32 buckets most variables have a narrow bucket
  window. Result for PASS1: 13 names as preferred, about 89 keep the first
  letter, about 27 need a neighbouring first letter. Fallbacks are recorded on the
  development side (`docs/lift/annot/PASSn.names.txt`), not in the VARS file
  (standalone rule). Declarations: names sharing a bucket must keep their storage
  order, so groups interleave; short runs join the previous INTEGER line.
  Mark (2026-10-25): the resulting names are acceptable as long as they are
  documented well; no further naming tuning (single letters are already
  candidates, but each has only one bucket per type, so few survive). The effort
  goes into DOC/VARS quality.
- **Page-3 ML block (Mark, 2026-10-25):** stays in PASS0's DATA statements, loaded by
  the original FOR/READ/POKE loop and USR-vector POKEs (the DATA text and its split
  into four statements are fixed by the object; the original method is the only one
  that keeps PASS0 byte-identical). Its DOC lines describe the routines themselves
  (entry points, what each does), standalone.
- **Recovered-source documentation is standalone (Mark, 2026-10-25):** DOC and VARS
  files (and anything else shipped with the recovered sources) must read as written
  by a programmer on an original Apple II: no references to this repository (ml/,
  RAG, .md files), hypotheses (H1-H7), tools (Pandowdy, Python, cp2) or the
  reverse-engineering process. Explain the code in its own terms (addresses, ROM
  routines, DOS). Enforced by pytest test_source_documentation_is_standalone.
- **MAKE RUNTIME (Mark, 2026-10-25):** RUNTIME is hand-written (H6), so add an
  Applesoft program `MAKE RUNTIME` that POKEs RUNTIME's 4,013 bytes from DATA
  statements and BSAVEs `RUNTIME,A$803,L4013` (not in the manual; consistent with
  how the original was probably built). Proof: run it in Pandowdy and compare the
  saved file with the original RUNTIME byte for byte. The program must sit above
  $17AF while it POKEs $0803-$17AF (it relocates itself first: TXTTAB to $4001).

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

- None blocking. Phase 5 defaults all decided (see Decisions).