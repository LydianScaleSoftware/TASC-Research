# TASC project: Phase 0 (toolchain, inventory, first compile)

## [confirmed] File inventory of the TASC disk images

Evidence: `python -m tasc.inventory` (repo `tasc-re`), files extracted with cp2 v2.0.0-dev3 `extract --preserve=naps`; SHA-256 over exact file data (no DOS 4-byte header). Full table: `docs/inventory.md`, `extracted/inventory.json`.

Reference image: `TASC 2.01 (Microsoft 1981).dsk` (key `tasc201`), DOS 3.3, 16-sector. Banner: "MICROSOFT APPLESOFT COMPILER, VER 2.01 COPYRIGHT (C) 1981 MICROSOFT".

| File (2.01) | Type | Load | Length | SHA-256 (first 16) |
|---|---|---|---|---|
| HELLO | A | $0801 | 51 | launcher |
| APCOM | A | $0801 | 51 | identical text to HELLO |
| PASS0 | B | $41F2 | 7803 | e500a1ff... |
| PASS1 | B | $41F2 | 19703 | 71768885... |
| PASS2 | B | $41F2 | 9221 | 218d8a5b... |
| RUNTIME | B | $0803 | 4013 | 3982a702... |
| ADR | T | | 74 | |
| CREATE ADR | A | $0801 | 302 | |
| BALL | A | $0801 | 975 | demo source |

Cross-image: PASS1 is byte-identical on 2.0, 2.01 and asimov 2.0 (71768885). PASS2 and RUNTIME are identical on 2.0 and asimov (37e674f9, e891e25f) and differ on 2.01 (218d8a5b, 3982a702), same lengths (9221, 4013). PASS0 differs on all three (2.01 7803, 2.0 7592, asimov 7721). `TASC COMPILER.DSK` (key `rebuild`) has PASS0/1/2.OBJ at $3F0A (6957/19168/9132 bytes) and a 3969-byte RUNTIME: a different build, comparison only.

## [confirmed] Launcher programs (TASC, HELLO, APCOM)

Evidence: `cp2 export <image> bas <file>`; listings in `src/launchers/`.

2.01 HELLO and APCOM (identical):

```
10  PRINT  CHR$ (4) + "BLOADRUNTIME" +  CHR$ (13) +  CHR$ (4) + "BRUNPASS0"
```

