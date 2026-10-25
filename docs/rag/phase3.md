# TASC project: Phase 3 (decompiler front end and PASS-file source recovery)

Session 4 (2026-10-25). Tools: `tasc/decomp/` (walk.py, lift.py, render.py, names.py, decompile.py), `python -m tasc.decomp.decompile --pass | --corpus [prefix] | <family> <job> | --file OBJ load`, `python -m tasc.selfcompile [PASSn ...]`. Generated sources: `src/generated/PASSn.bas` (tokenized) and `PASSn.txt` (listing). Results of real-TASC compiles: `experiments/p3_selfcompile/<pass>/summary.json`.

## [confirmed] H5: no line numbers or names survive in the PASS files

Evidence: the PASS files carry no line table (the line-number table is printed by PASS2 and only CLINENUM, a scratch file, holds it during a compile); no RESUME/Debug calls (JSR $1423) that would mark statements; string literals (all listed by `tasc.classify`) hold no line numbers or variable names. Line numbers and names are generated (handoff section 6b). Only constraints survive: branch targets must start lines, and names must reproduce the 32-bucket hash order of allocation and routines (below).

## [confirmed] Decompiler design (object -> tokenized Applesoft, verified by recompiling)

1. `walk.py` decodes the code section into semantic ops: routine entry + op number, RUNTIME call (name, integer variant, inline words: STRLIT/FOR/NEXT/ONERR words, ON lists), ROM call, JSR/JMP inside the object, string literal (JMP over [len][text], accepted only if a STRLIT word points at it; a JMP whose next byte equals its distance-4 is otherwise a coincidence, e.g. after BNE *+5 in r1002), DATA block, RTS, BNE/BEQ pieces, flag loads, LDA/ORA tests. Constants reached only by LDA/ORA (AND/OR operands) have no routine: the constant pool starts at the lowest such address.
2. `lift.py` runs an abstract machine mirroring codegen: numeric accumulator + ARG (MOVAF, op6, IMOVE), string "loaded" register + string stack (complex string results are pushed), typed temps, subscript stack (PUSH.SUB), PUSH.BYTE, SAVE.* registers, comparison pending after op5, AND/OR memory operand from LDA. Canonical operand order so the predictor regenerates the bytes: `acc op M` for + * and comparisons, `M op acc` for - / ^ and AND/OR, and a temp always holds the source's left operand (relation swapped back). After a store (op1) the accumulator holds the variable with a "peephole" mark: a statement that uses it without reloading must stay on the same line. This includes stores by READ and GET.
3. Temps: the lowest local slots (numeric before FN parameters, FN-body temps referenced only inside bodies, strings first in the string area) whose every write is followed by a fresh value and every read follows a write within one statement; statement ends = statement calls, control flow, or stores to non-temps (fixed point). DEF FN = JMP over [P.op1, expression, RTS].
4. `render.py` lays out lines: a line starts at every branch target and after any unconditional transfer; `IF c THEN` keeps its statements up to the next-line address; peephole joins. Constants are rendered as the shortest decimal text that the ROM's FIN packs to the stored bytes. Lines are rendered straight to tokens, so literals and DATA may hold any byte.
5. `names.py`/`decompile.py` choose names (below). Statements merge when no RESUME/Debug call or line start separates them (NEXT A,B; READ A,B; HPLOT .. TO ..).

Corpus status: 1,479 of 1,528 recorded compiles round-trip byte for byte (remaining: FRE/POS arguments that are never evaluated, RESUME-option programs, some random-program corner cases).

## [confirmed] Names that reproduce TASC's allocation order

Allocation and the routine list are both projections of the symbol-table order (bucket, insertion seq). Declarations are generated first: `REM! INTEGER` for every integer scalar and array (INTEGER-declared names are entered at the declaration, in an order the decompiler chooses; type hash T=0), then the COMMON declaration in address order, then DIM for other local arrays. The solver builds one DAG per group (numeric scalars, numeric arrays, strings) from each unit's address order and routine order, marks an edge "strict" when the later symbol was entered earlier (scan order from a provisional compile, declaration classes otherwise), and assigns buckets by a longest-path pass spread over 0-31; names are then picked per bucket (h = (3*(c1-1)+c2+T) mod 32), avoiding keywords. Several files that share COMMON are solved jointly so a COMMON variable has one name in all of them. Evidence: the declaration trick was needed for PASS1 (73 local integer scalars; first-scan order needed 37 buckets), and all PASS numeric scalars are integers, so the original almost certainly used REM! INTEGER too.

## [confirmed] COMMON layout of TASC 2.01 (union of PASS0/1/2)

$17B0-$41F1 exactly covered, no gaps or type conflicts: 36 integer scalars ($17B0-$17F3), integer array (5,1) at $17F4 (24 bytes), integer array (5350) at $180C (10,702 bytes), then 12 string scalars $41DA-$41F1. PASS0 declares it (header flag $00), PASS1/PASS2 use it (flag $FF). Each pass references only part of it, so a pass's own object does not determine the whole layout.

## [confirmed] Predictor fix from PASS1: FN parameters and FN temps in creation order

PASS1 allocates `param1, temp(FN1), param2, temp(FN2), ...`: each DEF FN body gets temps of its own (not reused by the next function), and parameters and FN-body temps share one list in creation order (locals and routines). The predictor had one shared FN-temp pool after all parameters. Fixed in `codegen.py` (fn_pool per DEF) and `assemble.py` (fn_syms sorted by seq); all 1,530 recorded compiles still match.

## [confirmed] Regenerated PASS sources compile to the original files

Predictor: PASS0 (300 lines), PASS1 (1,330), PASS2 (492) decompile and recompile byte for byte. Real TASC in Pandowdy (default options, `python -m tasc.selfcompile`): PASS0 regenerated source -> SRC0.OBJ identical to PASS0 (7,803 bytes, sha256 e500a1ff..., 464M cycles). PASS1/PASS2: see experiments/p3_selfcompile.
