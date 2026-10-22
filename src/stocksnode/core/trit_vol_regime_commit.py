"""Volatility-regime trits next to trit_side_commit.py: short vs long realized vol -> balanced trits -> pack -> side_commit. Pure math.

Short-window vol above long-window vol by more than the band -> +1 (expanding),
below by more than the band -> -1 (contracting), otherwise 0.
Each port keeps its own commit chain over the same trits.
Ports (names only, no addresses): Home, OSai, FieldCore, Flagstaff, JuniorLLM.
"""
from __future__ import annotations

import hashlib
import math

try:
    from .trit_side_commit import LAYER_ONE, MINT, RATE, SOCKET, pack, side_commit, unpack
except ImportError:
    from trit_side_commit import LAYER_ONE, MINT, RATE, SOCKET, pack, side_commit, unpack

FETCH = False
UE5_LAUNCH = False
PORTS = ("Home", "OSai", "FieldCore", "Flagstaff", "JuniorLLM")
GENESIS = "0" * 16


def returns(prices) -> list[float]:
    return [((b - a) / a if a else 0.0) for a, b in zip(prices, prices[1:])]


def realized_vol(rets) -> float:
    """Population standard deviation of a return window; 0.0 when empty."""
    n = len(rets)
    if n == 0:
        return 0.0
    m = sum(rets) / n
    return math.sqrt(sum((r - m) ** 2 for r in rets) / n)


def vol_regime_trits(prices, short: int = 3, long: int = 6, band: float = 0.0) -> list[int]:
    """One trit per return index i >= long - 1, comparing trailing short vs long windows."""
    if short < 1 or long < short:
        raise ValueError("need 1 <= short <= long")
    r = returns(prices)
    out = []
    for i in range(long - 1, len(r)):
        s = realized_vol(r[i - short + 1 : i + 1])
        l = realized_vol(r[i - long + 1 : i + 1])
        ratio = s / l - 1.0 if l else 0.0
        out.append(1 if ratio > band else (-1 if ratio < -band else 0))
    return out


def vol_regime_commit(prices, text: str, prev: str = GENESIS, short: int = 3, long: int = 6, band: float = 0.0) -> dict:
    t = vol_regime_trits(prices, short, long, band)
    pk = pack(t)
    return {"prev": prev, "trits": t, "text": text, "pack": pk.hex(), "commit": side_commit(prev, pk, text)}


def port_commits(trits, text: str, prevs=None) -> dict:
    """One side_commit per port; text is tagged with the port name."""
    prevs = prevs or {}
    pk = pack(trits)
    return {p: side_commit(prevs.get(p, GENESIS), pk, f"{p}:{text}") for p in PORTS}


def rate_regime(trits, s0: float = 0.0) -> float:
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
    return a == b and unpack(a) == list(trits) and side_commit(prev, a, text) == _side_commit_local(prev, b, text)


if __name__ == "__main__":
    calm = [100.0, 100.1, 100.0, 100.1, 100.0, 100.1, 100.0]
    wild = calm + [103.0, 98.0, 104.0]
    t = vol_regime_trits(wild, short=3, long=6, band=0.05)
    assert t[-1] == 1 and all(x in (-1, 0, 1) for x in t)
    assert vol_regime_trits(calm[:3]) == []
    assert abs(realized_vol([0.01, -0.01]) - 0.01) < 1e-12 and realized_vol([]) == 0.0
    cooling = [100.0, 104.0, 97.0, 103.0, 100.0, 100.1, 100.0, 100.1]
    assert vol_regime_trits(cooling, short=2, long=5, band=0.05)[-1] == -1
    d = vol_regime_commit(wild, "AAA", band=0.05)
    assert len(d["commit"]) == 16 and d["commit"] == side_commit(GENESIS, pack(t), "AAA")
    pc = port_commits(t, "AAA")
    assert tuple(pc) == PORTS and len(set(pc.values())) == 5
    assert engines_agree(t) and engines_agree([]) and engines_agree([-1, -1, 0, 1, 1, 0, -1])
    assert abs(rate_regime([1]) - 0.05) < 1e-12
    assert RATE == 0.05 and not (MINT or SOCKET or LAYER_ONE or FETCH or UE5_LAUNCH)
    print({"trits": t, "pack": d["pack"], "commit": d["commit"], "agree": True, "ok": True})