2.0 `TASC` (the program the manual's `RUN TASC` refers to):

```
5  HOME
6  VTAB 10: PRINT "        MICROSOFT'S TASC                       APPLESOFT COMPILER"
7  PRINT : PRINT "         NOTE: FP PROGRAM MUST BE                      SAVED ON THIS DISK!"
10  PRINT  CHR$ (4) + "BLOADRUNTIME" +  CHR$ (13) +  CHR$ (4) + "BRUNPASS0"
```

So the compiler itself is run like any compiled program: RUNTIME is BLOADed at $0803 and PASS0 is BRUN at $41F2. 2.01 boots straight into PASS0 (HELLO is the greeting program). The rebuild disk's COMPILER does the same with PASS0.OBJ. 2.0 also has RUNNER (asks for a name, `EXEC RUN`) and the EXEC text file RUN (`BLOAD RUNTIME`, then `BRUN <name>.OBJ`).

## [confirmed] Phase 0 procedure: scripted compile in Pandowdy

Evidence: `python -m tasc.phase0` (about 40 s wall time for three compiles plus a run).

- `tasc/emu.py` spawns a private Pandowdy MCP server (`dotnet ~/.local/share/pandowdy-mcp/Pandowdy.Mcp.dll`, override with `TASC_PANDOWDY`) and speaks newline-delimited JSON-RPC to it. This is independent of the Pandowdy instance Claude Code uses.
- Screen capture: breakpoints at Monitor SCROLL $FC70 (log row 0 before each scroll) and HOME $FC58 (log the whole screen), then `step` off the breakpoint. The transcript keeps wrapped 40-column rows as separate lines.
- Dialogue (defaults): boot the copy of the 2.01 image (power_cycle, about 17.4M cycles to the prompt) -> `SOURCE FILE?` BALL -> `(DEFAULT BALL.OBJ)?` RETURN -> `MEMORY USAGE: DEFAULT CONFIGURATION?` RETURN -> `OPTIONS: DEFAULT CONFIGURATION?` RETURN -> compile (about 150M cycles) -> `COMPILATION INFORMATION AND LINE NUMBER REFERENCE TABLE?` YES -> `*****COMPILATION COMPLETE` and the `]` prompt.
- Then `save_disk` to a path, and extract `<SRC>.OBJ` and CLINENUM with cp2.
- Every wait is a key wait (`until_key_wait`); see the dead-end chunk on `until_text`.

## [confirmed] BALL compiled with defaults: object file and line table

Evidence: experiment `experiments/phase0` runs A/B/C; source BALL from the 2.01 image; options all default.

BALL.OBJ: type B, load $17B0 (6064 = end of RUNTIME, $0803+4013), 1485 bytes, SHA-256 `7a37f0610faa84698ab9786e9113bfc5f7c31d618a07d36de3a65ded1a911f5b`. CLINENUM after the compile is 1 byte ($0A as extracted by cp2, i.e. a single CR in the DOS text file), SHA `01ba4719...`.

Compilation information printed:

```
LIBRARY OCCUPIES 2051 - 6063
PROGRAM OCCUPIES 6064 - 7548
NO COMMON BLOCK
LOCAL VARIABLES OCCUPY 7549 - 7733
HIGHEST MEMORY LOCATION: 7733
```

Line table (line: decimal address): 10/20/30/40/50: 6084, 60: 6087, 70: 6167, 80: 6176, 90: 6244, 100: 6261, 110: 6327, 120: 6351, 130: 6375, 140: 6380, 150: 6398, 160: 6416, 170: 6438, 180: 6456, 190: 6491, 200: 6500, 210: 6514, 220: 6545, 230: 6562, 240: 6565, 250: 6570, 260: 6608, 270: 6611, 280: 6641, 290: 6683, 300: 6721, 310: 6759, 320: 6783, 330: 6827, 340: 6868, 350: 6912, 360: 6953, 370: 6977, 380: 7003, 390: 7030, 400: 7042.

Lines 10-40 (REM!, DIMs) generate no code: they share the address of line 50 (HOME = `JSR $FC58` at 6084).

Running it: `BLOAD RUNTIME`, `BRUN BALL.OBJ`, answer 3: lo-res mode with balls plotted and "PRESS ANY KEY TO EXIT-"; a key returns to `]` in text mode.

## [confirmed] H4: TASC is deterministic

Evidence: `experiments/phase0/summary.md`. A = fresh boot; B = second fresh boot; C = the same machine as A after running BALL.OBJ, then `RUN HELLO` and recompiling over the existing BALL.OBJ (dirty memory, different disk layout; 144.96M vs 150.24M cycles). The object files, line tables and CLINENUM are identical across A, B and C. Byte comparisons of compiler output are therefore valid. (Fresh boots in Pandowdy are also cycle-identical: the emulator is deterministic.)

## [confirmed] Object file header: JSR $0803 plus a 17-byte block copied to zero page

Evidence: BALL.OBJ, the PASS files, Phase 1 compiles; mapping confirmed by reading RUNTIME 2.01 init ($0803-$08A3). Supersedes the session-1 "observed" reading, which misnumbered the fields and wrongly suggested an HGR1 object start.

Every object file starts `20 03 08` (JSR $0803). RUNTIME init pops the return address, adds $11, and reads the block through ($62),Y. It also reads the operand of the JSR itself to locate the library, so RUNTIME is relocatable by BLOAD address. File offsets:

| Offset | Zero page | Meaning (manual Appendix F) |
|---|---|---|
| +3 | $12-13 | address of first DATA item (0 = none) |
| +5 | $14-15 | highest location used |
| +7 | $69-6A | beginning of COMMON - 1 |
| +9 | $6B-6C | end of numeric COMMON |
| +11 | $6D-6E | end of string COMMON |
| +13 | $7B-7C | beginning of local variables - 1 (= last byte of the object file) |
| +15 | $7D-7E | end of local numeric variables |
| +17 | $7F-80 | end of local string variables |
| +19 | $16 | flag: $00 = define COMMON (store +7..+12); $FF = COMMON must already match (compare, error $A3 on mismatch) |

```
BALL.OBJ: 00 00 | 35 1E | AF 17 AF 17 AF 17 | 7C 1D | 35 1E 35 1E | 00
PASS0:    A2 42 | DE 60 | AF 17 D9 41 F1 41 | 6C 60 | D0 60 DE 60 | 00
PASS1:    00 00 | BE 94 | AF 17 D9 41 F1 41 | E8 8E | BC 94 BE 94 | FF
PASS2:    7C 4C | E4 94 | AF 17 D9 41 F1 41 | F6 65 | E2 94 E4 94 | FF
```

So the PASS files share one COMMON block at $17B0-$41F1 (numeric $17B0-$41D9, 10,794 bytes; string $41DA-$41F1, 12 pointers), directly after RUNTIME. Their object code starts right after COMMON at $41F2, i.e. the default object start (end of library) moved up by COMMON, not HGR1. PASS0 defines COMMON (flag $00); PASS1 and PASS2 use it (flag $FF). PASS0 and PASS2 contain DATA.

## [observed] String literals are inline: JMP over [length][text]

Evidence: BALL.OBJ at 6087 (line 60): `20 27 16` (JSR $1627, RUNTIME), `4C E9 17` (JMP $17E9), `1B` (27), "HOW MANY BALLS (UP TO 10)? ", then code at $17E9. All three PASS files start (after the header) with `4C 24 42 1A` + 26 bytes of "COPYRIGHT..." text, so their copyright string is a compiled string literal in the first statement, not data appended after compilation.

## [dead-end] until_text snapshots are mid-execution: don't compare screens taken at them

Evidence: experiment in session 1 (scripts `bp2.py`/`bp3.py`, not kept). After YES to the line-table prompt, a run stopped by `until_text "COMPILATION COMPLETE"` sometimes showed an extra row "HIGHEST MEMORY LOCA". It appeared only when the run had earlier been split at a breakpoint, never at a cycle-limit split. Cause: `until_text` is checked every ~5000 cycles counted from the start of each `run` call, so splitting a run shifts the stop point; one stop landed in the middle of the Monitor SCROLL copy loop (row 3 half-copied from row 4). At the next key wait, all variants had identical screens and identical total cycles (167,686,944). Breakpoints don't change program behaviour. Rule: compare state only at key waits (or at a fixed PC).
