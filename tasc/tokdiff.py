import sys, difflib

from tasc.linediff import by_line, norm
from tasc.batch import EXPERIMENTS, load_result
from tasc.compiler.assemble import compile_program
from tasc.objfile import parse
from tasc.predict_check import options_of
fam=sys.argv[1]
for job in sys.argv[2:]:
    r=load_result(fam,job); real=r.obj(fam)
    res=compile_program((EXPERIMENTS/fam/job/'source.bas').read_bytes(), options_of(r.options))
    a=parse(real,r.obj_addr); b=parse(res.data,res.load)
    ta={e.line:e.addr for e in r.line_table}; tb={n:v for n,v in res.line_addr.items() if n>=0}
    la,lb=by_line(a.code,ta),by_line(b.code,tb)
    for ln in sorted(ta):
        if la.get(ln)!=lb.get(ln):
            print(job, 'line', ln)
            sm=difflib.SequenceMatcher(a=la[ln],b=lb[ln],autojunk=False)
            for tag,i1,i2,j1,j2 in sm.get_opcodes():
                if tag!='equal': print('  ',tag,'TASC',la[ln][max(0,i1-3):i2+2],'\n     PRED',lb[ln][max(0,j1-3):j2+2])
            break
    ka=[(k.vtype[0],k.raw.hex()) for k in a.constants]; kb=[(k.vtype[0],k.raw.hex()) for k in b.constants]
    if ka!=kb: print('  consts differ:', [l for l in difflib.ndiff([str(x) for x in ka],[str(x) for x in kb]) if l[0] in '+-'])
    lb1 = a.header.words["LOCBEG1"]
    ra = [(x.vtype[0] + ("A" if x.dims else ""), sorted(x.entries.values()), x.target - lb1 if x.target > lb1 else "K") for x in a.routines]
    lb2 = b.header.words["LOCBEG1"]
    rb = [(x.vtype[0] + ("A" if x.dims else ""), sorted(x.entries.values()), x.target - lb2 if x.target > lb2 else "K") for x in b.routines]
    if ra != rb:
        print("  routines:", [l for l in difflib.ndiff([str(x) for x in ra], [str(x) for x in rb]) if l[0] in "+-"][:10])
    if a.header.words != b.header.words:
        print("  hdr T", a.header.describe(), "\n      P", b.header.describe())
