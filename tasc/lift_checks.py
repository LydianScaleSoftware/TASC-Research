"""Real-TASC checks for rules lifted from PASS1's code (Phase 3, session 5).

    python -m tasc.lift_checks      compile the cases with real TASC, compare with the predictor
"""

from __future__ import annotations

from tasc.applesoft import tokenize_program
from tasc.batch import Job, run_family
from tasc.compiler.assemble import compile_program
from tasc.harness import Options

RD = Options(resume=True)
CASES: list[tuple[str, str, Options]] = [
    # RUN (PASS1 1290-1310)
    ("run", "10 RUN\n", Options()),
    ("run_n", "10 PRINT:RUN 10\n", Options()),
    ("run_dead", "10 RUN:PRINT:X=1\n20 PRINT X\n", Options()),
    ("run_rd", "10 RUN\n", RD),
    ("run_n_rd", "10 RUN 10\n", RD),
    ("clear_run_rd", "10 CLEAR:GOTO 10\n", RD),
    # REM! CLEAR COMMON / CHAIN through the debug emitter (PASS1 1585-1615)
    ("clrcom_rd", "10 REM! CLEAR COMMON\n20 PRINT\n", RD),
    ("clrchain_rd", "10 REM! CLEAR CHAIN\n20 PRINT\n", RD),
    ("clrcom_then_rd", "10 IF X THEN REM! CLEAR COMMON\n20 PRINT\n", RD),
    ("clrcom", "10 REM! CLEAR COMMON\n20 PRINT\n", Options()),
    # comparisons with a simple left and a complex right (PASS1 5920-5980, 6085-6120)
    ("cmp_lt", "10 IF A<B(1) THEN 10\n", Options()),
    ("cmp_ge", "10 X=A>=B(1)+1\n", Options()),
    ("scmp_eq", "10 IF A$=MID$(B$,2) THEN 10\n", Options()),
    ("scmp_lt", "10 X=A$<LEFT$(B$,1)\n", Options()),
    ("scmp_ge", "10 X=A$>=B$(1)\n", Options()),
    ("scmp_gt2", "10 X=\"A\">B$+C$\n", Options()),
    # PASS2 845-1350: string routines are emitted without an op-mask check; numeric only with ops
    ("fre_str", "10 X=FRE(A$)\n", Options()),
    ("pos_str", "10 X=POS(B$)+1:PRINT X\n", Options()),
    ("fre_num", "10 X=FRE(A)\n", Options()),
    ("fre_strarr", "10 X=FRE(A$(2))\n", Options()),
]


def main() -> None:
    jobs = [Job(i, s, o) for i, s, o in CASES]
    res = run_family("p3_lift", jobs, workers=8)
    for i, s, o in CASES:
        r = res[i]
        if not r.ok:
            print(f"{i:16} TASC failed: {r.error[:60]}")
            continue
        real = r.obj("p3_lift")
        pred = compile_program(tokenize_program(s), o)
        same = pred.data == real and pred.load == r.obj_addr
        print(f"{i:16} {'match' if same else 'MISMATCH'}  {s.strip()!r}")


if __name__ == "__main__":
    main()
