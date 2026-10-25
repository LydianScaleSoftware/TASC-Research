# TASC project: RUNTIME library (Phase R)

RUNTIME 2.01: 4,013 bytes loaded at $0803 ($0803-$17AF), SHA-256 3982a702... Listing: `docs/runtime/runtime_listing.txt` (from `python -m tasc.rtdis --listing`), routine index `docs/runtime/routine_index.tsv`.

## [confirmed] H6: RUNTIME is hand-written; every byte classified

Evidence: `tasc.rtdis` flow-following disassembly from TASC's own entry table (PASS0 DATA, 117 entries), the named entries and their integer partners: 3,925 bytes are reached as code (2,119 instructions, 28 of them overlapping in BIT-skip tricks). The rest: $096C-$097A (15) CHRGET patch data, copied by RT.INIT into $BA-$C8; $09B9-$09BD (5) code `LDX #$16 / JMP $D412` (RETURN WITHOUT GOSUB error, reached indirectly near the FOR-pop vector $09B0); $109E-$10C7 (42) leftover source text from the assembler buffer (`";:01120:RFP2:+1360:2    IF A DISK COMMAN`), unused; $1796-$17AF (26) `COPYRIGHT(C)1981,MICROSOFT` in high-bit ASCII. No TASC template patterns occur (no variable-access routines, no JSR $0803), and no RUNTIME code calls the inline-operand entries, so the flow analysis is not confused by inline data.

## [confirmed] RT.INIT ($0803) and the vectors it sets

Called by every object file as `JSR $0803` followed by the 17-byte header. It calls $FD8B (CROUT1), stores $4C (JMP) at $03F5 (& vector), $5B and $58, pops the return address and skips the header (ADC #$11), and reads the operand of the caller's own JSR to learn where the library is loaded (so RUNTIME works at any BLOAD address). From that base L it sets $83/$84 = L+$169 (the CHRGET patch, copied to $BA-$C8), $AF/$B0 = L+$1AD ($09B0, the FOR-pop routine) and $59/$5A = L+$0E6B ($166E, RT.FLOAT.IACC; $58 holds JMP). It then copies the header into zero page: +3..+6 to $12-$15, +7..+12 to $69-$6E (or, when the flag byte is $FF, compares them and raises error $A3 on a mismatch), +13..+18 to $7B-$80, flag to $16. Uses BIT-skip (`2C A9 01 2C A9 FF`).

## [confirmed] TASC's table of RUNTIME and ROM entries (PASS0 DATA)

PASS0 DATA at object $4C99-$4F56 holds about 200 integers: TASC's code generator's call targets. A positive value is an offset from the library base (2912 -> $0803+2912 = $1363 RT.END); a negative value is a negated ROM address (-57612 -> $E10C AYINT, -62352 -> $F390 GR). That is how compiled calls follow the library address option. For an operation with an integer and a real form the table holds one entry; the other is 3 bytes away (+3 for most, -3 for CALL, HIMEM:, POKE/WAIT address and PEEK). PASS2 DATA ($4C7C, 11 values) lists the offsets PASS2 needs to emit variable routines and FOR/NEXT: the real/string/int dispatchers ($1764, $0C7F, $0D06), the array dispatchers ($0B11/$0B14/$0B17), $09E1/$09E5/$09DE/$09E8 and NEXT $0A31. Saved as `docs/runtime_entries.json`.

## [confirmed] Real variable dispatcher RT.DISP.REAL ($1764)

Entered from a variable routine with X = operation, (Y,A) = address of the 5-byte value. A DEX chain maps the operation onto ROM routines, each with the memory operand at (Y,A): op0 LOAD.FAC.FROM.YA $EAF9 (then sets flags through $DE59), op1 STORE.FAC.AT.YX.ROUNDED $EB2B (TAX first), op2 FADD $E7BE, op3 FSUB $E7A7 (memory - FAC), op4 FMULT $E97F, op5 FCOMP $EBB2, op6 LOAD.ARG.FROM.YA $E9E3, op7 FDIV $EA66 (memory / FAC). This confirms the operation numbers inferred in Phase 1 from compiled code.

## [confirmed] String variable dispatcher RT.DISP.STR ($0C7F)

A string variable is a 2-byte pointer to [length][text] (the length lives with the value, manual 8.2.3). The string accumulator is $77/$78. Entered with (Y,A) = variable address: C=1 (the routine's SEC entry, op0) copies the pointer into $77/$78; C=0 (the CLC entry, op1) stores $77/$78 into the variable.

## [confirmed] Integer variable dispatcher RT.DISP.INT ($0D06)

Entered with X = operation, (Y,A) = address of a 2-byte integer stored high byte first. The integer accumulator IACC is $A0 (high) / $A1 (low); the integer argument IARG is $9E/$9F. A DEX chain dispatches: op0 ($0C9F) load IACC, flags from ORA; op1 ($0CB1) store IACC, flags from ORA; op2 ($0CED) IACC += var, overflow -> error $45 (OVERFLOW); op3 ($0CCB) IARG = var then RT.ISUBT ($0CDA) IACC = IARG - IACC (RT.INEG $0CC3 is the same with IARG = 0), overflow -> error $45; op4 ($0C9D -> $0C43) multiply; op5 ($0D35) compare var with IACC, A = -1/0/+1 like FCOMP; op7 ($0D5F) store FAC into the integer through Applesoft's LET path (FORPNT $85/$86, JMP $DA65, which rounds and range-checks); op6 and op8-13 float the variable and run the real operation through a shared path ($0DAE, X = real op index): op6 load as real, op8 add, op9 subtract implemented as NEGOP then add (M - FAC = -FAC + M), op10 multiply, op11 compare, op12 load into ARG, op13 divide. Evidence: listing $0C9F-$0DAE; matches the Phase 1 operation numbers.
