"""TASC compile options (manual 5.1), shared by the compiler, the decompiler and the emulator harness."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Options:
    """TASC compile options (manual 5.1).  None / default values mean <RETURN>.

    library, variables: address as a number.  program: number, 'HGR1' or 'HGR2'.
    """

    library: int | None = None
    program: int | str | None = None
    variables: int | None = None
    listing: bool = True
    pause: bool = True
    int_arith: bool = True
    int_const: bool = True
    resume: bool = False

    def memory_default(self) -> bool:
        return self.library is None and self.program is None and self.variables is None

    def options_default(self) -> bool:
        return (self.listing, self.pause, self.int_arith, self.int_const, self.resume) == (
            True, True, True, True, False)

    def tag(self) -> str:
        """Short id: e.g. 'ia1ic1rd0' plus memory parts when not default."""
        t = f"ia{int(self.int_arith)}ic{int(self.int_const)}rd{int(self.resume)}"
        if not self.memory_default():
            t += f"-L{self.library or ''}P{self.program or ''}V{self.variables or ''}"
        return t

    def answers(self) -> list[tuple[str, str]]:
        def addr(v: int | str | None) -> str:
            return "" if v is None else str(v)

        def yn(v: bool) -> str:
            return "YES" if v else "NO"

        ans: list[tuple[str, str]] = [("(DEFAULT", "")]  # object file name
        if self.memory_default():
            ans.append(("MEMORY USAGE", ""))
        else:
            ans += [
                ("MEMORY USAGE", "NO"),
                ("ADDRESS FOR LIBRARY", addr(self.library)),
                ("END OF LIBRARY)?", addr(self.program)),
                ("ADDRESS FOR VARIABLES", addr(self.variables)),
                ("ADDRESSES CORRECT?", "YES"),
            ]
        if self.options_default():
            ans.append(("OPTIONS:", ""))
        else:
            ans += [
                ("OPTIONS:", "NO"),
                ("COMPILATION LISTING", yn(self.listing)),
                ("PAUSE ON ERRORS", yn(self.pause)),
                ("INTEGER ARITHMETIC", yn(self.int_arith)),
                ("INTEGER CONSTANTS", yn(self.int_const)),
                ("RESUME/DEBUG CODE", yn(self.resume)),
            ]
        return ans
