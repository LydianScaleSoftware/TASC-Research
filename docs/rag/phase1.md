# TASC project: Phase 1 (empirical templates)

All findings below are for TASC 2.01 with RUNTIME at $0803 and default memory, from controlled one-statement compiles in Pandowdy (`tasc.batch.run_family`; results in `experiments/<family>/<job>/`). Status "observed" = consistent across all compiles so far but not yet byte-predicted by a model; the template data is in `tasc/templates/core.json`.

## [observed] Compile dialogue: MEMORY USAGE and OPTIONS prompts

Evidence: session 2 dialogue mapping (scratch script), now driven by `tasc.harness.Options.answers()`.

```
SOURCE FILE? <name>
OBJECT CODE FILE: (DEFAULT <name>.OBJ)?
MEMORY USAGE: DEFAULT CONFIGURATION?          RETURN = defaults; NO = ask:
  ADDRESS FOR LIBRARY: (DEFAULT 2051)?
  ADDRESS FOR PROGRAM: (NUMBER, 'HGR1', 'HGR2', OR DEFAULT END OF LIBRARY)?
  ADDRESS FOR VARIABLES: (DEFAULT END OF PROGRAM)?
  LIBRARY OCCUPIES 2051 - 6063 / PROGRAM BEGINS AT ... / VARIABLES BEGIN AT ...
  ARE THESE ADDRESSES CORRECT?                 NO repeats MEMORY USAGE
OPTIONS: DEFAULT CONFIGURATION?               RETURN = defaults; NO = ask each (no confirmation):
  COMPILATION LISTING: (DEFAULT YES)?
  PAUSE ON ERRORS: (DEFAULT YES)?
  INTEGER ARITHMETIC: (DEFAULT YES)?
  INTEGER CONSTANTS: (DEFAULT YES)?
  RESUME/DEBUG CODE: (DEFAULT NO)?
... compile ...
COMPILATION INFORMATION AND LINE NUMBER REFERENCE TABLE?
```

HGR1 puts the program at 16384 ($4000). A fatal error prints `*****FATAL ERROR / LINE NUMBER n / <kind> / <line with !ERR!> / TYPE CNTRL-C TO ABORT, ANY OTHER KEY TO CONTINUE:`; Pandowdy's key-wait heuristic does not catch that prompt, so the harness also stops on its text. Addresses accept `$hex`. Listing and pause options did not change the bytes of `10 END` (one sample).

## [observed] Variable routines: shapes, dispatchers and operation numbers

Evidence: p1_explore, p1_binop (208 compiles), p1_mixed.

Numeric routine: `(A2 op AD)* A2 op A0 hi A9 lo 4C disp`: one entry per operation used, highest op first. The `AD` (LDA abs) swallows the next `LDX #op`, so each entry falls through to the shared `LDY/LDA/JMP`. Dispatchers: real $1764, integer $0D06.

String routine: `38 A9 18 A0 hi A9 lo 4C 7F 0C`: +0 = SEC (load), +2 = the `18` (CLC) = store. Same skip trick.

Array routine: `38 A9 18 20 disp` + inline `[addr][ndims][max index]*ndims`; dispatchers $0B11 real, $0B14 string, $0B17 int. +0 = load element, +2 = element address (for stores). Constants use numeric routines with op 0 (and others: PASS1 uses op 5 etc.).

Real ops (M = the variable): 0 load FAC, 1 store, 2 FAC+M, 3 M-FAC, 4 FAC*M, 5 compare, 6 load ARG, 7 M/FAC. Integer ops: 0 load IACC, 1 store IACC, 2 add, 3 M-IACC, 4 mul, 5 compare; 6..13 = real ops 0..7 applied to the integer variable (6 load as real, 7 store FAC as int, 8 add, 9 sub, 10 mul, 11 compare, 12 ARG, 13 divide).

## [observed] Symbol table order: 32-bucket hash (variables and constants)

Evidence: p1_order (26 reals + 26 ints, forward/reverse insertion), p1_order2 (two-character names, digits, strings), p1_alloc2; the predictor in `tasc.objfile.symbol_hash` matches all 556 compiles (`python -m tasc.checkall`).

