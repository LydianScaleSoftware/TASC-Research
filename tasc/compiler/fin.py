"""Bit-exact translation of the Applesoft ROM number input (FIN, $EC4A) and the
floating-point routines it uses.

TASC packs numeric constants as the ROM does (verified: 3.14159 -> 82 49 0F CF 82,
one ulp above the correctly rounded value).  Each routine below follows the ROM
listing instruction by instruction (labels from Bob Sander-Cederlof's commented
source), operating on a zero-page model, so rounding behaves exactly as on the
Apple II.
"""

from __future__ import annotations

FAC, ARG = 0x9D, 0xA5  # exponent, mantissa 1..4, sign
FAC_EXT, ARG_EXT, SGNCPR, SHIFT_SIGN_EXT = 0xAC, 0x92, 0xAB, 0xA4
RESULT = 0x62
TMPEXP, EXPON, DPFLG, EXPSGN, SERLEN = 0x99, 0x9A, 0x9B, 0x9C, 0xA3


class FPError(Exception):
    pass


class FP:
    def __init__(self) -> None:
        self.m = bytearray(256)
        self.a = self.x = self.y = 0
        self.c = False

    # -- 6502 helpers --------------------------------------------------
    def adc(self, v: int) -> int:
        r = self.a + v + (1 if self.c else 0)
        self.c = r > 0xFF
        self.a = r & 0xFF
        return self.a

    def sbc(self, v: int) -> int:
        r = self.a - v - (0 if self.c else 1)
        self.c = r >= 0
        self.a = r & 0xFF
        return self.a

    def rol(self, addr: int) -> int:
        v = (self.m[addr] << 1) | (1 if self.c else 0)
        self.c = v > 0xFF
        self.m[addr] = v & 0xFF
        return self.m[addr]

    def ror(self, addr: int) -> int:
        v = self.m[addr] | (0x100 if self.c else 0)
        self.c = bool(v & 1)
        self.m[addr] = v >> 1
        return self.m[addr]

    def asl(self, addr: int) -> int:
        v = self.m[addr] << 1
        self.c = v > 0xFF
        self.m[addr] = v & 0xFF
        return self.m[addr]

    def lsr(self, addr: int) -> int:
        v = self.m[addr]
        self.c = bool(v & 1)
        self.m[addr] = v >> 1
        return self.m[addr]

    # -- FADD family ($E7C1) -----------------------------------------------
    def faddt(self) -> None:
        """FAC = ARG + FAC; caller set SGNCPR; entered with Z from FAC exponent."""
        if self.m[FAC] == 0:
            self.copy_arg_to_fac()
            return
        self.m[ARG_EXT] = self.m[FAC_EXT]
        self.x = ARG
        self.a = self.m[ARG]
        self.fadd_2()

    def fadd_2(self) -> None:
        self.y = self.a
        if self.y == 0:
            return  # RTS.10: ARG = 0
        self.c = True
        self.sbc(self.m[FAC])
        if self.a == 0:
            self.fadd_3()
            return
        if not self.c:  # ARG has the smaller exponent
            self.y = 0
            self.m[FAC_EXT] = 0
        else:  # FAC has the smaller exponent
            self.m[FAC] = self.y
            self.m[FAC + 5] = self.m[ARG + 5]  # sign
            self.a ^= 0xFF
            self.adc(0)  # carry was set
            self.y = 0
            self.m[ARG_EXT] = 0
            self.x = FAC
        # .2: CMP #$F9 / BMI FADD.1 (more than 7 bits to shift)
        self.c = self.a >= 0xF9
        if (self.a - 0xF9) & 0x80:
            self.shift_right()  # FADD.1
            self.fadd_3()
            return
        self.y = self.a
        self.a = self.m[FAC_EXT]
        self.lsr(self.x + 1)
        self.shift_right_4()
        self.fadd_3()

    @staticmethod
    def _signed(v: int) -> int:
        return v - 256 if v & 0x80 else v

    def fadd_3(self) -> None:
        if not (self.m[SGNCPR] & 0x80):  # BIT SGNCPR / BPL: same signs
            self.fadd_4()
            return
        yreg = FAC if self.x == ARG else ARG  # subtract the unadjusted one minus the adjusted one
        self.c = True
        self.a ^= 0xFF
        self.adc(self.m[ARG_EXT])
        self.m[FAC_EXT] = self.a
        for i in (4, 3, 2, 1):
            self.a = self.m[yreg + i]
            self.sbc(self.m[self.x + i])
            self.m[FAC + i] = self.a
        self.normalize_fac_1()

    def fadd_4(self) -> None:
        self.adc(self.m[ARG_EXT])
        self.m[FAC_EXT] = self.a
        for i in (4, 3, 2, 1):
            self.a = self.m[FAC + i]
            self.adc(self.m[ARG + i])
            self.m[FAC + i] = self.a
        self.normalize_fac_5()

    # -- normalize ($E829) ------------------------------------------------
    def normalize_fac_1(self) -> None:
        if not self.c:
            self.complement_fac()
        self.normalize_fac_2()

    def normalize_fac_2(self) -> None:
        self.y = 0
        self.a = 0
        self.c = False
        while True:
            if self.m[FAC + 1] != 0:
                self.normalize_fac_4()
                return
            self.m[FAC + 1] = self.m[FAC + 2]
            self.m[FAC + 2] = self.m[FAC + 3]
            self.m[FAC + 3] = self.m[FAC + 4]
            self.m[FAC + 4] = self.m[FAC_EXT]
            self.m[FAC_EXT] = 0
            self.adc(8)
            if self.a == 32:
                self.zero_fac()
                return

    def zero_fac(self) -> None:
        self.m[FAC] = 0
        self.m[FAC + 5] = 0

    def normalize_fac_4(self) -> None:
        # loop: NORMALIZE.FAC.3 / .4 with X = FAC+1 tested via N flag of last op
        n = self.m[FAC + 1] & 0x80
        while not n:
            self.adc(1)
            self.asl(FAC_EXT)
            self.rol(FAC + 4)
            self.rol(FAC + 3)
            self.rol(FAC + 2)
            n = self.rol(FAC + 1) & 0x80
        self.c = True
        self.sbc(self.m[FAC])
        if self.c:
            self.zero_fac()  # underflow
            return
        self.a ^= 0xFF
        self.adc(1)
        self.m[FAC] = self.a
        self.normalize_fac_5()

    def normalize_fac_5(self) -> None:
        if not self.c:
            return
        self.normalize_fac_6()

    def normalize_fac_6(self) -> None:
        self.m[FAC] = (self.m[FAC] + 1) & 0xFF
        if self.m[FAC] == 0:
            raise FPError("OVERFLOW")
        for addr in (FAC + 1, FAC + 2, FAC + 3, FAC + 4, FAC_EXT):
            self.ror(addr)

    def complement_fac(self) -> None:
        self.m[FAC + 5] ^= 0xFF
        self.complement_fac_mantissa()

    def complement_fac_mantissa(self) -> None:
        for addr in (FAC + 1, FAC + 2, FAC + 3, FAC + 4, FAC_EXT):
            self.m[addr] ^= 0xFF
        self.m[FAC_EXT] = (self.m[FAC_EXT] + 1) & 0xFF
        if self.m[FAC_EXT] != 0:
            return
        self.increment_fac_mantissa()

    def increment_fac_mantissa(self) -> int:
        """Returns the last incremented byte (for the BNE that follows)."""
        for addr in (FAC + 4, FAC + 3, FAC + 2):
            self.m[addr] = (self.m[addr] + 1) & 0xFF
            if self.m[addr] != 0:
                return self.m[addr]
        self.m[FAC + 1] = (self.m[FAC + 1] + 1) & 0xFF
        return self.m[FAC + 1]

    # -- shifter ($E8DA) ----------------------------------------------------
    def shift_right(self) -> None:
        """SHIFT.RIGHT: A = negative shift count, X = base, carry as left by the caller.
        Returns extension bits in A, C=0."""
        while True:
            self.adc(8)
            if self.a & 0x80 or self.a == 0:  # BMI / BEQ SHIFT.RIGHT.2 (then falls back here)
                self.shift_right_2()
                continue
            break
        self.sbc(8)  # undo the ADC (carry from the ADC is significant)
        self.y = self.a
        self.a = self.m[FAC_EXT]
        if self.c:  # BCS SHIFT.RIGHT.5
            self.c = False
            return
        self._shift_right_3_loop()

    def shift_right_2(self) -> None:
        x = self.x
        self.m[FAC_EXT] = self.m[x + 4]
        self.m[x + 4] = self.m[x + 3]
        self.m[x + 3] = self.m[x + 2]
        self.m[x + 2] = self.m[x + 1]
        self.m[x + 1] = self.m[SHIFT_SIGN_EXT]

    def _shift_right_3_loop(self) -> None:
        while self.y != 0:
            x = self.x
            self.asl(x + 1)
            if self.c:
                self.m[x + 1] = (self.m[x + 1] + 1) & 0xFF
            self.ror(x + 1)
            self.ror(x + 1)
            self.ror(x + 2)
            self.ror(x + 3)
            self.ror(x + 4)
            self._ror_a()
            self.y = (self.y + 1) & 0xFF
        self.c = False

    def _ror_a(self) -> None:
        v = self.a | (0x100 if self.c else 0)
        self.c = bool(v & 1)
        self.a = v >> 1

    def shift_right_4(self) -> None:
        """Entry with the first ROR of byte 1 already done (Y = negative count)."""
        x = self.x
        self.ror(x + 2)
        self.ror(x + 3)
        self.ror(x + 4)
        self._ror_a()
        self.y = (self.y + 1) & 0xFF
        self._shift_right_3_loop()

    # -- moves and rounding ($EB2B..$EB7F) ------------------------------------
    def round_fac(self) -> None:
        if self.m[FAC] == 0:
            return
        self.asl(FAC_EXT)
        if not self.c:
            return
        if self.increment_fac_mantissa() != 0:
            return
        self.normalize_fac_6()

    def copy_fac_to_arg_rounded(self) -> None:
        self.round_fac()
        for i in range(6):
            self.m[ARG + i] = self.m[FAC + i]
        self.m[FAC_EXT] = 0
        self.a = self.m[FAC]  # last byte copied is FAC exponent (LDA FAC-1+1)

    def copy_arg_to_fac(self) -> None:
        for i in range(6):
            self.m[FAC + i] = self.m[ARG + i]
        self.m[FAC_EXT] = 0

    def load_fac(self, packed: bytes) -> None:
        self.m[FAC + 4] = packed[4]
        self.m[FAC + 3] = packed[3]
        self.m[FAC + 2] = packed[2]
        self.m[FAC + 5] = packed[1]
        self.m[FAC + 1] = packed[1] | 0x80
        self.m[FAC] = packed[0]
        self.m[FAC_EXT] = 0

    def packed(self) -> bytes:
        """STORE.FAC.AT.YX.ROUNDED."""
        self.round_fac()
        out = bytes([self.m[FAC], (self.m[FAC + 5] | 0x7F) & self.m[FAC + 1], self.m[FAC + 2], self.m[FAC + 3],
                     self.m[FAC + 4]])
        self.m[FAC_EXT] = 0
        return out

    def float_a(self, v: int) -> None:
        """FLOAT: signed byte in A -> FAC."""
        self.m[FAC + 1] = v
        self.m[FAC + 2] = 0
        self.x = 0x88
        self.a = self.m[FAC + 1] ^ 0xFF
        self.c = bool(self.a & 0x80)  # ROL: carry <- bit 7
        self.a = ((self.a << 1) & 0xFF)
        self.m[FAC + 4] = 0
        self.m[FAC + 3] = 0
        self.m[FAC] = self.x
        self.m[FAC_EXT] = 0
        self.m[FAC + 5] = 0
        self.normalize_fac_1()

    # -- multiply/divide by ten ($EA39, $EA55) -------------------------------
    def mul10(self) -> None:
        self.copy_fac_to_arg_rounded()
        if self.a == 0:
            return
        self.c = False
        self.adc(2)
        if self.c:
            raise FPError("OVERFLOW")
        self.m[SGNCPR] = 0
        self.fadd_2()  # A = exponent+2 -> FAC*5 (ARG*4 + FAC)
        self.m[FAC] = (self.m[FAC] + 1) & 0xFF
        if self.m[FAC] == 0:
            raise FPError("OVERFLOW")

    def div10(self) -> None:
        self.copy_fac_to_arg_rounded()
        self.m[SGNCPR] = 0
        self.load_fac(bytes([0x84, 0x20, 0, 0, 0]))
        self.fdivt()

    def add_exponents(self) -> None:
        self.a = self.m[ARG]
        if self.a == 0:
            self.zero_fac()
            raise _Zero()
        self.c = False
        self.adc(self.m[FAC])
        if self.c:
            if self.a & 0x80:
                raise FPError("OVERFLOW")
            self.c = False
            # skip the BPL ZERO
        else:
            if not (self.a & 0x80):
                self.zero_fac()
                raise _Zero()
        self.adc(0x80)
        self.m[FAC] = self.a
        if self.a == 0:
            self.m[FAC + 5] = 0
            return
        self.m[FAC + 5] = self.m[SGNCPR]

    def fdivt(self) -> None:
        if self.m[FAC] == 0:
            raise FPError("DIVISION BY ZERO")
        self.round_fac()
        self.a = 0
        self.c = True
        self.sbc(self.m[FAC])
        self.m[FAC] = self.a
        try:
            self.add_exponents()
        except _Zero:
            return
        self.m[FAC] = (self.m[FAC] + 1) & 0xFF
        if self.m[FAC] == 0:
            raise FPError("OVERFLOW")
        x = -4
        a = 1  # sentinel
        state = "cmp"  # label .1
        res = [0, 0, 0, 0]
        while True:
            if state == "cmp":
                ge = True
                for i in (1, 2, 3, 4):
                    if self.m[ARG + i] != self.m[FAC + i]:
                        ge = self.m[ARG + i] > self.m[FAC + i]
                        break
                c_cmp = ge
                state = "roll"
            if state == "roll":  # .2 : PHP / ROL
                saved = c_cmp
                v = (a << 1) | (1 if c_cmp else 0)
                carry_out = v > 0xFF
                a = v & 0xFF
                if carry_out:
                    x += 1
                    if x <= 0:
                        res[x + 3] = a  # STA RESULT+3,X
                    if x == 0:
                        a = 0x40  # .6: a few extension bits
                        c_cmp = saved
                        # fall to .3 with the saved compare
                    elif x > 0:  # .7 final exit (X=1)
                        a = (a << 6) & 0xFF
                        self.m[FAC_EXT] = a
                        for i in range(4):
                            self.m[FAC + 1 + i] = res[i]
                        self.normalize_fac_2()
                        return
                    else:
                        a = 1
                # .3: PLP -> carry = saved compare
                if saved:  # .5: subtract FAC from ARG
                    self.c = True
                    for i in (4, 3, 2, 1):
                        self.a = self.m[ARG + i]
                        self.sbc(self.m[FAC + i])
                        self.m[ARG + i] = self.a
                # .4: shift ARG left
                self.c = False
                self.asl(ARG + 4)
                self.rol(ARG + 3)
                self.rol(ARG + 2)
                top = self.rol(ARG + 1)
                if self.c:
                    c_cmp = True
                    state = "roll"
                elif top & 0x80:
                    state = "cmp"
                else:
                    c_cmp = False
                    state = "roll"


