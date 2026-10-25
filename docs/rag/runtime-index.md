# TASC project: RUNTIME routine index

Generated from `docs/runtime/routine_index.tsv` (`tasc.rtdis`). Columns: start, end (up to the next routine start), name (RT.* = named from compiled-code use in Phase 1; T_ = in TASC's entry table, not yet named; S_ = internal subroutine; E_ = integer/real partner entry), internal JSR/JMP references, ROM calls, zero-page locations used. Status: observed (structure from flow analysis; names from usage).

## [observed] RUNTIME routines $0803-$10CB

| Start | End | Name | Refs | ROM calls | Zero page |
|---|---|---|---|---|---|
| $0803 | $08A6 | RT.INIT | 0 | CROUT1 | $16 $33 $52 $58 $59 $5A $5B $62 $63 $75 $76 $83 $84 $AF $B0 $D8 $F4 $F5 |
| $08A7 | $08A9 | RT.CLEARCOMMON | 0 |  |  |
| $08AA | $08DA | RT.CLEAR | 0 |  | $14 $15 $16 $6F $70 $73 $74 $79 $7A |
| $08DB | $0962 | RT.HIMEM | 0 | GETADR | $16 $3C $3D $50 $51 $62 $63 $69 $6A $6B $6C $6D $6E $73 $74 $79 $7A $AF $B0 |
| $0963 | $096B | RT.RESTORE | 0 |  | $12 $13 $F6 $F7 |
| $096C | $097A | RT.CHRGET.PATCH(data) | 0 | $F114 | $B9 |
| $097B | $09DD | RT.POP | 0 |  | $62 $63 $AF $B0 |
| $09DE | $09E0 | RT.IFOR.INIT/R | 0 | AYINT |  |
| $09E1 | $09E4 | RT.IFOR.INIT | 0 |  |  |
| $09E5 | $09E7 | RT.FOR.INIT/I | 0 |  |  |
| $09E8 | $0A30 | RT.FOR.INIT | 0 | STORE.FAC.AT.YX.ROUNDED | $55 $56 $83 $84 $A0 $A1 |
| $0A31 | $0B10 | RT.NEXT | 0 | $EB82 FADD FCOMP LOAD.FAC.FROM.YA STORE.FAC.AT.YX.ROUNDED | $62 $63 $65 $83 $84 $A0 $A1 |
| $0B11 | $0B13 | RT.ARR.REAL | 0 |  |  |
| $0B14 | $0B16 | RT.ARR.STR | 0 |  |  |
| $0B17 | $0C6E | RT.ARR.INT | 0 | $DE59 LOAD.FAC.FROM.YA | $16 $55 $56 $62 $63 $64 $65 $77 $78 $79 $7A $83 $84 $8E $9E $9F $A0 $A1 $A2 $A3 $AA $AB $D9 $DC $DD |
| $0C6F | $0C7E | RT.ARR.STORE | 0 | STORE.FAC.AT.YX.ROUNDED | $D9 $DC $DD |
| $0C7F | $0CC2 | RT.DISP.STR | 0 |  | $55 $56 $62 $63 $77 $78 $A0 $A1 |
| $0CC3 | $0CD9 | RT.INEG | 0 |  | $62 $63 $9E $9F |
| $0CDA | $0D05 | RT.ISUBT | 0 |  | $62 $63 $9E $9F $A0 $A1 |
| $0D06 | $0DD8 | RT.DISP.INT | 0 | $DA65 $DE59 $DEE9 $E7C1 $E982 $EB21 $EB53 FCOMP FDIVT MOVAF NEGOP | $16 $62 $63 $64 $85 $86 $9D $A0 $A1 $A5 $AA |
| $0DD9 | $0DDB | RT.DRAW.AT | 0 | AYINT |  |
| $0DDC | $0DDF | T_0DDC | 0 |  |  |
| $0DE0 | $0DE2 | RT.XDRAW.AT | 0 | AYINT |  |
| $0DE3 | $0DEC | T_0DE3 | 0 |  | $65 |
| $0DED | $0DEF | RT.HPLOT.TO | 0 | AYINT |  |
| $0DF0 | $0DF3 | T_0DF0 | 0 |  |  |
| $0DF4 | $0DF6 | RT.HPLOT | 0 | AYINT |  |
| $0DF7 | $0E33 | T_0DF7 | 0 | $E6FE $F411 $F457 $F53A | $16 $50 $51 $A1 $F0 |
| $0E34 | $0E36 | RT.DRAW | 0 | AYINT |  |
| $0E37 | $0E3A | T_0E37 | 0 |  |  |
| $0E3B | $0E3D | RT.XDRAW | 0 | AYINT |  |
| $0E3E | $0E76 | T_0E3E | 0 | $E6FE $F605 $F661 | $1A $1B $65 $E8 $E9 $F9 |
| $0E77 | $0E79 | RT.COLOR | 0 | AYINT |  |
| $0E7A | $0E7F | RT.COLOR/I | 0 | $E6FE $F252 |  |
| $0E80 | $0EA9 | RT.VAL | 0 | $EC4A | $16 $77 $78 $83 $84 $B8 $B9 |
| $0EAA | $0EB5 | RT.ASC | 0 |  | $77 |
| $0EB6 | $0EC1 | RT.LEN | 0 |  | $77 $A0 $A1 |
| $0EC2 | $0EC4 | RT.STRLIT.PROMPT | 0 |  |  |
| $0EC5 | $0EED | RT.STRLIT | 0 |  | $16 $62 $63 $77 $78 |
| $0EEE | $0F0A | RT.PRINTSTR | 0 | OUTDO | $0E $16 $77 |
| $0F0B | $0F12 | RT.CLEARCHAIN | 0 |  | $80 |
| $0F13 | $10CB | RT.FRE | 0 | $E2F2 ERROR | $0D $14 $15 $55 $56 $62 $63 $64 $66 $6B $6C $6D $6E $6F $70 $73 $74 $80 $81 $82 $8A $8B $93 $94 $95 $96 $AD $AE $AF $B0 |

## [observed] RUNTIME routines $10CC-$148D

| Start | End | Name | Refs | ROM calls | Zero page |
|---|---|---|---|---|---|
| $10CC | $10DE | RT.GET.STR | 0 | $D553 | $55 |
| $10DF | $10EE | RT.CONCAT.T | 0 |  | $77 $78 $79 $7A |
| $10EF | $1134 | RT.CONCAT | 0 |  | $0D $0E $55 $56 $77 $78 $79 $7A |
| $1135 | $1191 | RT.PUSHSTR | 0 |  | $0D $14 $15 $55 $56 $6F $70 $77 $78 $79 $7A |
| $1192 | $1194 | RT.CHR | 0 | AYINT |  |
| $1195 | $11A8 | RT.CHR/I | 0 | $E6FE | $55 $A1 |
| $11A9 | $11C3 | RT.STR | 0 | $ED34 | $0D $55 |
| $11C4 | $11C6 | RT.LEFT | 0 | AYINT |  |
| $11C7 | $11F1 | T_11C7 | 0 | $E6FE | $0D $0E $55 $77 |
| $11F2 | $11F4 | RT.RIGHT | 0 | AYINT |  |
| $11F5 | $1226 | T_11F5 | 0 | $E6FE | $0D $0E $77 $78 |
| $1227 | $1229 | RT.MID2 | 0 | AYINT |  |
| $122A | $1230 | T_122A | 0 | $E6FE |  |
| $1231 | $1233 | RT.MID3 | 0 | AYINT |  |
| $1234 | $1286 | T_1234 | 0 | $DB5A $E6FE | $0E $10 $16 $64 $73 $74 $77 $78 |
| $1287 | $1289 | RT.INPUT.STR | 0 | $DB5A |  |
| $128A | $1297 | RT.INPUT.STR.PROMPT | 0 | INLIN | $71 |
| $1298 | $12FC | RT.INPUT.STR.NEXT | 0 | $DB5A | $0E $16 $71 $77 $78 |
| $12FD | $12FF | RT.INPUT.NUM | 0 | $DB5A |  |
| $1300 | $1311 | RT.INPUT.NUM.PROMPT | 0 | INLIN | $71 |
| $1312 | $134A | RT.INPUT.NUM.NEXT | 0 | $DB87 $EC4A | $16 $71 $B8 $B9 |
| $134B | $1362 | RT.STOP | 0 | $DB3A $ED19 CRDO | $75 $76 |
| $1363 | $1386 | RT.END | 0 | $D566 $D64B | $62 $63 $67 $68 $B1 |
| $1387 | $1398 | RT.INPUT.END | 0 | $DB3A | $71 |
| $1399 | $13A8 | RT.GET.NUM | 0 | $D553 $EB93 |  |
| $13A9 | $13AB | RT.READ.STR | 0 |  |  |
| $13AC | $1422 | RT.READ.NUM | 0 | $D863 $EC4A ERROR | $16 $77 $78 $B8 $B9 $D8 $F6 $F7 |
| $1423 | $143E | RT.DEBUG | 0 |  | $16 $75 $76 $F8 |
| $143F | $1441 | RT.PR# | 0 | AYINT |  |
| $1442 | $1447 | T_1442 | 0 | $E6FE $F1E8 |  |
| $1448 | $144A | RT.IN# | 0 | AYINT |  |
| $144B | $1450 | T_144B | 0 | $E6FE $F1E1 |  |
| $1451 | $1453 | RT.POKE.VAL | 0 | AYINT |  |
| $1454 | $1459 | RT.POKE.VAL/I | 0 | $E6FE $E77E |  |
| $145A | $145C | RT.WAIT2 | 0 | AYINT |  |
| $145D | $1465 | T_145D | 0 | $E6FE | $85 |
| $1466 | $1468 | RT.WAIT3 | 0 | AYINT |  |
| $1469 | $146E | T_1469 | 0 | $E6FE $E793 |  |
| $146F | $1471 | RT.TAB | 0 | AYINT |  |
| $1472 | $147E | T_1472 | 0 | $E6FE | $24 |
| $147F | $1481 | RT.SPC | 0 | AYINT |  |
| $1482 | $148D | T_1482 | 0 | $DB57 $E6FE |  |

## [observed] RUNTIME routines $148E-$160A

| Start | End | Name | Refs | ROM calls | Zero page |
|---|---|---|---|---|---|
| $148E | $149D | RT.COMMA | 0 | CRDO | $24 |
| $149E | $14A0 | RT.VTAB | 0 | AYINT |  |
| $14A1 | $14A6 | RT.VTAB/I | 0 | $E6FE $F259 |  |
| $14A7 | $14A9 | RT.HTAB | 0 | AYINT |  |
| $14AA | $14AF | T_14AA | 0 | $E6FE $F7EA |  |
| $14B0 | $14B2 | RT.ONGOTO | 0 | AYINT |  |
| $14B3 | $14B6 | T_14B3 | 0 |  |  |
| $14B7 | $14B9 | RT.ONGOSUB | 0 | AYINT |  |
| $14BA | $14FC | T_14BA | 0 | $E6FE | $16 $50 $51 $A1 |
| $14FD | $1502 | RT.OR/I | 0 |  | $A0 $A1 |
| $1503 | $150A | RT.AND/I | 0 |  | $A0 $A1 |
| $150B | $1510 | RT.OR | 0 |  | $9D |
| $1511 | $1516 | RT.AND | 0 |  | $9D |
| $1517 | $1518 | RT.NE | 0 |  |  |
| $1519 | $151A | RT.GT | 0 |  |  |
| $151B | $1523 | RT.GE | 0 | LOAD.FAC.FROM.YA |  |
| $1524 | $1525 | RT.EQ | 0 |  |  |
| $1526 | $1527 | RT.LE | 0 |  |  |
| $1528 | $152E | RT.LT | 0 |  | $9D |
| $152F | $1531 | RT.STRGE | 0 |  |  |
| $1532 | $1545 | RT.STRLT | 0 |  | $77 $78 $79 $7A |
| $1546 | $1548 | RT.STRLE | 0 |  |  |
| $1549 | $1581 | RT.STRGT | 0 |  | $66 $77 $79 $9D |
| $1582 | $15B6 | RT.STREQ | 0 | LOAD.FAC.FROM.YA | $77 $78 $79 $7A $9D |
| $15B7 | $15BA | RT.STRNE | 0 |  |  |
| $15BB | $15BD | RT.ROT | 0 | AYINT |  |
| $15BE | $15C3 | T_15BE | 0 | $E6FE | $F9 |
| $15C4 | $15C6 | RT.SCALE | 0 | AYINT |  |
| $15C7 | $15CC | T_15C7 | 0 | $E6FE | $E7 |
| $15CD | $15CF | RT.SAVE.SHAPE | 0 | AYINT |  |
| $15D0 | $15D5 | T_15D0 | 0 | $E6FE | $F0 |
| $15D6 | $15D8 | RT.SAVE.ARG3 | 0 | AYINT |  |
| $15D9 | $15DE | T_15D9 | 0 | $E6FE | $85 |
| $15DF | $15E1 | RT.PUSH.BYTE | 0 | AYINT |  |
| $15E2 | $15E7 | T_15E2 | 0 | $E6FE | $10 |
| $15E8 | $15EA | RT.SAVE.HX | 0 | AYINT |  |
| $15EB | $15F3 | T_15EB | 0 |  | $50 $51 $A0 $A1 |
| $15F4 | $15F6 | RT.HCOLOR | 0 | AYINT |  |
| $15F7 | $15FC | T_15F7 | 0 | $E6FE $F6EC |  |
| $15FD | $15FF | RT.SAVE.X | 0 | AYINT |  |
| $1600 | $1607 | RT.SAVE.X/I | 0 | $E6FE $F220 | $F0 |
| $1608 | $160A | RT.SAVE.Y | 0 | AYINT |  |

## [observed] RUNTIME routines $160B-$17AF

| Start | End | Name | Refs | ROM calls | Zero page |
|---|---|---|---|---|---|
| $160B | $161D | T_160B | 0 | $E6FE $F1FD | $2C $2D $F0 |
| $161E | $1620 | RT.SPEED | 0 | AYINT |  |
| $1621 | $1626 | T_1621 | 0 | $E6FE $F265 |  |
| $1627 | $1636 | RT.INPUT.BEGIN | 0 |  | $50 $51 |
| $1637 | $1655 | RT.ONERR | 0 |  | $5C $5D $62 $63 $D8 |
| $1656 | $165B | RT.RESUME | 0 |  | $DF |
| $165C | $165E | RT.PUSH.SUBSCRIPT | 0 | AYINT |  |
| $165F | $166D | RT.PUSH.SUBSCRIPT/I | 0 |  | $A0 $A1 |
| $166E | $1674 | RT.FLOAT.IACC | 0 | $E2F2 | $A0 $A1 |
| $1675 | $167D | RT.IMOVE | 0 |  | $9E $9F $A0 $A1 |
| $167E | $1686 | RT.IFOR.STEP1 | 0 |  | $A0 $A1 |
| $1687 | $1689 | RT.IFOR.STEP/R | 0 | AYINT |  |
| $168A | $168D | RT.IFOR.STEP | 0 |  |  |
| $168E | $1690 | RT.IFOR.LIMIT/R | 0 | AYINT |  |
| $1691 | $16AB | RT.IFOR.LIMIT | 0 |  | $16 $64 $65 $A0 $A1 |
| $16AC | $16B4 | RT.FOR.STEP1 | 0 | LOAD.FAC.FROM.YA |  |
| $16B5 | $16B7 | RT.FOR.STEP/I | 0 |  |  |
| $16B8 | $16BB | RT.FOR.STEP | 0 |  |  |
| $16BC | $16BE | RT.FOR.LIMIT/I | 0 |  |  |
| $16BF | $16EA | RT.FOR.LIMIT | 0 | STORE.FAC.AT.YX.ROUNDED | $16 $64 $65 $AF $B0 |
| $16EB | $16ED | RT.SCRN | 0 | AYINT |  |
| $16EE | $16FF | T_16EE | 0 | $E6FE $F220 $F871 | $10 |
| $1700 | $1709 | RT.POS | 0 |  | $24 $A0 $A1 |
| $170A | $170C | RT.PLOT | 0 | AYINT |  |
| $170D | $1715 | RT.PLOT/I | 0 | $E6FE $F220 $F228 |  |
| $1716 | $1718 | RT.HLIN | 0 | AYINT |  |
| $1719 | $1721 | T_1719 | 0 | $E6FE $F220 $F235 |  |
| $1722 | $1724 | RT.VLIN | 0 | AYINT |  |
| $1725 | $172A | T_1725 | 0 | $E6FE $F244 |  |
| $172B | $172D | RT.PDL | 0 | AYINT |  |
| $172E | $1737 | T_172E | 0 | $E6FE $FB1E |  |
| $1738 | $173A | RT.CALL/R | 0 |  |  |
| $173B | $173D | RT.CALL | 0 | $F1D8 |  |
| $173E | $1740 | RT.SAVE.ADDR/I | 0 |  |  |
| $1741 | $1743 | RT.SAVE.ADDR | 0 | GETADR |  |
| $1744 | $1746 | RT.PEEK/I | 0 |  |  |
| $1747 | $175D | RT.PEEK | 0 | GETADR | $50 $51 |
| $175E | $1760 | RT.PRINTINT | 0 |  |  |
| $1761 | $1763 | RT.PRINTNUM | 0 | $ED2E |  |
| $1764 | $17AF | RT.DISP.REAL | 0 | $DE59 FADD FCOMP FDIV FMULT FSUB LOAD.ARG.FROM.YA LOAD.FAC.FROM.YA STORE.FAC.AT.YX.ROUNDED | $AA |

