# TASC Research

Recovering the source code of **Microsoft TASC 2.01**, The Applesoft Compiler (1981),
for the Apple II, and proving that the recovered source is the real thing.

TASC compiled Applesoft BASIC into 6502 machine code. Microsoft shipped it as compiled
code only: three compiler passes (PASS0, PASS1, PASS2) that TASC had compiled from its
own Applesoft source, plus RUNTIME, a 4,013-byte hand-written machine language library.
No source was ever published. This project reconstructs it.

## Results

- **The compiler's Applesoft source, recovered.** PASS0, PASS1 and PASS2 as Applesoft
  programs (306, 1,345 and 504 lines) with meaningful variable names, structured line
  numbering, and line-by-line documentation. When the **original TASC**, running in an
  emulated Apple II, compiles these sources, it produces object files **identical byte
  for byte** to the ones Microsoft shipped.
- **The RUNTIME library as 6502 assembly source**, labeled and commented, in the style
  of Apple's DOS Tool Kit assembler (EDASM). Assembled by the **real EDASM** of 1979,
  it produces RUNTIME byte for byte.
- **MAKE RUNTIME**, an Applesoft program that rebuilds the RUNTIME file from DATA
  statements; run on the emulated Apple II, it saves a file identical to the original.
- **A bootable DOS 3.3 source disk** holding all of the above, from which the original
  TASC compiles its own passes.
- **AASCAD** (Another AppleSoft Compiler And Decompiler): a reimplementation of TASC in
  one Python script. It compiles Applesoft exactly as TASC does, byte for byte, and
  decompiles TASC object files back into Applesoft that recompiles to the same bytes.
- **A documentation site** (`src/html/`): annotated listings and an overview of each
  program, the RUNTIME assembler listing, the transcribed TASC manual, and downloads.

## How it was done

This project relied heavily on **Claude Code with Claude Opus 5.5**, which did most
of the analysis, coding, annotation and testing. It was a guided effort, not an
unattended one: I set the goals, the rules and the
standards, made the judgment calls, and reviewed the results, working through a custom
ecosystem of tools built so the agent could run its own experiments and check its own
work against the real software:

- **An Apple II emulator the agent could drive.** The (as-of-yet unreleased) Pandowdy emulator, with a custom
  MCP server, let Claude boot disks, type, set breakpoints and watchpoints, and read
  memory and the screen. A Python harness ran up to twelve emulators in parallel, each
  booting the original TASC disk to compile a test program, so any question about
  TASC's behavior could be settled by asking TASC itself.
- **An agent-writable RAG server.** RAGamuffin, a document library the agent could both
  search and add to, held the reference manuals (Applesoft, the Apple II, DOS, the TASC
  manual), and the project's own findings, written up phase by phase, so that knowledge
  carried across many working sessions.
- **CiderPress II** for reading and writing files on DOS 3.3 disk images.

The work went in phases, each with an exit test agreed in advance:

1. **Observe.** Confirm TASC is deterministic, and learn its object file format
   (a header, the code, a constant pool, per-variable routines) from controlled
   compiles.
2. **Predict.** Build a compiler in Python that matches TASC's output. Its rules were
   learned from TASC's output and then checked against the logic read from PASS1 and
   PASS2 themselves. Exit test: it matches real TASC **byte for byte on all 1,954
   recorded compiles**, and it rejects all 237 programs that TASC rejects. The test
   programs included targeted cases for each statement and corner case, and
   generated programs whose output nobody had predicted beforehand.
3. **Decompile.** Turn object code back into Applesoft. Every result is verified by
   recompiling: the decompiler round-trips all 1,954 compiles. Applied to PASS0-2,
   it recovered the compiler's own source.
4. **Reconstruct and document.** Choose names consistent with TASC's hashed variable
   ordering (the names determine the memory layout, so they are constrained), number
   the lines, write the documentation, and disassemble and annotate RUNTIME.
5. **Prove.** After every change to the recovered sources, the original TASC compiles
   them again in the emulator, and the result must match the shipped PASS files
   exactly. The same holds for RUNTIME through the original EDASM and MAKE RUNTIME.

Two rules held throughout: originals are kept read-only and all work is done on copies,
and nothing counts as proven unless the comparison against the original actually ran.

The result is strong evidence that the reconstruction is faithful. The source is
not Microsoft's original text, since names, line numbers and comments were lost in
compilation, but it is a source from which the original compiler, unchanged, produces
the shipped program exactly.

## Repository

| Path | Contents |
|---|---|
| `src/` | The recovered sources: `PASSn.bas` (tokenized) and `.txt` (listing), `.DOC.TXT` and `.VARS.TXT` (documentation), `RUNTIME.S` and `runtime/` (assembly source), `MAKE_RUNTIME.txt` |
| `src/html/` | The documentation site; self-contained, so it can be archived and served as is |
| `dist/aascad.py` | AASCAD, as one script |
| `tasc/` | The project's Python code: emulator harness, compiler, decompiler, source and documentation generators, a small EDASM-compatible assembler |
| `tests/` | The test suite (`pytest`; `pytest -m emu` for the emulator tests) |
| `docs/` | Analysis notes and the annotations that drive the generated documentation |
| `experiments/` | Recorded compiles by the real TASC (sources, objects, transcripts) |
| `images/` | Disk images: the originals, working copies, and the source disk |
| `NOTES.md` | The project's working notes and decisions |

## AASCAD

```bash
python3 dist/aascad.py compile BALL.txt -o BALL.OBJ
python3 dist/aascad.py decompile BALL.OBJ -o BALL.txt --bas BALL.bas
python3 dist/aascad.py compile "TASC.dsk::BALL" -o "WORK.dsk::BALL.OBJ"
```

It needs Python 3.9 or later and nothing else; CiderPress II's `cp2` is needed only for
files inside disk images. See `src/html/AASCAD.html` or `python3 dist/aascad.py --help`.

## Copyright

TASC, its compiler passes, the RUNTIME library and the TASC manual are the copyrighted
work of Microsoft (© 1981 Microsoft). Applesoft is the work of Microsoft and Apple; the
DOS Tool Kit is Apple's. The recovered sources, disk images and documentation here are
for educational and historical purposes only: to study and preserve how an early Apple II
compiler worked. They are not offered for sale or for any commercial use. Any takedown
or removal request from a copyright holder will be respected and acted on promptly.

AASCAD and the project's own code are © 2026 [Lydian Scale Software](https://lydianscale.com).
The parts of AASCAD that reproduce TASC's behavior (the code it generates, the object
file layout, the RUNTIME entry points it calls) are Microsoft's work, and its number
conversion follows the Applesoft ROM. AASCAD is not a Microsoft product.
