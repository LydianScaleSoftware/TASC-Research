"""Predict every recorded TASC compile with the Python predictor and compare bytes.

    python -m tasc.predict_check [family-prefix] [-v]
"""

from __future__ import annotations

import collections
import json
import sys
import traceback
from dataclasses import fields

from tasc.batch import EXPERIMENTS, load_result
from tasc.compiler.assemble import compile_program
from tasc.compiler.codegen import CompileError
from tasc.harness import Options
from tasc.objfile import parse


def options_of(d: dict[str, object]) -> Options:
    names = {f.name for f in fields(Options)}
    return Options(**{k: v for k, v in d.items() if k in names})  # type: ignore[arg-type]


def check(prefix: str = "p1_", verbose: bool = False) -> None:
    stats: collections.Counter[str] = collections.Counter()
    errors: collections.Counter[str] = collections.Counter()
    mism: list[str] = []
    for d in sorted(EXPERIMENTS.glob(f"{prefix}*/*")):
        if not (d / "result.json").exists():
            continue
        if not (d / "source.bas").exists():
            from tasc.applesoft import tokenize_program
            if not (d / "source.txt").exists():
                continue
            (d / "source.bas").write_bytes(tokenize_program((d / "source.txt").read_text()))
        r = load_result(d.parent.name, d.name)
        if not r.ok:
            if "FATAL ERROR" in r.error:
                # TASC rejected the program: the predictor must reject it too
                kind = r.error.split("LINE NUMBER")[-1].split("\n")[1:3]
                try:
                    compile_program((d / "source.bas").read_bytes(), options_of(r.options))
                    stats["tasc_rejects_pred_accepts"] += 1
                    mism.append(f"{d.parent.name}/{d.name}: TASC {' '.join(k.strip() for k in kind)}, predictor accepts")
                except Exception:  # noqa: BLE001
                    stats["both_reject"] += 1
            continue
        if not (d / "OBJ.bin").exists():
            continue  # being written by a running batch
        stats["total"] += 1
        opts = options_of(r.options)
        try:
            res = compile_program((d / "source.bas").read_bytes(), opts)
        except CompileError as exc:
            stats["unsupported"] += 1
            errors[str(exc).split(":")[0] + (":" + str(exc).split(":")[1] if "GUESS" in str(exc) else "")] += 1
            continue
        except Exception as exc:  # noqa: BLE001
            stats["crash"] += 1
            errors["CRASH " + type(exc).__name__ + ": " + str(exc)[:60]] += 1
            if verbose:
                traceback.print_exc()
            continue
        real = r.obj(d.parent.name)
        if res.load == r.obj_addr and res.data == real:
            stats["match"] += 1
            continue
        stats["mismatch"] += 1
        off = next((i for i in range(min(len(real), len(res.data))) if real[i] != res.data[i]), min(len(real), len(res.data)))
        mism.append(f"{d.parent.name}/{d.name}: {r.source.strip()[:70]!r} load {res.load:04X}/{r.obj_addr:04X} "
                    f"len {len(res.data)}/{len(real)} first diff +{off}")
        if verbose:
            try:
                a = parse(real, r.obj_addr, r.source).symbolic()
                b = parse(res.data, res.load, r.source).symbolic()
                print(mism[-1])
                print("   TASC:", " | ".join(a))
                print("   PRED:", " | ".join(b))
            except Exception as exc:  # noqa: BLE001
                print("   (parse failed)", exc)
    print(json.dumps(dict(stats)))
    for k, n in errors.most_common():
        print(f"  {n:4d}  {k}")
    for m in mism[: 40 if not verbose else 10**6]:
        print("  MISMATCH", m)


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    check(args[0] if args else "p1_", "-v" in sys.argv)
