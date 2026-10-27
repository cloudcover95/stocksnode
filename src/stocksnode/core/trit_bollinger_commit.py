"""Bollinger-band trits next to trit_side_commit.py: close vs trailing mean +/- k*sd -> balanced trits -> pack -> side_commit. Pure math.

Close above mean + k * sd of the trailing window -> +1 (upper break),
below mean - k * sd -> -1 (lower break), otherwise 0 (inside the band).
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


def band(window) -> tuple[float, float]:
    """Mean and population standard deviation of a price window."""
    n = len(window)
    if n == 0:
        return 0.0, 0.0
    m = sum(window) / n
    return m, math.sqrt(sum((x - m) ** 2 for x in window) / n)


def percent_b(prices, window: int = 5, k: float = 2.0) -> list[float]:
    """%B per index i >= window: (close - lower) / (upper - lower) over the prior `window` closes; 0.5 when flat."""
    if window < 2 or k <= 0:
        raise ValueError("need window >= 2 and k > 0")
    out = []
    for i in range(window, len(prices)):
        m, sd = band(prices[i - window : i])
        lo, hi = m - k * sd, m + k * sd
        out.append((prices[i] - lo) / (hi - lo) if hi > lo else 0.5)
    return out


def bollinger_trits(prices, window: int = 5, k: float = 2.0) -> list[int]:
    """+1 when %B > 1, -1 when %B < 0, else 0."""
    return [1 if b > 1.0 else (-1 if b < 0.0 else 0) for b in percent_b(prices, window, k)]


def bollinger_commit(prices, text: str, prev: str = GENESIS, window: int = 5, k: float = 2.0) -> dict:
    t = bollinger_trits(prices, window, k)
    pk = pack(t)
    return {"prev": prev, "trits": t, "text": text, "pack": pk.hex(), "commit": side_commit(prev, pk, text)}


def port_commits(trits, text: str, prevs=None) -> dict:
    """One side_commit per port; text is tagged with the port name."""
    prevs = prevs or {}
    pk = pack(trits)
    return {p: side_commit(prevs.get(p, GENESIS), pk, f"{p}:{text}") for p in PORTS}


def rate_band(trits, s0: float = 0.0) -> float:
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
    calm = [100.0, 100.2, 99.9, 100.1, 100.0]
    up = calm + [100.1, 105.0]
    down = calm + [94.0]
    assert bollinger_trits(up)[-1] == 1
    assert bollinger_trits(down)[-1] == -1
    assert bollinger_trits(calm + [100.05]) == [0]
    assert bollinger_trits(calm) == [] and percent_b([1.0, 1.0, 1.0], window=2) == [0.5]
    assert band([1.0, 3.0]) == (2.0, 1.0) and band([]) == (0.0, 0.0)
    t = bollinger_trits(up)
    d = bollinger_commit(up, "AAA")
    assert len(d["commit"]) == 16 and d["commit"] == side_commit(GENESIS, pack(t), "AAA")
    pc = port_commits(t, "AAA")
    assert tuple(pc) == PORTS and len(set(pc.values())) == 5
    assert engines_agree(t) and engines_agree([]) and engines_agree([-1, -1, 0, 1, 1, 0, -1])
    assert abs(rate_band([1]) - 0.05) < 1e-12
    assert RATE == 0.05 and not (MINT or SOCKET or LAYER_ONE or FETCH or UE5_LAUNCH)
    print({"trits": t, "pack": d["pack"], "commit": d["commit"], "agree": True, "ok": True})
