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
    # PASS1 6555: the store-load peephole also skips an AND/OR memory test (CK=20)
    ("peep_and", "10 X=5:Y=X AND X\n", Options()),
    ("peep_or_int", "10 X%=A:Y=X% OR X%\n", Options()),
    ("peep_if_and", "10 X=A:IF X AND X THEN 10\n", Options()),
    ("peep_and_other", "10 X=A:Y=X AND B\n", Options()),
    ("peep_read_and", "10 READ X:Y=X AND X\n20 DATA 1\n", Options()),
]


# PASS1 2485: unsupported keywords (and RESUME with the RESUME/Debug option off) are skipped
# with a warning; PASS1 330: REM and DATA are exempt from the dead-code skip
UNSUP = ["DEL", "SHLOAD", "TRACE", "NOTRACE", "LOMEM:", "RECALL", "STORE", "&", "LOAD", "SAVE", "CONT", "LIST"]
UNSUP_CASES: list[tuple[str, str, Options]] = [
    ("del", "10 DEL 10,20\n20 PRINT\n", Options()),
    ("shload", "10 SHLOAD\n20 X=1\n", Options()),
    ("trace", "10 TRACE\n", Options()),
    ("notrace", "10 NOTRACE:PRINT\n", Options()),
    ("lomem", "10 LOMEM: 16384:X=2\n", Options()),
    ("recall", "10 RECALL A:PRINT A\n", Options()),
    ("store", "10 STORE ZZ:PRINT B\n", Options()),
    ("amper", '10 & "A:B",Q:PRINT Q\n', Options()),
    ("load", '10 LOAD "X":PRINT\n', Options()),
    ("save", "10 SAVE\n", Options()),
    ("cont", "10 X=1:CONT:PRINT X\n", Options()),
    ("list", "10 LIST 10-20:PRINT \"A:B\";C$\n", Options()),
    ("trace_then", "10 IF X THEN TRACE:PRINT\n20 END\n", Options()),
    ("trace_then_rd", "10 IF X THEN TRACE:PRINT\n20 END\n", Options(resume=True)),
    ("trace_rd", "10 TRACE:PRINT:LIST:X=1\n", Options(resume=True)),
    ("trace_dead", "10 GOTO 10:TRACE:X=1\n", Options()),
    ("resume_off", "10 RESUME:PRINT\n", Options()),
    ("resume_then_rd", "10 IF X THEN RESUME:PRINT\n", Options(resume=True)),
    ("rem_dead", "10 GOTO 20:REM! CLEAR COMMON\n20 PRINT\n", Options()),
    ("rem_dead_rd", "10 GOTO 20:REM! CLEAR CHAIN\n20 PRINT\n", Options(resume=True)),
    ("unsup_all", "10 " + ":".join(UNSUP[:6]) + "\n20 " + ":".join(UNSUP[6:]) + "\n30 PRINT 1\n", Options()),
    ("unsup_vars", "10 X=1:STORE Q,R:Y=X\n20 PRINT R\n", Options()),
]


# PASS1 1335-1405 / 2435 -> 310: an empty statement right after THEN takes the normal
# statement-end path (general IF form; after-THEN flag cleared)
THEN_CASES: list[tuple[str, str, Options]] = [
    ("then_colon_goto", "10 IF X THEN :GOTO 10\n", Options()),
    ("then_colon_return", "10 IF X THEN :RETURN\n", Options()),
    ("then_colon_print_rd", "10 IF X THEN :PRINT\n", Options(resume=True)),
    ("then_colon_end", "10 IF X THEN :\n20 PRINT\n", Options()),
    ("then_colon2_print_rd", "10 IF X THEN ::PRINT:PRINT\n", Options(resume=True)),
    ("then_return_colon", "10 IF X THEN RETURN:\n20 PRINT\n", Options()),
]


def check(family: str, cases: list[tuple[str, str, Options]]) -> None:
    jobs = [Job(i, s, o) for i, s, o in cases]
    res = run_family(family, jobs, workers=8)
    for i, s, o in cases:
        r = res[i]
        if not r.ok:
            print(f"{i:16} TASC failed: {r.error[:60]}")
            continue
        real = r.obj(family)
        pred = compile_program(tokenize_program(s), o)
        same = pred.data == real and pred.load == r.obj_addr
        print(f"{i:16} {'match' if same else 'MISMATCH'}  {s.strip()!r}")


def main() -> None:
    import sys
    if "--unsup" in sys.argv:
        check("p3_unsup", UNSUP_CASES)
    elif "--then" in sys.argv:
        check("p3_then", THEN_CASES)
    else:
        check("p3_lift", CASES)


if __name__ == "__main__":
    main()