class _Zero(Exception):
    pass


def fin(text: str) -> bytes:
    """Convert a numeric literal as typed (digits, '.', E, exponent sign) to packed
    bytes exactly as the ROM's FIN + STORE.FAC.AT.YX.ROUNDED would."""
    f = FP()
    s = text.upper()
    i = 0
    tmpexp = expon = 0
    dpflg = False
    expneg = False

    def addacc(d: int) -> None:
        f.copy_fac_to_arg_rounded()
        f.float_a(d)
        f.m[SGNCPR] = f.m[ARG + 5] ^ f.m[FAC + 5]
        f.faddt()

    while i < len(s):
        ch = s[i]
        if ch.isdigit():
            if dpflg:
                tmpexp += 1
            f.mul10()
            addacc(int(ch))
            i += 1
            continue
        if ch == ".":
            if dpflg:
                break
            dpflg = True
            i += 1
            continue
        if ch == "E":
            i += 1
            if i < len(s) and s[i] in "+-":
                expneg = s[i] == "-"
                i += 1
            while i < len(s) and s[i].isdigit():
                if expon >= 10:  # GETEXP: more than two digits
                    if expneg:
                        expon = 100
                    else:
                        raise FPError("OVERFLOW")
                else:
                    expon = (expon * 10 + int(s[i])) & 0xFF
                i += 1
            break
        break
    e = ((-expon if expneg else expon) - tmpexp) & 0xFF  # EXPON is one byte
    if e & 0x80:
        for _ in range(256 - e):
            f.div10()
    else:
        for _ in range(e):
            f.mul10()
    return f.packed()
