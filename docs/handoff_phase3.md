# Handoff: TASC reverse engineering, start of Phase 3

You are continuing a long-running project with Mark (experienced developer, deep Apple II background; he owns the tools and reviews the work). Sessions 1-3 completed Phases 0, 1, 2 and R. This session starts **Phase 3**.

## Read first (in this order)

1. **The original handoff prompt:** `/Users/mlong/research/tasc_project/TASC_handoff_prompt.md`. It holds the mission, goals, rules, phase plan, conventions (sections 5-8, 6a, 6b) and how to work with Mark. Everything in it still applies unless this document updates it.
2. **The project notes:** `/Users/mlong/research/tasc_project/tasc-re/NOTES.md` (status, decisions, hypotheses table, layout).
3. **The RAG collection `TASC project`** (see the list below). Search it before re-deriving anything. Search scope: `collections: ["TASC project", "Apple II programming", "Apple 2 Software"]`.

Repo: `/Users/mlong/research/tasc_project/tasc-re` (git, main branch; last commit `99ea06d`). Python dev tools are in `.venv` (`.venv/bin/pytest`, `.venv/bin/mypy`).

## Where things stand

- **Phase 0 (done).** Scripted loop: `python -m tasc.phase0`. TASC is deterministic (H4).
- **Phase 1 (done; exit criterion met).** The Python predictor `tasc/compiler/` (parse.py, codegen.py, assemble.py, fin.py) reproduces **BALL.OBJ byte for byte** and **all 1,528 recorded real-TASC compiles**, including 603 random programs (`python -m tasc.predict_check`; pytest `tests/test_compiler.py`). The predictor's code and comments are the authoritative template set; `tasc/templates/core.json` is an older summary. This predictor is the seed of the Phase 3 compiler: Phase 3's job is to make it *derived from* TASC's own code (lifting PASS1/PASS2), not just observed behaviour, and to cover anything the observations never exercised.
- **Phase 2 (done for the PASS files).** `python -m tasc.classify extracted/tasc201/PASSn#0641f2`: every byte of PASS0/1/2 is TASC template output; **zero foreign bytes** (H3 confirmed). The only hand-written code the PASS files use is an 89-byte block POKEd from **PASS0 DATA** to $0377-$03CF (`ml/pass0_page3.hex`, H7 confirmed): because it lives in DATA statements, recovering TASC's source reproduces it automatically. PASS0 also patches DOS 3.3 (6 bytes) so TASC can READ the tokenized source as a text file; the originals are saved in a COMMON array.
- **Phase R (done enough; reassemblable source deferred by Mark).** `python -m tasc.rtdis --listing docs/runtime/runtime_listing.txt`: RUNTIME is hand-written (H6 confirmed); 3,925/4,013 bytes are code, the rest classified. Documented: RT.INIT, TASC's entry table, the three variable dispatchers, integer multiply, arrays, FOR/NEXT frames (measured), strings and GC, INPUT/READ/GET, STOP/END, ONERR/RESUME (traced in Pandowdy), statement/graphics entries. **Mark will return to a reassemblable RUNTIME source later; do not start it now.**

## Hypotheses (from NOTES.md)

H1 shared config: supported (PASS0/1/2 all load $41F2 with one COMMON block $17B0-$41F1; PASS0 defines COMMON (flag $00), PASS1/PASS2 use it (flag $FF)). **H2 options: observed in session 3 as all defaults** (integer arithmetic on: integer ops on integer variables occur; integer constants on; RESUME/Debug off: no JSR $1423; library $0803; program start = default, i.e. right after COMMON; variables after the program). H3, H4, H6, H7 confirmed. **H5 (line numbers and names lost) is still open**: the PASS files carry no line table; plan to verify quickly, then generate per handoff section 6b.

## Phase 3 goal and suggested plan

Goal (original prompt section 9): lift PASS1's code generator and PASS2's backpatching into the IR, render to Python, and get a compiler that matches real TASC byte for byte on every test program, including BALL. Suggested route, building on what exists:

1. **Recover statement structure of the PASS files.** They are TASC output, so the decompiler direction applies: segment each PASS file's code into statements using the template knowledge in `tasc/compiler/codegen.py` and `tasc/objfile.py` (symbolic listing). Every JSR/JMP target inside the code is a line start (GOTO/GOSUB/IF/ON/ONERR/FOR-loop bodies, DEF FN bodies); DATA blocks and string literals are already delimited by `tasc.classify`. Variables are addressable as COMMON slots ($17B0-$41F1, declaration order) or locals (hash order), constants are in the pool. Build this as a reusable decompiler front end (it is also Phase 4).
2. **Use the predictor as the oracle:** a recovered statement is right when the predictor compiles it to the same bytes at that position. Work line by line; the predictor already handles the whole language subset, dead-code rules, temps, constants (FIN), allocation and layout.
3. **Lift the semantics** of PASS1 (parser, symbol table with the 32-bucket hash, expression parser with scan/reduce, code generator, constant handling) and PASS2 (backpatching chains, routine emission, allocation) into an IR; reconcile with `tasc/compiler/` and replace any rule that was only observed with the rule TASC's code actually implements. Known leads: the operator table in PASS0 DATA $5005 (token-keyed triples), the RUNTIME/ROM entry table in PASS0 DATA $4C99-$4F56 (positive = library offset, negative = negated ROM address), PASS2 DATA $4C7C (dispatcher and FOR/NEXT offsets), TASC's use of `USR(VAL(text))` + PEEK($0371..) to pack constants.
4. **Explain the remaining observed-only rules from the lifted code:** why main-program temps are int-first while FN-body temps follow creation order; the RESUME/Debug statement list; the string-compare swap (simple left, complex right); the "unparsed skip" after GOTO/THEN line/RETURN/END/STOP/NEW/ONERR (and RESUME with debug on).
5. Exit: the Python compiler matches real TASC on all test programs (rerun `tasc.predict_check`, add more random batches with `python -m tasc.gen_random <family> <n> <seed> --v2`).

