"""Phase 1 one-statement families (default options unless stated)."""

from __future__ import annotations

STMT0 = ["HOME", "TEXT", "GR", "HGR", "HGR2", "NORMAL", "INVERSE", "FLASH", "END", "STOP",
         "RETURN", "POP", "RESTORE", "CLEAR", "NEW", "PRINT"]
STMT1 = ["VTAB X", "HTAB X", "COLOR=X", "HCOLOR=X", "SPEED=X", "ROT=X", "SCALE=X", "CALL X",
         "IN#X", "PR#X", "HIMEM:X", "PLOT X,Y", "HLIN X,Y AT Z", "VLIN X,Y AT Z", "POKE X,Y",
         "WAIT X,Y", "WAIT X,Y,Z", "HPLOT X,Y", "HPLOT TO X,Y", "HPLOT X,Y TO Z,W", "DRAW X", "DRAW X AT Y,Z",
         "XDRAW X", "XDRAW X AT Y,Z",
         "VTAB X%", "PLOT X%,Y%", "POKE X%,Y%", "COLOR=X%"]
OPS = ["+", "-", "*", "/", "^", "AND", "OR", "=", "<", ">", "<=", ">=", "<>"]
TYPEPAIRS = {"rr": ("A", "B"), "ii": ("A%", "B%"), "ir": ("A%", "B"), "ri": ("A", "B%")}
OPNAME = {"+": "add", "-": "sub", "*": "mul", "/": "div", "^": "pow", "AND": "and", "OR": "or", "=": "eq",
          "<": "lt", ">": "gt", "<=": "le", ">=": "ge", "<>": "ne"}


def ident(s: str) -> str:
    return "".join(c if c.isalnum() else "_" for c in s.replace("%", "i").replace("$", "s")).strip("_").lower()


def stmt_family() -> dict[str, str]:
    return {ident(s): f"10 {s}" for s in STMT0 + STMT1}


def binop_family(target: str = "X") -> dict[str, str]:
    out: dict[str, str] = {}
    for op in OPS:
        for tp, (a, b) in TYPEPAIRS.items():
            out[f"{OPNAME[op]}_{tp}_to_{ident(target)}"] = f"10 {target}={a}{op}{b}"
    return out


PEEPHOLE = {
    "store_load_same_stmt": "10 X=1:Y=X",
    "store_load_next_line": "10 X=1\n20 Y=X",
    "store_load_target_line": "10 X=1\n20 Y=X\n30 GOTO 20",
    "store_other_load": "10 X=1:Z=2:Y=X",
    "store_load_int": "10 X%=1:Y%=X%",
    "store_load_str": '10 A$="A":B$=A$',
    "store_print": "10 X=1:PRINT X",
    "store_load_expr": "10 X=1:Y=X*2",
    "load_load": "10 Y=X:Z=X",
    "print_then_load": "10 PRINT X:Y=X",
    "if_store": "10 X=1:IF X THEN Y=1",
    "store_then_add": "10 X=Y+1:Z=X+1",
}

UNARY_FN = {
    "neg_r": "10 X=-A", "neg_i_to_i": "10 X%=-A%", "neg_i_to_r": "10 X=-A%", "not_r": "10 X=NOT A", "not_i": "10 X=NOT A%",
    "plus_r": "10 X=+A",
    **{f"fn_{f.lower()}_r": f"10 X={f}(A)" for f in ["SGN", "INT", "ABS", "USR", "FRE", "PDL", "POS", "SQR", "RND", "LOG", "EXP",
                                                    "COS", "SIN", "TAN", "ATN", "PEEK"]},
    "fn_sgn_i": "10 X=SGN(A%)", "fn_int_i": "10 X=INT(A%)", "fn_abs_i": "10 X=ABS(A%)", "fn_peek_i": "10 X=PEEK(A%)",
    "fn_int_to_i": "10 X%=INT(A)", "fn_abs_i_to_i": "10 X%=ABS(A%)",
    "fn_scrn": "10 X=SCRN(A,B)", "fn_len": "10 X=LEN(A$)", "fn_val": "10 X=VAL(A$)", "fn_asc": "10 X=ASC(A$)",
    "fn_str": "10 X$=STR$(A)", "fn_chr": "10 X$=CHR$(A)", "fn_left": "10 X$=LEFT$(A$,B)", "fn_right": "10 X$=RIGHT$(A$,B)",
    "fn_mid2": "10 X$=MID$(A$,B)", "fn_mid3": "10 X$=MID$(A$,B,C)", "fn_chr_i": "10 X$=CHR$(A%)", "fn_len_to_i": "10 X%=LEN(A$)",
    "concat": "10 X$=A$+B$", "concat3": "10 X$=A$+B$+C$", "streq": "10 X=A$=B$", "strlt": "10 X=A$<B$", "strne": "10 X=A$<>B$",
}

