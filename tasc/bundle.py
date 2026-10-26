"""Build TASCAD as one self-contained script: dist/tascad.py.

    python -m tasc.bundle

The script carries the source of every module TASCAD needs (the compiler, the
decompiler and their helpers) verbatim, each under a banner with its module name, and a
small import hook that loads them from the script itself. The modules keep their own
namespaces (several define names such as Sym or Line differently), so the code in the
script is exactly the code the project's tests run. Standard library only.
"""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "dist" / "tascad.py"

# (module, is package), in an order that imports cleanly
MODULES = [
    ("tasc", True), ("tasc.options", False), ("tasc.applesoft", False), ("tasc.m6502", False),
    ("tasc.symbols", False), ("tasc.objfile", False),
    ("tasc.compiler", True), ("tasc.compiler.fp", False), ("tasc.compiler.fin", False),
    ("tasc.compiler.parse", False), ("tasc.compiler.codegen", False), ("tasc.compiler.assemble", False),
    ("tasc.decomp", True), ("tasc.decomp.walk", False), ("tasc.decomp.lift", False),
    ("tasc.decomp.names", False), ("tasc.decomp.render", False), ("tasc.decomp.decompile", False),
    ("tasc.tascad", False),
]

LOADER = '''
# ---------------------------------------------------------------- loader
import importlib.abc
import importlib.util
import linecache
import sys


class _Bundle(importlib.abc.MetaPathFinder, importlib.abc.Loader):
    """Imports the modules above from this file."""

    def find_spec(self, name, path=None, target=None):  # type: ignore[no-untyped-def]
        if name in _MODULES:
            return importlib.util.spec_from_loader(name, self, is_package=_MODULES[name][1])
        return None

    def create_module(self, spec):  # type: ignore[no-untyped-def]
        return None

    def exec_module(self, module):  # type: ignore[no-untyped-def]
        source = _MODULES[module.__name__][0]
        filename = f"<tascad:{module.__name__}>"
        linecache.cache[filename] = (len(source), None, source.splitlines(True), filename)
        exec(compile(source, filename, "exec"), module.__dict__)


sys.meta_path.insert(0, _Bundle())

if __name__ == "__main__":
    from tasc.tascad import main
    raise SystemExit(main())
'''


def module_path(name: str, package: bool) -> Path:
    parts = name.split(".")
    return ROOT.joinpath(*parts, "__init__.py") if package else ROOT.joinpath(*parts[:-1], parts[-1] + ".py")


def build() -> Path:
    import tasc.tascad as front
    doc = (front.__doc__ or "").strip()
    out = ["#!/usr/bin/env python3", '"""' + doc + "\n\nThis file is the whole program: the modules below are loaded from it by the",
           "small import hook at the end. Run it with: python3 tascad.py compile|decompile ...", '"""', "",
           "_MODULES = {}"]
    for name, package in MODULES:
        src = module_path(name, package).read_text()
        if "'''" in src or src.endswith("\\"):
            raise ValueError(f"{name}: cannot be embedded as a raw string")
        ast.parse(src)  # it must at least be valid Python
        out += ["", "", f"# {'=' * 76}", f"# module {name}" + (" (package)" if package else ""),
                f"# {'=' * 76}", f"_MODULES[{name!r}] = (r'''" + src + f"''', {package})"]
    out.append(LOADER)
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text("\n".join(out))
    OUT.chmod(0o755)
    return OUT


def main() -> None:
    path = build()
    text = path.read_text()
    print(f"{path.relative_to(ROOT)}: {text.count(chr(10))} lines, {len(text)} characters, {len(MODULES)} modules")


if __name__ == "__main__":
    main()
