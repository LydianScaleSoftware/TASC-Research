# Handoff: TASC reverse engineering, Phase 5 continued

You are continuing a long-running project with the project owner (experienced developer, deep Apple II background; owns the tools and reviews the work). Sessions 1-5 completed Phases 0, 1, 2, R, 3 and 4 and started Phase 5. This document says where Phase 5 stands and how to continue it.

## Read first, in this order

1. **The original handoff prompt: `/Users/mlong/research/tasc_project/TASC_handoff_prompt.md`.** Read all of it. It defines the mission and the five project goals (section 1), what is known about TASC (2), the hypotheses (3), the environment and tools, including how to use the **Pandowdy emulator MCP**, the **RAG server** and **CiderPress II (`cp2`)** (4), working principles (5), architecture (6), hand-written ML handling (6a), **the rules for recovered source and its documentation files (6b)**, repository conventions (7), knowledge management (8), the phase plan (9), pitfalls (10) and how to work with the project owner (12). Everything in it still applies unless NOTES.md records a later decision. The deliverable that matters most is goal 4 (TASC's own source with documentation), proven by goal 5 (the real TASC compiles it to the original files).
2. **The project notes: `/Users/mlong/research/tasc_project/tasc-re/NOTES.md`.** Status, every decision (with date and reason), hypotheses table, layout. The **Decisions** section holds the Phase 5 rulings; follow them exactly.
3. **The RAG collection `TASC project`.** Search it before re-deriving anything. Scope searches with `collections: ["TASC project", "Apple II programming", "Apple 2 Software"]`. Most relevant now: `phase5.md` (method and results so far), `phase3-lift.md` (TASC's rules as read from its own code), `lift-PASS1.md` and `lift-PASS2.md` (routine maps and variables by object address), `phase3.md` (decompiler design, COMMON layout, self-compile proof), `phase2.md` (PASS0 DATA tables, page-3 block, DOS patches), `runtime*.md` (the library). Reference collections: `Apple II programming` (commented Applesoft ROM source, DOS, Beneath Apple DOS), `Apple 2 Software` (the TASC manual).
4. Earlier handoff for background: `docs/handoff_phase3.md`.

Repo: `/Users/mlong/research/tasc_project/tasc-re` (git, main branch). Python dev tools in `.venv` (`.venv/bin/pytest`, `.venv/bin/mypy`). Read the Pandowdy MCP README (`~/develop/pandowdy-mcp/Pandowdy.Mcp/README.md`) before driving the emulator by hand; the Python harness (`tasc/emu.py`) spawns its own Pandowdy over stdio, so most emulator work runs from scripts.

## Where things stand

- **Phases 0, 1, 2, R: done** (sessions 1-3).
- **Phase 3: closed.** The Python compiler (`tasc/compiler/`) matches real TASC byte for byte on all 1,954 recorded compiles and rejects all 237 programs TASC rejects (`python -m tasc.predict_check`). Its rules were lifted from PASS1/PASS2's own code where read, and confirmed with targeted real-TASC cases (`python -m tasc.lift_checks [--unsup | --then]`).
- **Phase 4: closed.** The decompiler (`tasc/decomp/`) round-trips all 1,954 compiles, BALL.OBJ and PASS0/1/2 (`python -m tasc.decomp.decompile --corpus`, `--pass`).
- **Phase 5: in progress.**
  - **MAKE RUNTIME: done.** `src/MAKE_RUNTIME.txt` (+ `.DOC.TXT`, `.VARS.TXT`) POKEs RUNTIME from DATA and BSAVEs it; run in Pandowdy it rebuilds RUNTIME byte for byte (`python -m tasc.makeruntime`).
  - **Source generator: done.** `python -m tasc.sourcegen` writes `src/PASSn.bas` (tokenized program), `src/PASSn.txt` (listing), `src/PASSn.DOC.TXT` and `src/PASSn.VARS.TXT` for PASS0/1/2, from annotation files. **The real TASC compiles all three generated sources into files identical to PASS0, PASS1, PASS2** (`python -m tasc.selfcompile`; results in `experiments/p3_selfcompile/<pass>/summary.json`).
  - **Annotations:** `docs/lift/annot/COMMON.ann` (all 46 COMMON variables, shared by the passes) and `docs/lift/annot/PASS1.ann` (all PASS1 variables and DEF FNs, about 80 routine headers, a few line comments) are written. **PASS0 and PASS2 have no annotation files yet** (their own variables use solver names, their DOC files are mostly bare).
  - **PASS1 statement-level commentary: done (session 6).** About 1,000 `[lines]` entries; 287 of 1,346 lines keep a bare `n REM` (RETURN, plain GOTO, PRINT). `python -m tasc.annlist PASS1 [first [last]]` prints the address-keyed listing with preferred names in braces (use it to find `[lines]` keys). Corrections found on the way (IL, SG, EC meanings) are in RAG phase5.md.

## The Phase 5 decisions (details in NOTES.md, Decisions)

- Every integer is declared with `REM! INTEGER`, grouped by meaning where the hash order allows; INTEGER lines come before the COMMON declaration.
- Line numbers: steps of 10; a routine start (GOSUB target, or ON GOTO/GOSUB target such as PASS1's statement handlers) begins at the smallest multiple of 100 that is not the very next number (after 90 comes 200); a routine start reached by fall-through skips one number instead (after 50 comes 70).
- Names should say what a variable is for; where the hash order forbids the preferred name, fall back to a similar first letter with another letter or a digit, never a keyword. The current results were accepted ("anything will be ok so long as they are documented well"): do not spend more effort on naming; put it into the documentation.
- The page-3 machine-code block stays in PASS0's DATA statements with the original READ/POKE loop (required for byte identity).
- **Recovered-source documentation is standalone.** DOC and VARS files must read as if written by a programmer on an original Apple II: no references to this repository, RAG, `.md` files, hypotheses (H1-H7), tools (Pandowdy, Python, cp2, predictor, decompiler) or the reverse-engineering process. Describe the code in its own terms (addresses, ROM and DOS routines, what the program does). `tests/test_decomp.py::test_source_documentation_is_standalone` enforces this. Project notes and RAG may still refer to tooling.
- Comments are upper case (Apple II style).

## How the annotation loop works

Annotation file format (`docs/lift/annot/<PASS>.ann`, development files, never shipped):

```
[names]     $addr NAME group MEANING      a variable, keyed by its storage address
[fns]       $addr NAME PARAM MEANING      a DEF FN, keyed by its body address
[routines]  $addr TITLE                   comment on a routine's first line
[lines]     $addr COMMENT                 comment on the line that starts at addr
```

- Keys are **object addresses**, which never change with renaming or renumbering. To find a line's address, generate an address-keyed listing (a few lines of Python over `decompile_many(pass_units())`: `u.line_addr` maps line number to address; see how this session did it in the scratch scripts, or write it into a small tool).
- Write names inside meanings and comments as `{NAME}` (the *preferred* name; arrays as `{SY}()`, strings as `{W$}`). The generator replaces them with the final names. A plain-text name in a comment goes stale when the hash order forces a fallback.
- `docs/lift/annot/PASSn.names.txt` (generated) lists preferred name -> final name.
- The generator writes every source line into the DOC file: the declaration lines list their variables' meanings, routine starts get the routine comment, DEF FN lines get the function's meaning, a variable's first definition gets "NAME IS ...", and lines without a comment get a bare `n REM`. Several entries per line are allowed.

The loop, after each batch of annotations:

1. `.venv/bin/python -m tasc.sourcegen`: regenerate; it asserts each pass still recompiles identically with the Python compiler.
2. `.venv/bin/pytest -q tests/test_source.py` (DOC mirrors the source's line numbers, every variable documented where first defined, safe names) and `tests/test_decomp.py -k standalone`. When a pass's annotations are complete, add it to `DOCUMENTED` in `tests/test_source.py`.
3. **If names may have changed** (new or changed `[names]` entries, solver changes), **re-run the real-TASC proof**: `python -m tasc.selfcompile PASS0`, `PASS1`, `PASS2` (three background processes in parallel take about 3 minutes; PASS1 is about 1.7G emulated cycles). Comment-only changes do not change the program, so they need no new proof, but re-prove before the final deliverable anyway.
4. Commit; update NOTES.md and push RAG chunks (whole file, per the original prompt section 8).

## Next steps

1. ~~PASS1 statement-level commentary~~ (done in session 6; a review may still adjust wording). It was done routine by routine, using the routine map (`docs/lift/PASS1.md`, RAG `lift-PASS1.md`) and the generated listing `src/PASS1.txt`. Say what each line does in the program's terms: which token is checked, what is written to the object file, which library or ROM routine a call-table index selects (the table is PASS0 DATA lines, copied into `CT()`), why. Also extend the `[lines]` and `[routines]` coverage the generator already uses.
2. ~~PASS0 annotations~~ (done in session 6: docs/lift/annot/PASS0.ann). Originally: its own variables (dialog, file names, address parsing, DATA tables for the DOS patches, call table, operator table and page-3 block) and comments. Its DOC entries for the page-3 DATA lines and POKE loop describe the routines themselves (entry points: $0377 USR packs FAC into $0371-$0375; $037E read byte into $0376; $0387 write byte; $038D list the tokenized line at $0280 through the ROM keyword table).
3. ~~PASS2 annotations~~ (done in session 6: docs/lift/annot/PASS2.ann). Originally: backpatching, constant pool, COMMON allocation, routines and locals (routine map in `docs/lift/PASS2.md`).
4. Background reading still open from Phase 3: the PASS1 parser corners (functions 4270-4440 in session-4 numbering, arrays 3285-3500, DATA/INPUT details) and PASS0. If the reading turns up behaviour the compiler lacks, confirm it on the real TASC (`tasc.lift_checks` style) before changing `tasc/compiler/`.
5. Final proof for goal 5: regenerate, re-run `python -m tasc.selfcompile` for all three passes, record it in RAG and NOTES.

## Things to watch

- **TASCAD** (session 6): dist/tascad.py is generated; after changing the compiler, decompiler or tasc/tascad.py run `python -m tasc.bundle` (pytest test_bundle_is_current fails otherwise).

- **Source disk** (session 6): images/source/TASC 2.01 SOURCE.dsk, rebuilt by `python -m tasc.sourcedisk` whenever the sources change; `--compile` re-proves it with TASC in drive 1 and the disk in drive 2.

- **Documentation views** (session 6): src/html/ (listing + overview per program) and src/PASSn.OVERVIEW.TXT are generated with the sources; edit docs/lift/annot/<PASS>.overview.txt, never the generated files.

- **Names are solved jointly across the passes** (COMMON names are shared), so adding or changing preferred names in one pass can rename variables in all three; re-prove all three passes after any [names] change. Listings must re-tokenize to the .bas (pytest test_listing_retokenizes); names may not end in A or T.

- **Never claim a proof that did not run.** After any change that can affect names or code, the earlier real-TASC results no longer apply to the new files.
- `cp2 export` writes into the current directory; run such commands in the scratchpad directory so no stray files land in the repo.
- The batch harness puts 8 jobs per disk (`tasc/batch.py JOBS_PER_DISK`); 20 filled the disk with larger programs.
- The harness ignores "TYPE CNTRL-C TO ABORT" inside a listed source line (PASS1/PASS2 print it themselves); only a row starting with it is the real error prompt.
- `src/generated/` is the older raw decompiler output (solver names, steps of 5); the Phase 5 sources are `src/PASSn.*`.
- Open housekeeping: mypy strict (~35 errors in `tasc/decomp`, ~31 older in `tasc/compiler`). RUNTIME source: done in session 6 on request (src/RUNTIME.S combined, src/runtime/RUNTIME.S1-S6 chained with CHN for EDASM, at most 12K each; `python -m tasc.rtsource`). Verified with the real DOS Tool Kit EDASM: `python -m tasc.edasmrun` assembles it to RUNTIME byte for byte.
- Ask the project owner before costly or irreversible choices. Report concisely with evidence.
