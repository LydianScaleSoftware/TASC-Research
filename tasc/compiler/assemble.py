"""Lay out and assemble a compiled program into TASC object file bytes."""

from __future__ import annotations

from dataclasses import dataclass

from tasc.compiler.codegen import RT_RANGE, Compiler, CompileError, Item, Ref, Sym, parse_program
from tasc.harness import Options

LIB_SIZE = 4013  # RUNTIME 2.01
DISP = {"real": 0x1764, "int": 0x0D06, "str": 0x0C7F}
ARR_DISP = {"real": 0x0B11, "str": 0x0B14, "int": 0x0B17}


@dataclass
class Result:
    load: int
    data: bytes
    line_addr: dict[int, int]
    compiler: Compiler


def _symbol_order(syms: list[Sym]) -> list[Sym]:
    return sorted(syms, key=lambda s: (s.bucket, s.seq))


def assemble(c: Compiler, opts: Options) -> Result:
    lib = opts.library if isinstance(opts.library, int) else 0x0803
    delta = lib - 0x0803
    if isinstance(opts.program, int):
        prog_start = opts.program
    elif opts.program == "HGR1":
        prog_start = 0x4000
    elif opts.program == "HGR2":
        prog_start = 0x6000
    else:
        prog_start = lib + LIB_SIZE

    # COMMON block at program start: numeric then string, declaration order
    a = prog_start
    for s in c.common:
        if s.vtype != "str":
            s.addr, a = a, a + s.size()
    numcomend = a - 1
    for s in c.common:
        if s.vtype == "str":
            s.addr, a = a, a + s.size()
    strcomend = a - 1
    load = a

    # code addresses
    pc = load + 20
    labels: dict[str, int] = {}
    line_addr: dict[int, int] = {}
    pending_lines: list[int] = []
    for it in c.items:
        if it.line is not None:
            pending_lines.append(it.line)
            continue
        if it.label is not None:
            labels[it.label] = pc
            continue
        for ln in pending_lines:
            line_addr[ln] = pc
        pending_lines = []
        pc += it.size()
    for ln in pending_lines:
        line_addr[ln] = pc
    code_end = pc
    if c.common_last_line is not None:
        # observed (manual 8.2.4): lines up to the last COMMON declaration keep the address
        # the code had before COMMON moved it up, i.e. a jump there lands in the COMMON block
        for ln in list(line_addr):
            if 0 <= ln <= c.common_last_line:
                line_addr[ln] = prog_start + 20

    # constant pool
    consts = _symbol_order([k for k in c.consts.values() if k.ops or k.used])  # unused forms only fix the order
    for k in consts:
        k.addr, pc = pc, pc + len(k.raw)

    # symbols: temps, FN params, named variables
    temps = [t for vt in ("int", "real") for t in c.temps[vt]]  # observed in BALL: int temp before real temp
    # observed (PASS1): FN parameters and FN-body temps share one list in creation order
    # (main temps: int first)
    fn_syms = sorted(c.params + [t for vt in ("real", "int") for t in c.fn_temps[vt]], key=lambda t: t.seq)
    stemps = c.temps["str"]
    named = list(c.syms.values())
    num_scalars = _symbol_order([s for s in named if not s.array and s.vtype != "str"])
    num_arrays = _symbol_order([s for s in named if s.array and s.vtype != "str"])
    # observed: string scalars and string arrays share one hash order (numerics are grouped)
    strings = _symbol_order([s for s in named if s.vtype == "str"])

    # routines: numeric (temps, params, scalars), constants, strings, arrays   (order partly GUESS)
    # observed: numeric scalars, constants, numeric arrays, string scalars, string arrays
    # (arrays always get a routine)
    rtn_order = ([s for s in temps + fn_syms + num_scalars if s.ops] + [k for k in consts if k.ops] + num_arrays
                 + [s for s in stemps + c.fn_temps["str"] + strings if s.ops or s.array or s.common is not None])
    entry: dict[tuple[int, int], int] = {}
    for s in rtn_order:
        s.rtn = pc
        if s.array:
            entry[(id(s), 0)], entry[(id(s), 1)] = pc, pc + 2
            pc += 9 + 2 * len(s.dims)
        elif s.vtype == "str":
            entry[(id(s), 0)], entry[(id(s), 1)] = pc, pc + 2
            pc += 10
        else:
            for i, op in enumerate(sorted(s.ops, reverse=True)):
                entry[(id(s), op)] = pc + 3 * i
            pc += 3 * len(s.ops) + 6
    obj_end = pc

    # local variables
    var_start = opts.variables if isinstance(opts.variables, int) else obj_end
    a = var_start
    for s in temps + fn_syms + [s for s in num_scalars + num_arrays if s.common is None]:
        s.addr, a = a, a + s.size()
    locnumend = a - 1
    for s in stemps + c.fn_temps["str"] + [s for s in strings if s.common is None]:
        s.addr, a = a, a + s.size()
    locstrend = a - 1

    # data block chain
    data_first = [labels[f] for f in c.data_blocks]

    def resolve(ref: Ref) -> int:
        if ref.kind == "abs":
            return int(ref.a)  # type: ignore[arg-type]
        if ref.kind == "rt":
            v = int(ref.a)  # type: ignore[arg-type]
            if not (RT_RANGE[0] <= v < RT_RANGE[1]):
                raise CompileError(f"RUNTIME address out of range {v:04X}")
            return v + delta
        if ref.kind == "entry":
            s = ref.a
            assert isinstance(s, Sym)
            return entry[(id(s), ref.b)]
        if ref.kind == "line":
            n = int(ref.a)  # type: ignore[arg-type]
            if n not in line_addr:
                raise CompileError(f"undefined line {n}")
            return line_addr[n]
        if ref.kind == "label":
            return labels[str(ref.a)]
        if ref.kind == "store":
            s = ref.a
            assert isinstance(s, Sym)
            return s.addr + ref.b
        if ref.kind == "datalink":
            i = int(ref.a)  # type: ignore[arg-type]
            return data_first[i + 1] if i + 1 < len(data_first) else 0
        raise CompileError(f"ref {ref.kind}")

    out = bytearray()
    for it in c.items:
        if it.op is not None:
            assert it.ref is not None
            v = resolve(it.ref)
            out += bytes([it.op, v & 0xFF, v >> 8])
        elif it.word:
            assert it.ref is not None
            v = resolve(it.ref)
            out += bytes([v & 0xFF, v >> 8])
        else:
            out += it.raw
    for k in consts:
        out += k.raw
    for s in rtn_order:
        if s.array:
            disp = ARR_DISP[s.vtype] + delta
            out += bytes([0x38, 0xA9, 0x18, 0x20, disp & 0xFF, disp >> 8, s.addr & 0xFF, s.addr >> 8, len(s.dims)])
            for d in reversed(s.dims):  # observed: rightmost subscript first
                out += bytes([d & 0xFF, d >> 8])
        elif s.vtype == "str":
            disp = DISP["str"] + delta
            out += bytes([0x38, 0xA9, 0x18, 0xA0, s.addr >> 8, 0xA9, s.addr & 0xFF, 0x4C, disp & 0xFF, disp >> 8])
        else:
            ops = sorted(s.ops, reverse=True)
            for op in ops[:-1]:
                out += bytes([0xA2, op, 0xAD])
            disp = DISP[s.vtype] + delta
            out += bytes([0xA2, ops[-1], 0xA0, s.addr >> 8, 0xA9, s.addr & 0xFF, 0x4C, disp & 0xFF, disp >> 8])

    locbeg1 = var_start - 1
    highest = max(obj_end - 1, locstrend, strcomend)
    comb1 = prog_start - 1
    hdr = [data_first[0] if data_first else 0, highest, comb1, numcomend, strcomend, locbeg1, locnumend, locstrend]
    head = bytearray([0x20, lib & 0xFF, lib >> 8])
    for w in hdr:
        head += bytes([w & 0xFF, w >> 8])
    head.append(c.common_flag)
    data = bytes(head) + bytes(out)
    if len(data) != obj_end - load:
        raise CompileError(f"size mismatch {len(data)} vs {obj_end - load}")
    return Result(load, data, line_addr, c)


def compile_program(program: bytes, opts: Options | None = None) -> Result:
    opts = opts or Options()
    c = Compiler(opts)
    c.compile_lines(parse_program(program))
    return assemble(c, opts)
