"""Decompiler step 4: variable names that reproduce TASC's allocation order.

TASC orders symbols by a 32-bucket hash of the name, h = (3*(c1-1) + c2 + T)
mod 32 (T: real 0, string 1, int 2, +22 for arrays; INTEGER-declared names
keep T=0), with ties in insertion order.  Local storage and the routine list
are both projections of that order, so the names must be chosen to match
them.  Insertion order (seq) comes from the source we generate; the solver
merges the address and routine orders into one sequence and starts a new
bucket wherever seq goes down.
"""

from __future__ import annotations

from dataclasses import dataclass

from tasc.applesoft import TOKENS
from tasc.decomp.walk import Sym

LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
SECOND = [""] + list(LETTERS) + list("0123456789")
# two-letter keywords and names that would tokenize badly
RESERVED = {t for t in TOKENS if len(t) <= 2} | {"AT", "TO", "ON", "OR", "FN", "IF", "GR", "PI"}


def code(ch: str) -> int:
    return ord(ch) & 0x1F if ch else 0


def bucket(name: str, t: int) -> int:
    return (3 * (code(name[0]) - 1) + code(name[1:2]) + t) % 32


def type_hash(s: Sym, decl_int: bool) -> int:
    t = 0 if s.vtype == "real" or (s.vtype == "int" and decl_int) else (1 if s.vtype == "str" else 2)
    return (t + 22) % 32 if s.array else t


def suffix(s: Sym, decl_int: bool) -> str:
    if s.vtype == "str":
        return "$"
    if s.vtype == "int" and not decl_int:
        return "%"
    return ""


def _ok(name: str) -> bool:
    if name in RESERVED:
        return False
    return not any(t in name for t in ("AT", "TO", "ON", "OR", "FN", "IF"))


@dataclass
class NamePool:
    used: set[tuple[str, str, bool]]

    def take(self, b: int | None, t: int, suf: str, array: bool, prefer: str = "") -> str:
        cands = [c1 + c2 for c1 in LETTERS for c2 in SECOND]
        if prefer:
            cands.sort(key=lambda n: (not n.startswith(prefer), len(n)))
        for n in cands:
            if not _ok(n) or (n, suf, array) in self.used:
                continue
            if b is not None and bucket(n, t) != b:
                continue
            self.used.add((n, suf, array))
            return n
        raise ValueError(f"no free name in bucket {b}")


def merge_orders(nodes: list[Sym], chains: list[list[Sym]], seq: dict[Sym, int]) -> list[Sym]:
    """Linear extension of the chains' orders that keeps seq increasing as long as possible."""
    succ: dict[Sym, set[Sym]] = {n: set() for n in nodes}
    indeg = {n: 0 for n in nodes}
    for ch in chains:
        for a, b in zip(ch, ch[1:]):
            if b not in succ[a]:
                succ[a].add(b)
                indeg[b] += 1
    ready = [n for n in nodes if indeg[n] == 0]
    out: list[Sym] = []
    last = -1
    while ready:
        up = [n for n in ready if seq[n] > last]
        pick = min(up or ready, key=lambda n: seq[n])
        ready.remove(pick)
        out.append(pick)
        last = seq[pick]
        for m in succ[pick]:
            indeg[m] -= 1
            if indeg[m] == 0:
                ready.append(m)
    if len(out) != len(nodes):
        raise ValueError("cyclic order constraints")
    return out


def buckets_for(order: list[Sym], seq: dict[Sym, int]) -> dict[Sym, int]:
    out: dict[Sym, int] = {}
    b = 0
    for i, s in enumerate(order):
        if i and seq[s] < seq[order[i - 1]]:
            b += 1
        out[s] = b
    if b > 31:
        raise ValueError(f"{b + 1} buckets needed")
    return out
