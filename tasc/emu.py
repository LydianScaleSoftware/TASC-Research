"""Emulator harness: drives a private Pandowdy MCP server over stdio.

The server is spawned as a subprocess and spoken to with newline-delimited
JSON-RPC (MCP).  Each Pandowdy instance is independent of the one Claude Code
uses interactively.  Override the server command with TASC_PANDOWDY (a path to
Pandowdy.Mcp.dll).
"""

from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

DEFAULT_DLL = Path.home() / ".local/share/pandowdy-mcp/Pandowdy.Mcp.dll"

MON_HOME = 0xFC58
MON_SCROLL = 0xFC70


class EmuError(RuntimeError):
    pass


class Pandowdy:
    def __init__(self, extra_args: list[str] | None = None) -> None:
        dll = os.environ.get("TASC_PANDOWDY", str(DEFAULT_DLL))
        self._proc = subprocess.Popen(
            ["dotnet", dll, *(extra_args or [])],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            bufsize=1,
        )
        self._id = 0
        self._rpc("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "tasc-harness", "version": "0.1"},
        })
        self._send({"jsonrpc": "2.0", "method": "notifications/initialized"})

    # -- transport -------------------------------------------------------
    def _send(self, msg: dict[str, Any]) -> None:
        assert self._proc.stdin is not None
        self._proc.stdin.write(json.dumps(msg) + "\n")
        self._proc.stdin.flush()

    def _rpc(self, method: str, params: dict[str, Any]) -> Any:
        self._id += 1
        self._send({"jsonrpc": "2.0", "id": self._id, "method": method, "params": params})
        assert self._proc.stdout is not None
        while True:
            line = self._proc.stdout.readline()
            if not line:
                raise EmuError("Pandowdy server exited")
            msg = json.loads(line)
            if msg.get("id") != self._id:
                continue  # notification or log
            if "error" in msg:
                raise EmuError(f"{method}: {msg['error']}")
            return msg["result"]

    def call(self, tool: str, **args: Any) -> Any:
        res = self._rpc("tools/call", {"name": tool, "arguments": args})
        text = "".join(c.get("text", "") for c in res.get("content", []))
        if res.get("isError"):
            raise EmuError(f"{tool}: {text}")
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return text

    def close(self) -> None:
        try:
            if self._proc.stdin:
                self._proc.stdin.close()
            self._proc.wait(timeout=10)
        except Exception:
            self._proc.kill()

    def __enter__(self) -> "Pandowdy":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # -- conveniences ----------------------------------------------------
    def screen_rows(self) -> list[str]:
        """The 24 text rows (40 chars each, right-stripped)."""
        txt = self.call("read_text_screen")
        rows: list[str] = []
        for line in str(txt).splitlines():
            # rows look like ' 7 |SOURCE FILE? BALL      |'
            if "|" in line and line.rstrip().endswith("|") and line.lstrip()[:2].strip().isdigit():
                body = line[line.index("|") + 1 : line.rindex("|")]
                rows.append(body.rstrip())
        if len(rows) != 24:
            raise EmuError(f"could not parse text screen:\n{txt}")
        return rows

    def run(self, **args: Any) -> dict[str, Any]:
        args.setdefault("max_seconds", 0)
        r = self.call("run", **args)
        assert isinstance(r, dict)
        return r

    def type(self, text: str) -> None:
        self.call("type_text", text=text)

    def wait_key(self, max_cycles: int = 50_000_000) -> dict[str, Any]:
        r = self.run(until_key_wait=True, max_cycles=max_cycles)
        if r["stop_reason"] != "waiting_for_key":
            raise EmuError(f"expected key wait, got {r['stop_reason']}")
        return r

    def boot(self, image: Path, drive2: Path | None = None) -> None:
        self.call("mount_disk", path=str(image.resolve()), drive=1)
        if drive2 is not None:
            self.call("mount_disk", path=str(drive2.resolve()), drive=2)
        self.call("power_cycle")


@dataclass
class Transcript:
    """Everything printed to the text screen, rebuilt from scroll/home captures."""

    rows: list[str] = field(default_factory=list)

    def add_scrolled(self, row0: str) -> None:
        self.rows.append(row0)

    def add_screen(self, rows: list[str]) -> None:
        while rows and not rows[-1]:
            rows = rows[:-1]
        self.rows.extend(rows)

    def text(self) -> str:
        return "\n".join(self.rows) + "\n"


def run_capturing(
    emu: Pandowdy,
    transcript: Transcript,
    max_cycles: int,
    stop_on_key_wait: bool = True,
    until_text: str | None = None,
) -> dict[str, Any]:
    """Run, logging every line that scrolls off (and every screen cleared by HOME).

    Returns the first stop that is not one of our capture breakpoints.  The
    caller is responsible for the capture breakpoints being installed
    (install_capture) and for adding the final screen.
    """
    budget = max_cycles
    while True:
        if until_text is not None:
            r = emu.run(until_key_wait=stop_on_key_wait, max_cycles=budget, until_text=until_text)
        else:
            r = emu.run(until_key_wait=stop_on_key_wait, max_cycles=budget)
        budget -= int(r["cycles_executed"])
        pc = int(r["cpu"]["pc"].lstrip("$"), 16)
        if r["stop_reason"] == "breakpoint" and pc == MON_SCROLL:
            transcript.add_scrolled(emu.screen_rows()[0])
            emu.call("step")  # move off the breakpoint
            continue
        if r["stop_reason"] == "breakpoint" and pc == MON_HOME:
            transcript.add_screen(emu.screen_rows())
            emu.call("step")
            continue
        if budget <= 0 and r["stop_reason"] == "cycle_limit":
            return r
        return r


def install_capture(emu: Pandowdy) -> None:
    emu.call("add_breakpoint", address=f"${MON_SCROLL:04X}")
    emu.call("add_breakpoint", address=f"${MON_HOME:04X}")
