# PASS2 lift notes (TASC 2.01): routine map and variables

Keyed by object address; line numbers and names from `src/generated/PASS2.txt`
(session 4 numbering). PASS2 works on the symbol table BX() that PASS1 left in
COMMON and on the object file PASS1 wrote, in which every reference is still a
backward chain: a routine call is `[op number][chain word]`, a line/FN reference
`[opcode][chain word]`, words biased by +32767; the symbol holds the latest link.
Symbol entries (link-relative): +0 next, +1 reference chain head (-32767 = none),
+2 op bit mask / address, +3.. data (name hash, type, dims, constant bytes).

| Addr | Line | Routine | Notes |
|---|---|---|---|
| $425C | 60-85 | DEF FNs | FN A hi byte, FN AA lo byte, FN AB +32767, FN AC -32767, FN AD type with the COMMON +50 mark removed, FN AE floor(log2) |
| $42BC | 90-150 | collect line references | AG() pairs (chain head, target) for every line symbol (chains AB..AJ) |
| $4358 | 155-210 | shell sort of the pairs | |
| $449C | 215-295 | undefined line numbers | checked against CLINENUM; "UNDEFINED LINE NUMBER" |
| $4594 | 300-365 | FN references | "UNDEFINED FUNCTION" |
| $47C4 | 465-555 | **constant pool** | one walk over the constant chains (AW..AB-1) in bucket order; an entry whose reference chain is empty is unlinked and not emitted; real = 5 bytes, int = 2 bytes high byte first [confirmed by every recorded compile] |
| $4906 | 560-665 | **COMMON allocation** | declaration list from BX(0); numeric pass then string pass; sizes 2 (int, string), 5 (real), arrays prod(dim+1)*size; AR(3..5) = COMBEG1, NUMCOMEND, STRCOMEND |
| $4AC3 | 670-780 | routine area size | numeric 3*ops+6, string 10, array 9+2*dims |
| $4C27 | 785-805 | local start | after the routines, or the VARIABLES address (DY); AR(0) = LOCBEG1 |
| $4C79 | 810-840 | dispatcher table | `DATA 3937,1148,1283,782,785,788,478,482,475,485,558` + library = $1764 real, $0C7F string, $0D06 int, $0B11/$0B14/$0B17 arrays, then $09E1 $09E5 $09DE $09E8 $0A31 (FOR/NEXT entries with an address word) |
| $4D09 | 845-1350 | **routines and locals, three passes** | pass 1 numeric scalars: temp chains (5 int, 7 real), FN chain 8, variable chains in bucket order, then constants (no locals); a numeric routine only if its op mask is non-zero: ops highest first, `A2 op` with `AD` before every one but the first, then `A0 hi A9 lo 4C disp`; pass 2 numeric arrays (always a routine: `38 A9 18 20 disp`, address, ndims, dims; undimensioned = 10 each, 1280); pass 3 strings: string temps (chain 6), FN chain strings, variables, scalars and arrays interleaved, **always a routine** (1105, no op-mask check) [confirmed p3_lift fre_str]; locals allocated in the same order (constants and COMMON skipped) |
| $51C5 | 1355-1370 | highest address | |
| $5217 | 1375-1640 | **backpatching** | the object is walked in 256-byte pages from the end; each chain is followed and its links replaced: op byte <= 13 -> JSR routine entry for that op; 21-25 -> JSR FOR/NEXT entry + variable address; otherwise LDA (and ORA for an int) of the variable's storage (AND/OR tests) |
| $5592 | 1655-1785 | header | JSR library, then the 8 header words and the COMMON flag (BV, -1 -> 0) |
| $567F | 1800-2050 | report | COMPILATION INFORMATION AND LINE NUMBER REFERENCE TABLE |
| $5C37 | 2105-2205 | helpers | 2105 add an AG() pair; 2175 write one byte to the object file (POKE A,4 / POKE AO,DX / CALL AV) |

| Name | Addr | Meaning |
|---|---|---|
| AG() / B6 / FW | $66C9 / $666A / $6636 | reference pairs / count / limit 5900 |
| AR() | $667B | header words being built (LOCBEG1.., COMBEG1..) |
| AU() | $6699 | dispatcher and FOR/NEXT addresses (lo, hi) |
| BK | $6648 | next local address |
| BL | $17DA (COMMON) | object address being written |
| EC | $6654 | pass number 1-3 in the routine loop |
| DV | $6679 | op byte read back at a reference |