PRINTS = {
    "pr_x": "10 PRINT X", "pr_xi": "10 PRINT X%", "pr_s": "10 PRINT A$", "pr_x_semi": "10 PRINT X;", "pr_x_comma": "10 PRINT X,",
    "pr_x_y": "10 PRINT X;Y", "pr_x_c_y": "10 PRINT X,Y", "pr_xy_juxt": "10 PRINT X Y", "pr_s_x": '10 PRINT "A";X',
    "pr_s_juxt_x": '10 PRINT "A"X', "pr_tab": "10 PRINT TAB(X)", "pr_spc": "10 PRINT SPC(X)", "pr_tab_semi": "10 PRINT TAB(X);",
    "pr_expr": "10 PRINT X+Y", "pr_sexpr": "10 PRINT A$+B$", "pr_semi_only": "10 PRINT ;", "pr_comma_only": "10 PRINT ,",
    "pr_lit_semi": '10 PRINT "A";', "pr_empty_lit": '10 PRINT ""', "pr_two_lits": '10 PRINT "A";"B"',
}

ARRAYS = {
    "arr_r_load": "10 X=A(1)", "arr_r_store": "10 A(1)=X", "arr_i_load": "10 X%=A%(1)", "arr_i_store": "10 A%(1)=X%",
    "arr_s_load": "10 X$=A$(1)", "arr_s_store": "10 A$(1)=X$", "arr_var_idx": "10 X=A(I)", "arr_ivar_idx": "10 X=A(I%)",
    "arr_expr_idx": "10 X=A(I+1)", "arr_2d": "10 X=A(I,J)", "arr_dim": "10 DIM A(5)", "arr_dim_use": "10 DIM A(5):X=A(I)",
    "arr_dim2": "10 DIM A(5,3):X=A(I,J)", "arr_dim_i": "10 DIM A%(20):X%=A%(I%)", "arr_dim_s": "10 DIM A$(7):X$=A$(I)",
    "arr_dim_multi": "10 DIM A(5),B%(6)", "arr_ops": "10 X=A(1)+A(2)", "arr_store_load": "10 A(1)=X:Y=A(1)",
}

CONSTS = {
    "k_int_to_r": "10 X=5", "k_int_to_i": "10 X%=5", "k_real_to_i": "10 X%=1.5", "k_big": "10 X=40000", "k_big_i": "10 X%=40000",
    "k_neg": "10 X=-5", "k_zero_r": "10 X=0", "k_zero_i": "10 X%=0", "k_e": "10 X=1E10", "k_small": "10 X=.001",
    "k_add_r": "10 X=A+5", "k_add_i": "10 X%=A%+5", "k_add_ir": "10 X=A%+5", "k_same_twice": "10 X=5:Y%=5",
    "k_vtab": "10 VTAB 5", "k_poke": "10 POKE 768,0", "k_mul_both": "10 X=A%*5:Y=B*5", "k_32767": "10 X%=32767",
    "k_m32768": "10 X%=-32768", "k_expr": "10 X=2+3", "k_cmp_i": "10 X=A%>5", "k_cmp_r": "10 X=A>5",
}

