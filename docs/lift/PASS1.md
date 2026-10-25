# PASS1 lift notes (TASC 2.01): routine map and variables

Keyed by object address (stable across renumbering and renaming); the line number
is that of the generated source `src/generated/PASS1.txt` (session 4 numbering) and
the name is the generated name. Status: [code] = read from the decompiled code;
[confirmed] = also checked by real-TASC compiles (experiments p3_lift, predictor).

## Routine map

| Addr | Line | Routine | Notes |
|---|---|---|---|
| $4206 | 20 | init | copyright string; `AD(0..135) = BX(150+i)` (call-target table from COMMON); `AJ(16,2) = BX(300+...)` operator table |
| $42E9 | 115-170 | DEF FNs | FN A letter (65-90), FN AA digit, FN AB operator token (200-209, NOT 198, internal >=235), FN AC operator or ( ) or end, FN AD function token 210-227/229/230, FN AE string function 231-234/228, FN AF end of statement (`:` or 0), FN AG +32767 (word bias), FN AH operand is integer (CX(x,0) = -8 int temp, -9, -1 int), FN AI/AJ op classes, FN AK operand in the accumulator (CX(x,0) = -5 / -9) |
| $458C | 175-285 | start | prints, reads the first line (GOSUB 3050 x3, 3035) |
| $46B9 | 305-370 | statement loop | 310 `B3=0`; 315 end of statement -> 2435; 320 non-REM clears D2 (declarations must come first); **330 dead-code skip: `IF C8 AND GT<>131 AND GT<>178` (not DATA, not REM) -> 2485** [confirmed]; 335-370 dispatcher `ON token-127 GOTO` (three lists of 21/21/22); 375 letter -> implicit LET |
| $4801 | 395-500 | FOR | A7 = 1 for a **real** loop variable, 0 for an integer one (`A7 = -1 <> CK`; corrected session 6); init = variable op 20+A7+D4 (21-24, PASS2 turns it into JSR FOR.INIT entry + address word); limit entry 5 (real loop, 5390) or 125 (integer loop, 5400); no STEP: 129+A7 (IFOR.STEP1 / FOR.STEP1); STEP: 3 (real) / 126 (integer) |
| $489D | 505-545 | NEXT | entry 25 per variable, 0 word for a bare NEXT |
| $48CE | 550-645 | DATA | JMP over items, $FF, link word chained through C |
| $499D | 650-755 | INPUT | prompt literal via 3660; entries 39-44, 48 |
| $4A2A | 760-910 | DIM | 785: dimension list (<= 88 values per array, A4 0..32767), stored after the symbol |
| $4B80 | 915-955 | READ | |
| $4BC4 | 960-1015 | PLOT/HLIN/VLIN | entries 60, 120 |
| $4BFC | 1020-1095 | HPLOT | entries 122, 59 |
| $4C43 | 1100-1155 | DRAW/XDRAW | entry 86 for AT |
| $4C7E | 1160-1185 | ONERR | entry, then word chained to the line symbol; sets C8 |
| $4C93 | 1190-1195 | RESUME | with A8 (debug option) JMP entry, sets C8; else unsupported/ignored path |
| $4CA4 | 1200-1240 | LET | ON D4 GOSUB numeric/string/integer expression; 6465 store |
| $4CCF | 1245-1285 | GOTO, IF..GOTO | BEQ *+5 then JMP chained line (1245/1250); 1465 sets C8 |
| $4CF3 | 1290-1310 | **RUN** | debug call; `RUN` = JMP $03F5 (AC=1013); `RUN n` = JSR CLEAR (entry 61) + GOTO code [confirmed] |
| $4D1E | 1315-1405 | IF | 1325 flags (6585: LDA $9D or LDA $A0/ORA $A1); THEN GOTO / THEN n -> 1245; THEN RETURN -> 1430 (BEQ *+3, RTS); else BNE *+5, JMP next line, **B3=1, GOTO 315** (no debug call for the first statement after THEN) [confirmed] |
| $4DA2 | 1410-1425 | GOSUB | JSR chained line |
| $4DC6 | 1455-1470 | RETURN | RTS; 1465 `C8=1` (dead code follows) |
| $4DD8 | 1475-1865 | REM / REM! | INTEGER (needs D2=2; `*` sets BP=2), CLEAR COMMON (entry 127) / CLEAR CHAIN (128) **through the debug emitter** (1605) [confirmed], USECOMMON/DEFCOMMON (1630-1785: allocate, AM += size, BL = AM+20, CI = AM-4) |
| $5156 | 1880-1885 | STOP, NEW | call, C8 |
| $515C | 1890-1970 | ON | entry BR (+3 for GOTO), count byte, chained words |
| $51CF | 1975-2030 | WAIT | |
| $520A | 2035-2175 | DEF FN | 2060 redefinition check; BG = FN name, HV = parameter (CK=-3, chain 8); body via 3730; RTS; 5495 freezes the FN's temps |
| $52AD | 2180-2205 | POKE | |
| $52C2 | 2210-2300 | PRINT | `;` nothing, `,` entry 56, TAB 121 / SPC 84, items 50 (string) / 82 (number, 5390); CR entry 58 unless the statement ends in `;` `,` TAB SPC |
| $5382 | 2305-2345 | GET | |
| $53CB | 2370-2425 | one-argument statements, POP/CLEAR, ROM statements | 2370 via 5390 (CALL, HIMEM:), 2395 via 5400 |
| $53F5 | 2430-2480 | end of statement / line | listing, Ctrl-C check, next line; end: chain to PASS2 (`REM! CLEAR CHAIN`, BRUN PASS2) |
| $54D8 | 2485-2530 | warning: LINE NUMBER n IGNORED | used for unsupported keywords and for dead keyword statements; 2535 skips to `:` outside quotes |
| $5597 | 2575-2705 | expect / error kinds | SYNTAX, DECLARATION, SUBSCRIPT, TOO COMPLEX, TOO LONG, SYMBOL TABLE FULL, INCOMPLETE, OPERAND, REDEFINED, TYPE MISMATCH |
| $5807 | 2845-2885 | number conversion | ONERR-guarded `VAL(AG$)` |
| $5877 | 2920-3070 | token reader | GT current, GY lookahead; reads the source a byte at a time (CALL A1, PEEK(AO)); new line: BJ=0, C8=0, line number CG, line symbol defined at BL (2965-2985) |
| $59FC | 3075-3120 | line-number symbol | value-32767, chains AB + n mod AR |
| $5B68 | 3250-3280 | name scanner | **DC = 99*c1 + c2** (later characters skipped) [code] |
| $5BD5 | 3285-3500 | array reference | subscripts as triples; dims check |
| $5FAE | 3755-3810 | expression entry points | AA = 3 numeric, 2 string, 0 any |
| $5FE4 | 3810-4440 | expression scanner | constants (4160-4220), functions (4270-4315), unary + - NOT (4020-4055, minus = internal 239) |
| $6702 | 4585-4685 | relational tokens | two characters combined: >= => 235, <= =< 236, <> >< 237 |
| $67AB | 4690-4875 | shift-reduce | AO() operator/operand stack, AJ() priorities; reduce while stack priority > incoming; operator codes BU: 1 + 2 - 3 * 4 / 5 ^ 6 AND 7 OR 8 > 9 = 10 < 11 >= 12 <= 13 <> 14 NOT 15 negate 16 concat, 23-28 string relations, functions = token-181 |
| $6B16 | 5025-5055 | variable lookup/entry | bucket = (DC + CK) mod 32 (CK -3 real, -2 string, -1 int, +22 arrays; INTEGER-declared names hash as real) [confirmed]; appended at the chain's end |
| $6C56 | 5060-5095 | FN / line symbols | |
| $6D06 | 5100-5135 | symbol-table allocation in BX() | `SYMBOL TABLE FULL` when G9 > A5 (5350) |
| $6D4F | 5140-5245 | emitters | 5140: set op bit in the mask, write [op][chain word]; 5180: [opcode][chain word] (lines, FN); 5210/5195 word (+32767 bias) |
| $6F9E | 5380 | debug emitter | `IF A8 AND NOT B3` -> JSR entry 85 ($1423) [confirmed] |
| $6FC8 | 5390-5455 | call emitter | 5390 AP=3 / 5400 AP=1: entry -3 when the operand type D4 differs (the +-3 integer-entry rule); 5435 JMP |
| $7021 | 5460-5525 | temps | chains 5 int / 6 string / 7 real / 8 inside DEF FN; first free of the type, else new; 5485 free; 5495 freeze a function's temps [confirmed] |
| $715A | 5555-6410 | code generator over triples | D8 (operands real) / F7 (result real) per op (5640-5675); ops at 5745-6250; spill of a pending result to a temp at 6285-6375 |
| $7B9F | 6465-6510 | store of an expression result | CK=7 for an int target of a real value; `BJ=AA: D7=BL` arms the peephole |
| $7C5A | 6515-6580 | operand load/apply | 6550 int operand in real mode: op+6; integer constant -> its real form; **6555 peephole: skip a load (CK=0) or AND/OR test (CK=20) of the symbol just stored when the store is the last 3 bytes** [confirmed] |
| $7DF9 | 6585-6605 | flags for IF | |
| $7E1C | 6610- | termination | restore DOS patches from AX(5,1) |