Variables are allocated, and get routines, in symbol-table order: bucket h = (3*(c1-1) + c2 + T) mod 32, where c1, c2 are 5-bit character codes (A=1 ... Z=26, '0'=16 ... '9'=25; c2 = 0 for a one-letter name) and T = 0 real, 1 string, 2 integer. Buckets are walked in ascending order; names in the same bucket keep insertion (source text) order. Examples: one-letter reals order A L W B M X C N Y D O Z E P F Q G R H S I T J U K V; K% ties with A (both bucket 0); B% ties with X.

Constants (the pool between code and routines) use the same 32-bucket scheme with bucket = low byte & 31 for integers (stored big-endian, so the second byte) and exponent & 31 for reals; insertion order within a bucket. All three PASS pools (55, 170, 52 constants) are in nondecreasing bucket order. Equal value as int and real = two entries.

## [observed] Local variable allocation and temporaries

Evidence: p1_alloc*, p1_temp (39 compiles), p1_mixed/arr.*.

Local space starts right after the object file (LOCBEG1+1). Order: expression temporaries first; then numeric scalars, numeric arrays, string scalars, string arrays (each group in symbol order; the array placement relative to symbol order is a hypothesis that matched all tests). Sizes: real 5, integer 2, string pointer 2; arrays = product(max index+1) * size with no header (default max index 10 per subscript; DIM generates no code). Temporaries: needed when both operands of an operation are complex (e.g. `A(1)+A(2)`); they take the first slots regardless of names, are reused across statements, and their count is the maximum depth (2 for `A(1)+A(2)*A(3)`). Integer and string temps are 2 bytes. Open: the DEF FN parameter is allocated first (like a temp), not by its hash; `REM !INTEGER` names.

## [observed] Store-load peephole

Evidence: p1_mixed/peep.* (12 compiles).

A store to V followed immediately, in the same line, by a load of V omits the load (`X=1:Y=X` = K(1).op0, X.op1, Y.op1); also for integers and strings, and `IF X` right after storing X just branches on the flags. Not done across a line boundary or with another statement between. The manual describes no optimizer; this one matters for byte-exactness and for the decompiler.

## [observed] Expressions: operand order, types and constants

Evidence: p1_binop, p1_mixed/unary.*, p1_mixed/const.* (88 compiles over the four ia/ic combinations).

Commutative `+ *`: E(left), right.op. Non-commutative `- /`: E(right), left.op3/op7 (ROM FSUB/FDIV compute mem-FAC). `^`: E(right), left.op6 (ARG), JSR $EE97. Comparisons: E(left), right.op5, JSR $1524 = / $1528 < / $1519 > / $1526 <= / $151B >= / $1517 <> (real 0/1, Z flag). AND/OR with a simple left variable: E(right), then the left variable tested in memory (`LDA exponent`, or `LDA lo/ORA hi` for an int), JSR $1511/$150B (real right) or $1503/$14FD (int right). NOT = E, JSR $1524. Unary minus: real JSR $EED0, int JSR $0CC3; literals are never folded (-5 = const 5 + negate). Unary plus: nothing.

Integer arithmetic option on: int op int for + - * and negate in IACC, then JSR $166E (float IACC) if a real is needed. Off: integers are floated (op6/op8...) and stored with op7. Integer comparisons stay integer either way; division is always real. Integer constants option: an integer-valued literal within ±32767 is an int constant where the context can use an int; a lone literal stored to a real is a real constant (`X=5`), but `X=2+3` uses int 2, int 3, int add, float. With the option off, all literals are real. 40000 and 32768 are always real.

String concatenation and compares: E(left), JSR $1135 (save string), E(right), JSR $10EF concat / $1582 = / $1532 < / $15B7 <>.

## [observed] Statement templates

Evidence: p1_stmt (44), p1_mixed/flow.*, io.*, print.*.

Direct ROM: HOME $FC58, TEXT $F399, GR $F390, HGR $F3E2, HGR2 $F3D8, NORMAL $F273, INVERSE $F277, FLASH $F280. END = JMP $1363 (and TASC always appends one JMP $1363 after the last line); NEW = JSR $1363; STOP $134B; RETURN = RTS; POP $097B; RESTORE $0963; CLEAR $08AA; REM, DIM, RESUME (debug off) = no code.