FLOW = {
    "goto_fwd": "10 GOTO 30\n20 X=1\n30 END", "gosub": "10 GOSUB 30\n20 END\n30 RETURN",
    "if_then_line": "10 IF X THEN 30\n20 Y=1\n30 END", "if_then_stmt": "10 IF X THEN Y=1", "if_then_goto": "10 IF X THEN GOTO 30\n20 Y=1\n30 END",
    "if_cmp_r": "10 IF X>Y THEN Z=1", "if_cmp_i": "10 IF X%>Y% THEN Z=1", "if_str": '10 IF A$="" THEN Z=1', "if_and": "10 IF X AND Y THEN Z=1",
    "if_two_stmts": "10 IF X THEN Y=1:Z=2", "if_nested": "10 IF X THEN IF Y THEN Z=1",
    "on_goto": "10 ON X GOTO 20,30\n20 END\n30 END", "on_gosub": "10 ON X GOSUB 20,30\n20 RETURN\n30 RETURN",
    "for_r": "10 FOR I=1 TO 10:NEXT I", "for_i": "10 FOR I%=1 TO 10:NEXT I%", "for_step": "10 FOR I=1 TO 10 STEP 2:NEXT I",
    "for_noname_next": "10 FOR I=1 TO 10:NEXT", "for_vars": "10 FOR I=A TO B STEP C:NEXT I", "for_nested_next": "10 FOR I=1 TO 2:FOR J=1 TO 2:NEXT J,I",
    "for_lines": "10 FOR I=1 TO 10\n20 X=I\n30 NEXT I", "onerr": "10 ONERR GOTO 30\n20 END\n30 END", "resume": "10 ONERR GOTO 30\n20 END\n30 RESUME",
    "pop_ret": "10 GOSUB 20\n20 POP:RETURN",
}

IO = {
    "input_x": "10 INPUT X", "input_xi": "10 INPUT X%", "input_s": "10 INPUT A$", "input_prompt": '10 INPUT "Q";X', "input_two": "10 INPUT X,Y",
    "get_s": "10 GET A$", "get_x": "10 GET X", "read_x": "10 READ X\n20 DATA 5", "read_s": "10 READ A$\n20 DATA HI", "read_two": "10 READ X,A$\n20 DATA 1,HI",
    "data_only": "10 DATA 1,2,3", "data_mixed": '10 DATA 1,"A B",C,-2.5,', "restore_read": "10 READ X:RESTORE\n20 DATA 1",
    "def_fn": "10 DEF FN F(Z)=Z*2\n20 X=FN F(3)", "def_fn_var": "10 DEF FN F(Z)=Z+Y\n20 X=FN F(A)",
    "rem": "10 REM HELLO\n20 END", "rem_bang_int": "10 REM !INTEGER I\n20 I=1", "let": "10 LET X=1", "colon_empty": "10 X=1::Y=2",
}


RESUME_DEBUG = {
    "end": "10 END", "home": "10 HOME", "assign_k": "10 X=1", "assign_v": "10 X=Y", "assign_expr": "10 X=Y+Z",
    "assign_div": "10 X=Y/Z", "print_x": "10 PRINT X", "goto": "10 GOTO 10", "two_stmts": "10 X=1:Y=2",
    "two_lines": "10 X=1\n20 Y=2", "if": "10 IF X THEN Y=1", "for": "10 FOR I=1 TO 2:NEXT I", "gosub": "10 GOSUB 20\n20 RETURN",
    "rem": "10 REM X\n20 END", "resume": "10 ONERR GOTO 20\n20 RESUME", "input": "10 INPUT X", "vtab": "10 VTAB X",
    "str_assign": '10 A$="X"', "int_add": "10 X%=Y%+Z%", "arr": "10 X=A(1)", "return": "10 RETURN", "data": "10 DATA 1",
}