## Variables (selected)

| Name | Addr | Meaning |
|---|---|---|
| GT / GY | $8F96 / $8FA4 | current token / lookahead byte |
| CG | $8FB6 | current source line number |
| BL | $17DA (COMMON) | current object address (code being written) |
| AM | $17D6 (COMMON) | program start (moved up by COMMON declarations) |
| BX() | $180C (COMMON, 5350) | symbol table: chains of entries; G9 next free, A5 = 5350 limit |
| AD() | $93AD | call-target table (136 entries, from PASS0 DATA via COMMON BX(150..)) |
| AJ() | $900F | operator table (17 x 3: token, stack priority, input priority) |
| AO() | $907F | parser stack (operators grow up from BE, operands down from CL) |
| CX() | $9149 | triple table (op, left, right); CF count, C6 current |
| AN / BA / DX / AC | $8FBB / $8F8A / $8F7B / $8F83 | call-table index / entry adjustment (0, -3) / byte to emit / word to emit |
| CK | $8FC7 | operand type or op number, by context |
| DC | $8FB0 | name hash value 99*c1+c2, or line number - 32767 |
| D4 | $9005 | expression type: 1 int, 2 string, 3 real |
| C8 | $9009 | dead code: set after an unconditional transfer, cleared at a new line |
| B3 | $8FE2 | first statement after THEN (no debug call) |
| A8 | $17EA (COMMON) | RESUME/Debug option |
| AF / BO | $17EC / $17EE (COMMON) | integer arithmetic / integer constants options |
| BP | $8FCF | 2 while INTEGER-declaring (also `INTEGER *`) |
| D2 | $8FF7 | 2 = declarations still allowed, 1 = after COMMON, 0 = after a statement |
| BV | $17F2 (COMMON) | COMMON kind: -1 none, 0 define, 255 use |
| BG / HV | $8F9E / $8FA8 | inside DEF FN: function name hash / parameter symbol |
| BJ / D7 | $8FB4 / $8F75 | last stored symbol and its address (peephole) |
| D8 / F7 / B2 | $8F7D / $8F94 / $8FDC | operands real / result real / flags already set |
| BN | $17F0 (COMMON) | fatal error seen |