One argument: E then JSR: VTAB $149E, HTAB $14A7, COLOR= $0E77, HCOLOR= $15F4, SPEED= $161E, ROT= $15BB, SCALE= $15C4, CALL $173B, IN# $1448, PR# $143F, HIMEM: $08DB, DRAW $0E34, XDRAW $0E3B. When E is an integer, several use an entry 3 bytes higher (VTAB $14A1, COLOR $0E7A, PLOT $1600/$170D) or 3 lower (POKE address $173E vs $1741).

Multi-argument: PLOT a,b = a, $15FD, b, $170A; HLIN/VLIN a,b AT c = a, $15FD, b, $1608, c, $1716/$1722; POKE a,b = a, $1741, b, $1451; WAIT a,b[,c] = a, $1741, b, $145A | $15D6, c, $1466; HPLOT a,b = a, $15E8, b, $0DF4; HPLOT TO = ... $0DED; DRAW s AT x,y = s, $15CD, x, $15E8, y, $0DD9 (XDRAW $0DE0).

Flow: GOTO = JMP line; GOSUB = JSR line; IF E THEN stmts = E, BNE *+5, JMP next-line, stmts; IF E THEN n / THEN GOTO n = E, BEQ *+5, JMP n; ON E GOTO/GOSUB = E, JSR $14B0/$14B7, .BYTE count, .WORD lines; ONERR GOTO n = JSR $1637, .WORD n. FOR V=A TO B [STEP C] = A, JSR $09E5 (int A) / $09E8 (real A), .WORD &V, B, JSR $16BC/$16BF, then C, JSR $16B5/$16B8, or JSR $16AC for step 1; NEXT V = JSR $0A31, .WORD &V (NEXT without a name: .WORD 0?). The loop variable needs no routine. `FOR I%` is a syntax error (as in Applesoft); integer loops use REM !INTEGER.

PRINT: per item: string JSR $0EEE, real $1761, integer $175E; `,` JSR $148E; TAB( E, $146F; SPC( E, $147F; `;` nothing; JSR $DAFB (CR) unless the statement ends with `;`, `,`, TAB( or SPC(. `"A";X` and `"A"X` compile identically. String literal: JMP past `[len][text]`, then JSR $0EC5 + .WORD &len.

I/O: INPUT = JSR $1627, items ($12FD number, $1287 string, $1312 next number; prompt literal via $0EC2 + .WORD and $1300), each followed by the store, then JSR $1387. GET string $10CC, number $1399. READ number $13AC, string $13A9. DATA in place: JMP past items `[len][text]` (quotes removed, empty item = len 0), $FF, .WORD link to the next DATA block (0 = last); header DATAPTR points at the first. DEF FN F(P)=E: in place, JMP past body (P.op1, E, RTS); FN F(A) = E(A), JSR body.

## [observed] Functions

Evidence: p1_mixed/unary.* (46 compiles).

ROM direct after E (integers floated by op6): SGN $EB90, INT $EC23, ABS $EBAF, SQR $EE8D, RND $EFAE, LOG $E941, EXP $EF09, COS $EFEA, SIN $EFF1, TAN $F03A, ATN $F09E, USR JSR $000A. RUNTIME: PEEK $1747 (int arg $1744), PDL $172B, SCRN(a,b) = a, $15DF, b, $16EB; these three and LEN $0EB6 and ASC $0EAA return an int (JSR $166E to float). VAL $0E80, STR$ $11A9, CHR$ $1192 (int arg $1195), LEFT$ $11C4, RIGHT$ $11F2, MID$ two-arg $1227, three-arg s, n, $15DF, m, $1231. Quirk: FRE(x) and POS(x) do not evaluate x (JSR $0F13 / $1700 only), though x is still allocated.

## [observed] RUNTIME init and relocation

Evidence: disassembly of RUNTIME 2.01 $0803-$08EE.

$0803: JSR $FD8B; LDA #$4C; STA $3F5, $5B, $58 (JMP opcodes); PLA/TAX/CLC/ADC #$11 skips the 17 header bytes; $62/$63 = address of the caller's JSR. It reads the JSR's operand (the library address) and derives internal pointers from it ($83/$84 = lib+$169, $AF/$B0 FOR-pop vector, $59/$5A float-IACC vector), then copies 15 bytes from lib+$169 into $BA (CHRGET patch) and the header into zero page. Coding style (BIT-skip tricks `2C A9 01 2C A9 FF`) is hand-written assembly (H6 evidence).
