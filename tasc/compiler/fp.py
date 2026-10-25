"""Applesoft 5-byte packed floating point.

Format: exponent byte (bias 128, 0 = zero), then 4 mantissa bytes big-endian
with the implied leading 1 replaced by the sign bit.  Value = 0.1mmm... (binary)
* 2^(exp-128).

pack_decimal() rounds the exact decimal value to nearest (ties away from zero).
Whether that matches the ROM's FIN for every literal is checked against TASC
output in tests; FIN accumulates digits in FAC, so it can differ in the last bit.
"""

from __future__ import annotations

from fractions import Fraction


def pack_fraction(v: Fraction) -> bytes:
    if v == 0:
        return bytes(5)
    neg = v < 0
    a = -v if neg else v
    exp = 0
    # normalise a into [1/2, 1)
    while a >= 1:
        a /= 2
        exp += 1
    while a < Fraction(1, 2):
        a *= 2
        exp -= 1
    m = a * (1 << 32)
    mi = int(m)
    if m - mi >= Fraction(1, 2):
        mi += 1
    if mi == 1 << 32:  # rounding overflowed
        mi >>= 1
        exp += 1
    e = exp + 128
    if not 1 <= e <= 255:
        raise OverflowError(f"value {v} out of Applesoft range")
    b = mi.to_bytes(4, "big")
    first = (b[0] & 0x7F) | (0x80 if neg else 0)
    return bytes([e, first]) + b[1:]


def pack_decimal(text: str) -> bytes:
    """Pack a numeric literal as written (e.g. '1.5', '.001', '1E10')."""
    t = text.upper()
    mant, _, ex = t.partition("E")
    if mant in ("", "."):
        mant = "0"
    v = Fraction(mant if not mant.endswith(".") else mant[:-1] or "0")
    if ex:
        v *= Fraction(10) ** int(ex)
    return pack_fraction(v)


def literal_value(text: str) -> Fraction:
    t = text.upper()
    mant, _, ex = t.partition("E")
    if mant in ("", "."):
        mant = "0"
    v = Fraction(mant if not mant.endswith(".") else mant[:-1] or "0")
    if ex:
        v *= Fraction(10) ** int(ex)
    return v


def unpack(raw: bytes) -> float:
    if raw[0] == 0:
        return 0.0
    m = int.from_bytes(bytes([raw[1] | 0x80]) + raw[2:5], "big")
    v = m / 2.0**32 * 2.0 ** (raw[0] - 128)
    return -v if raw[1] & 0x80 else v