Ask Mark before costly or irreversible choices (IR design if it diverges from section 6 of the original prompt, large refactors of tasc/compiler).

## Key facts to carry forward (details in RAG)

- Object file = `JSR <library>` + 17-byte header (copied to zero page $12/$14/$69-$6E/$7B-$80/$16) + code + constant pool + variable routines; locals follow. RUNTIME is relocatable via the caller's JSR operand.
- Symbol order: 32-bucket hash, names h = (3*(c1-1)+c2+T) & 31 (T real 0, string 1, int 2; arrays +22; INTEGER-declared names keep T=0 and are entered at the declaration); constants by low byte/exponent & 31, entered at scan time with natural type. Locals: int temps, real temps, FN params, FN-body temps (creation order), numeric scalars, numeric arrays, then strings (scalars and arrays interleaved by hash).
- Constants are packed by the ROM's FIN (bit-exact translation in `tasc/compiler/fin.py`), not correctly rounded.
- Expression codegen mirrors TASC's bottom-up parse: literal data and constant entries at scan time, code at reductions, one numeric and one string accumulator, pending results spilled to typed temps (with lookahead over later arguments).
- Dead code after GOTO/THEN line/RETURN/END/STOP/NEW/ONERR (RESUME if debug on): keyword statements skipped unparsed; implicit assignments and DATA kept. Quirk: `IF X THEN RETURN:Y=1` runs Y=1 when X is false.
- Lines up to the last COMMON declaration get address program-start+20 (a jump there lands in the COMMON block, manual 8.2.4).
- Runtime errors and BREAK print object addresses because RUNTIME keeps the statement's object address in CURLIN.

## Tools and how to use them

- `tasc/disk.py` (cp2 wrapper; use `extract_all`, cp2 can't name files with `/`), `tasc/applesoft.py` (tokens, Python tokenizer matching cp2: `tokenize_program`).
- Emulator harness `tasc/emu.py` spawns its **own** Pandowdy over stdio; `tasc/harness.py` (Options, compile driver); `tasc/batch.py` (`run_family`, 12 parallel emulators, ~2 s/program; results cached in `experiments/<family>/<job>/` with source.txt, source.bas, OBJ.bin, transcript.txt, result.json).
- `tasc/objfile.py` (parse an object: symbolic code, constants, routines; library-relocatable), `tasc/classify.py`, `tasc/rtdis.py`, `tasc/predict_check.py`, `tasc/linediff.py` and `tasc/tokdiff.py` (first differing line / token diff between TASC and the predictor), `tasc/gen_random.py`, `tasc/families.py`, `tasc/checkall.py`.
- Interactive Pandowdy MCP (`mcp__pandowdy__*`) for poking: to get a `]` prompt boot `images/work/tasc201.dsk`, wait for the key prompt, press Ctrl-C (PASS0 prints BREAK IN 21641); then `load_binary` RUNTIME at $0803 and an OBJ at its load address and `CALL` it. Use key waits, not `until_text`, when comparing state (RAG dead-end chunk). Compiles of PASS-sized sources will take far longer than BALL (~150M cycles); `harness.COMPILE_CYCLES` is 2e9.
- If the auto-mode safety classifier fails repeatedly, switch to read-only work (it happened once in session 2).

## RAG documents in collection `TASC project` (push the whole file again after editing; sources in `tasc-re/docs/rag/`)

- `phase0.md`: file inventory and hashes; launchers; Phase 0 procedure; BALL compile and line table; H4; object header (zero-page mapping, COMMON flag); string literals; dead end on `until_text`.
- `phase1.md`: compile dialogue (memory/options prompts); variable routines and op numbers; symbol hash; allocation and temps; store-load peephole; expressions/types/constants; statement templates; functions; RUNTIME init.
- `phase1-predictor.md`: the predictor and every rule it needed (FIN, symbol entry times, layout, scan/reduce codegen, flags/IF, dead code, integer entry points, RESUME/Debug list).
- `phase2.md`: H3 and H7 (page-3 block), DOS patches and their purpose, compiler data tables in PASS DATA.
- `runtime.md`: H6, RT.INIT, TASC's entry table, real/string/integer dispatchers.
- `runtime-routines.md`: integer multiply, arrays, FOR/NEXT frames (measured), strings and GC, INPUT/READ/GET, STOP/END/ONERR/RESUME (traced), statement and graphics entries (+3/-3 rule).
- `runtime-index.md`: index of 166 RUNTIME routine starts with ROM calls and zero page.
- Reference collections: `Apple II programming` holds the commented Applesoft ROM source (`AppleSoft Commented.txt`, one chunk per routine: use it for FIN/FP/ERROR/HANDLERR/CHRGET), the DOS 3.2 listing, Beneath Apple DOS, The DOS Manual; `Apple 2 Software` holds the TASC manual (`TASC_Applesoft_Compiler_Manual.md`, section numbers as in the original prompt).

## Open items not in Phase 3's main line

- mypy strict reports ~31 errors (mostly `Ref` payload typing in `tasc/compiler/`); clean up when convenient.
- GUESS markers remaining in `tasc/compiler/codegen.py` (string compare swap; RESUME/Debug list beyond tested statements).
- Reassemblable RUNTIME source: deferred by Mark.
- Update NOTES.md at the end of each work block and push RAG chunks for new findings (dead ends too), per the original prompt section 8.
