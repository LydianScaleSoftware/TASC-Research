"""Assemble the RUNTIME source with Apple's real EDASM (DOS Toolkit) in Pandowdy.

    python -m tasc.edasmrun          boot the DOS Toolkit (drive 1) with the source disk
                                     (drive 2), assemble RUNTIME.S1 and its chain, and
                                     compare EDASM's object file with RUNTIME

Results go to experiments/p5_edasm/: the transcript of the assembly (listing and errors),
both disks after the run, the object file and summary.json.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from tasc import disk
from tasc.emu import Pandowdy, Transcript, install_capture, run_capturing
from tasc.harness import sha256

ROOT = Path(__file__).resolve().parents[1]
TOOLKIT = ROOT / "images" / "work" / "dostoolkit.dsk"
SOURCE = ROOT / "images" / "source" / "TASC 2.01 SOURCE.dsk"
RUNTIME = ROOT / "images" / "work" / "tasc201.dsk"
OUT = ROOT / "experiments" / "p5_edasm"


def command(emu: Pandowdy, text: str) -> None:
    """One editor command: EDASM drops keys typed ahead, so wait for its prompt each time."""
    emu.type(text + "\n")
    emu.wait_key(100_000_000)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    tk, src = OUT / "toolkit.dsk", OUT / "source.dsk"
    shutil.copyfile(TOOLKIT, tk)
    shutil.copyfile(SOURCE, src)
    t = Transcript()
    with Pandowdy() as emu:
        emu.boot(tk, drive2=src)
        emu.wait_key(40_000_000)
        command(emu, "RUN EDASM")
        command(emu, "")  # keep the assembler ID stamp
        command(emu, "DRIVE 2")
        install_capture(emu)
        emu.type("ASM RUNTIME.S1\n")
        cycles = 0
        for _ in range(40):  # it stops for a key between its phases
            r = run_capturing(emu, t, 2_000_000_000)
            cycles += int(r.get("cycles_executed", 0))
            if r["stop_reason"] == "waiting_for_key" and "PRESS ANY KEY" in "\n".join(emu.screen_rows()):
                emu.type(" ")
                continue
            break
        t.add_screen(emu.screen_rows())
        emu.call("save_disk", path=str((OUT / "toolkit_after.dsk").resolve()), drive=1)
        emu.call("save_disk", path=str((OUT / "source_after.dsk").resolve()), drive=2)
    (OUT / "transcript.txt").write_text(t.text())
    files = disk.extract_all(OUT / "source_after.dsk")
    obj = next((f for n, f in files.items() if n.startswith("RUNTIME.S1.OBJ")), None)
    orig = disk.extract(RUNTIME, "RUNTIME")
    summary: dict[str, object] = {"cycles": cycles, "object": obj.name if obj else None}
    if obj:
        (OUT / "RUNTIME.OBJ").write_bytes(obj.data)
        diff = next((k for k in range(min(len(obj.data), len(orig.data))) if obj.data[k] != orig.data[k]), None)
        summary.update(identical=obj.data == orig.data, len=len(obj.data), orig_len=len(orig.data), load=obj.aux,
                       first_diff=None if diff is None else f"${0x0803 + diff:04X}", sha256=sha256(obj.data))
    (OUT / "summary.json").write_text(json.dumps(summary, indent=1) + "\n")
    print(json.dumps(summary))


if __name__ == "__main__":
    main()