REMBANG = {
    "int_one": "10 REM! INTEGER I\n20 I=1", "int_for": "10 REM! INTEGER I\n20 FOR I=1 TO 10:NEXT I",
    "int_for_vars": "10 REM! INTEGER I\n20 FOR I=A% TO B% STEP C%:NEXT I", "int_star": "10 REM! INTEGER *\n20 I=1:J=I+1",
    "int_list": "10 REM! INTEGER I,J , K\n20 I=J+K", "int_arr": "10 REM! INTEGER A(5)\n20 A(1)=2",
    "int_hash": "10 REM! INTEGER K\n20 A=1:K=1", "int_two_rems": "10 REM! INTEGER I\n20 REM! INTEGER J\n30 I=J",
    "rem_nospace": "10 REM!INTEGER I\n20 I=1", "rem_inactive": "10 REM INTEGER I\n20 I=1",
    "defcommon_num": "10 REM! DEFCOMMON A,B%\n20 A=1:B%=2", "defcommon_str": "10 REM! DEFCOMMON A$,B\n20 A$=\"X\":B=1",
    "defcommon_arr": "10 REM! DEFCOMMON A(3),B$(2)\n20 A(1)=1", "usecommon": "10 REM! USECOMMON A,B%\n20 A=1:B%=2",
    "common_order": "10 REM! DEFCOMMON Z,A\n20 A=1:Z=1", "common_plus_local": "10 REM! DEFCOMMON A\n20 A=1:B=2",
    "int_then_common": "10 REM! INTEGER I\n20 REM! DEFCOMMON I,J\n30 I=1", "clear_common": "10 REM! CLEAR COMMON",
    "clear_chain": "10 REM! CLEAR CHAIN\n20 PRINT CHR$(4);\"BRUN X\"", "common_two_rems": "10 REM! DEFCOMMON A\n20 REM! DEFCOMMON B\n30 B=A",
}

OPEN_Q = {
    "fn_param_hash0": "10 DEF FN F(Z)=Z\n20 A=FN F(1)", "fn_param_after": "10 DEF FN F(A)=A\n20 Z=FN F(1)",
    "fn_two": "10 DEF FN F(X)=X\n20 DEF FN G(Y)=Y\n30 A=FN F(1)+FN G(2)", "fn_param_used_outside": "10 DEF FN F(Z)=Z\n20 Z=FN F(1)",
    "fn_str_not_allowed": "10 DEF FN F(Z)=Z*Z\n20 PRINT FN F(2)",
    "next_noname_lines": "10 FOR I=1 TO 2\n20 NEXT", "next_two_loops": "10 FOR I=1 TO 2:FOR J=1 TO 2:NEXT:NEXT",
    "on_gosub3": "10 ON X GOSUB 20,30,40\n20 RETURN\n30 RETURN\n40 RETURN", "str_temp": "10 X$=B$(1)+B$(2)",
    "lit_5p0": "10 X%=5.0", "lit_1e2": "10 X%=1E2", "lit_dot5": "10 X%=.5", "lit_neg0": "10 X%=-0", "lit_32767_r": "10 X=32767",
    "lit_ident_lead0": "10 X%=007", "lit_two_forms": "10 X=5:Y%=5:Z=A%+5",
    "sub_complex_left": "10 X=A(1)-Y", "and_complex_left": "10 X=A(1) AND Y", "paren": "10 X=(A+B)*(C+D)", "paren_rev": "10 X=(A+B)-(C+D)",
}

MEMORY = {
    "lib_1000": ("$1000", None, None), "prog_hgr1": (None, "HGR1", None), "prog_hgr2": (None, "HGR2", None),
    "prog_num": (None, "$5000", None), "vars_num": (None, None, "$6000"), "prog_vars": (None, "HGR1", "$7000"),
    "lib_prog": ("$4000", "$6000", None), "vars_below": (None, "$6000", "$2000"),
}
MEMORY_SRC = '10 X=1:A$="HI":PRINT X;A$\n20 GOTO 10\n30 DATA 5'
