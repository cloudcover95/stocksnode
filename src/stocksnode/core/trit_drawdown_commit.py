"""Drawdown trits next to trit_side_commit.py: running-peak -> balanced trits -> pack -> side_commit. Pure math.

New high -> +1, drawdown deeper than the band -> -1, otherwise 0.
Ports (names only, no addresses): Home, OSai, FieldCore, Flagstaff, JuniorLLM.
"""
from __future__ import annotations

import hashlib

try:
    from .trit_side_commit import LAYER_ONE, MINT, RATE, SOCKET, pack, side_commit
except ImportError:
    from trit_side_commit import LAYER_ONE, MINT, RATE, SOCKET, pack, side_commit

FETCH = False
UE5_LAUNCH = False
PORTS = ("Home", "OSai", "FieldCore", "Flagstaff", "JuniorLLM")
GENESIS = "0" * 16


def drawdown_trits(prices, band: float = 0.0) -> list[int]:
    """One trit per step after the first price, measured against the running peak."""
    out = []
    if not prices:
        return out
    peak = prices[0]
    for p in prices[1:]:
        if p > peak:
            peak = p
            out.append(1)
        else:
            dd = (peak - p) / peak if peak else 0.0
            out.append(-1 if dd > band else 0)
    return out


def max_drawdown(prices) -> float:
    peak, worst = None, 0.0
    for p in prices:
        peak = p if peak is None or p > peak else peak
        if peak:
            worst = max(worst, (peak - p) / peak)
    return worst


def drawdown_commit(prices, text: str, prev: str = GENESIS, band: float = 0.0) -> dict:
    t = drawdown_trits(prices, band)
    pk = pack(t)
    return {"prev": prev, "trits": t, "text": text, "pack": pk.hex(), "commit": side_commit(prev, pk, text)}


def rate_drawdown(trits, s0: float = 0.0) -> float:
    """Same accumulator shape as trit_signal_chain.rate_signal: s <- (1 - RATE) * s + RATE * t."""
    s = s0
    for t in trits:
        s = (1.0 - RATE) * s + RATE * t
    return s


def _pack_local(trits) -> bytes:
    """Independent engine: 4-byte big-endian count + 2 bits per trit (t + 1)."""
    n = len(trits)
    bits = 0
    for t in trits:
        bits = (bits << 2) | (t + 1)
    return n.to_bytes(4, "big") + bits.to_bytes((2 * n + 7) // 8 or 1, "big")


def _side_commit_local(prev: str, pk: bytes, text: str) -> str:
    return hashlib.sha256(prev.encode() + pk + text.encode()).hexdigest()[:16]


def engines_agree(trits, prev: str = GENESIS, text: str = "stocks") -> bool:
    a, b = pack(trits), _pack_local(trits)
    return a == b and side_commit(prev, a, text) == _side_commit_local(prev, b, text)


if __name__ == "__main__":
    px = [100.0, 102.0, 101.5, 98.0, 103.0, 103.0]
    t = drawdown_trits(px, band=0.01)
    assert t == [1, 0, -1, 1, 0]
    assert drawdown_trits([]) == [] and drawdown_trits([5.0]) == []
    assert abs(max_drawdown(px) - (4.0 / 102.0)) < 1e-12
    d = drawdown_commit(px, "AAA", band=0.01)
    assert len(d["commit"]) == 16 and d["commit"] == side_commit(GENESIS, pack(t), "AAA")
    assert engines_agree(t) and engines_agree([]) and engines_agree([-1, -1, 0, 1, 1, 0, -1])
    assert abs(rate_drawdown([1]) - 0.05) < 1e-12
    assert RATE == 0.05 and not (MINT or SOCKET or LAYER_ONE or FETCH or UE5_LAUNCH)
    assert PORTS == ("Home", "OSai", "FieldCore", "Flagstaff", "JuniorLLM")
    print({"trits": t, "pack": d["pack"], "commit": d["commit"], "agree": True, "ok": True})
