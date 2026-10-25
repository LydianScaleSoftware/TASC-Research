# TASC project: Phase 2 (PASS file classification)

Tool: `python -m tasc.classify extracted/tasc201/PASSn#0641f2 [--list]` (classes header/code/strlit/data/inline/const/routine/foreign; built on `tasc.objfile`).

## [confirmed] H3: the PASS files contain no hand-written machine code

Evidence: tasc.classify on PASS0/1/2 (TASC 2.01). Every byte is TASC template output: PASS0 7,803 = header 20, code 3,805, string literals 979, DATA 1,295, inline operands 228, constants 179, variable routines 1,297. PASS1 19,703 = header 20, code 14,521, literals 655, inline 393, constants 460, routines 3,654 (no DATA). PASS2 9,221 = header 20, code 6,505, literals 729, DATA 50, inline 182, constants 143, routines 1,592. Zero bytes fall outside the compiled-code vocabulary (JSR, JMP, LDA/ORA abs for AND/OR, BNE/BEQ over a JMP, BEQ over RTS, RTS, LDA $9D, LDA $A0 / ORA $A1, plus inline literal/DATA/FOR/NEXT/ONERR/ON-list bytes). Every JSR/JMP target outside the object is a known RUNTIME or ROM entry. The PASS files share COMMON $17B0-$41F1 (PASS0 defines it, PASS1/PASS2 use it) and all load at $41F2. So TASC's source is pure Applesoft plus REM! declarations; its machine code reaches the PASS files only through DATA (below), RUNTIME and the ROM.

## [confirmed] H7: hand-written code is POKEd from DATA (page-3 block)

Evidence: PASS0 DATA at $50CE-$51E6 (89 decimal values) loaded by `FOR I=887 TO 975: READ A: POKE I,A: NEXT` (object $5233), followed by `POKE 10,76: POKE 11,119: POKE 12,3` (USR -> JMP $0377). Preserved as `ml/pass0_page3.hex` (sha256 f75ed7b1..., load $0377-$03CF, fixed address) with `ml/pass0_page3.asm.txt`. Entries: $0377 USR = store FAC packed at $0371-$0375 (STORE.FAC.AT.YX.ROUNDED), so TASC converts a literal with USR(VAL(text)) and PEEKs the 5 bytes, i.e. through the ROM's FIN, consistent with the predictor's FIN finding; $037E RDKEY into $0376; $0387 COUT of $0376; $038D lists the tokenized line in the input buffer $0280, expanding tokens through the ROM keyword table $D0D0 (the compile listing). Because the block lives in DATA statements of TASC's own source, recovering the source reproduces it; no separate BLOAD or post-link step is needed.

## [confirmed] DOS patches made by PASS0 (bytes); purpose observed

Evidence: PASS0 DATA at $42A2 (18 values = 6 triples address, new byte, original byte) and the loop that READs them, saves the originals in a COMMON array and POKEs the new bytes: $A633-$A635 <- 4C 44 A6 (JMP $A644, replacing D0 0F 20), $A649 <- $FF (was $7F), $A7C4 <- $60 RTS (was $4D), $A96C <- $FF (was $7F). The original bytes were verified in Pandowdy against DOS 3.3 in memory before PASS0 runs (stopped at $41F2): A633: D0 0F 20 (in the sequence 20 8C A6 / D0 0F / 20 FC A2), A649: 7F (operand of AND #$7F, so the patch makes DOS keep bit 7 of characters), A7C4: 4D, A96C: 7F. After an interrupted compile (Ctrl-C in PASS0, which prints BREAK IN 21641, an object address) the patched bytes remain in memory, as the manual warns. The exact effect of the JMP at $A633 and the $A7C4/$A96C patches is still to be traced in the DOS code (Phase 2 follow-up). The saved originals let TASC restore DOS on a clean exit (manual 5.2).

## [confirmed] Compiler data tables in the PASS files

PASS0 DATA $4C99-$4F56: TASC's table of call targets (positive = RUNTIME offset from the library base, negative = negated ROM address); see RAG runtime.md. PASS0 DATA $5005 (51 values in triples, e.g. 40,1,14 / 41,13,1 / 198,13,14 / 200,9,8 ...): a table keyed by Applesoft token values (198 = $C6 NOT? 200-209 = + - * / ^ AND OR > = <, 235-239 functions), probably operator classes/precedences for the expression parser (to be confirmed when PASS1 is lifted). PASS2 DATA $4C7C: dispatcher and FOR/NEXT offsets used when PASS2 emits variable routines.
