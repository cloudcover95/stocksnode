"""Williams %R trits next to trit_side_commit.py: close vs trailing high/low range -> balanced trits -> pack -> side_commit. Pure math.

%R = (high - close) / (high - low) over the prior `window` closes plus the current one, in [0, 1].
%R < lo (close near the top of the range) -> +1, %R > hi (near the bottom) -> -1, otherwise 0.
Each port keeps its own commit chain over the same trits.
Ports (names only, no addresses): Home, OSai, FieldCore, Flagstaff, JuniorLLM.
"""
from __future__ import annotations

import hashlib

try:
    from .trit_side_commit import LAYER_ONE, MINT, RATE, SOCKET, pack, side_commit, unpack
except ImportError:
    from trit_side_commit import LAYER_ONE, MINT, RATE, SOCKET, pack, side_commit, unpack

FETCH = False
UE5_LAUNCH = False
PORTS = ("Home", "OSai", "FieldCore", "Flagstaff", "JuniorLLM")
GENESIS = "0" * 16


def williams_r(prices, window: int = 5) -> list[float]:
    """%R per index i >= window over prices[i - window : i + 1]; 0.5 when the range is flat."""
    if window < 1:
        raise ValueError("need window >= 1")
    out = []
    for i in range(window, len(prices)):
        w = prices[i - window : i + 1]
        hi, lo = max(w), min(w)
        out.append((hi - prices[i]) / (hi - lo) if hi > lo else 0.5)
    return out


def williams_trits(prices, window: int = 5, lo: float = 0.2, hi: float = 0.8) -> list[int]:
    """+1 when %R < lo, -1 when %R > hi, else 0."""
    if not 0.0 <= lo < hi <= 1.0:
        raise ValueError("need 0 <= lo < hi <= 1")
    return [1 if r < lo else (-1 if r > hi else 0) for r in williams_r(prices, window)]


def williams_commit(prices, text: str, prev: str = GENESIS, window: int = 5, lo: float = 0.2, hi: float = 0.8) -> dict:
    t = williams_trits(prices, window, lo, hi)
    pk = pack(t)
    return {"prev": prev, "trits": t, "text": text, "pack": pk.hex(), "commit": side_commit(prev, pk, text)}


def port_commits(trits, text: str, prevs=None) -> dict:
    """One side_commit per port; text is tagged with the port name."""
    prevs = prevs or {}
    pk = pack(trits)
    return {p: side_commit(prevs.get(p, GENESIS), pk, f"{p}:{text}") for p in PORTS}


def port_chain(series, prevs=None) -> dict:
    """Advance every port's chain over a list of (trits, text) steps; returns the final head per port."""
    heads = {p: (prevs or {}).get(p, GENESIS) for p in PORTS}
    for trits, text in series:
        heads = port_commits(trits, text, heads)
    return heads


def rate_williams(trits, s0: float = 0.0) -> float:
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
    base = [100.0, 101.0, 99.0, 100.5, 100.0]
    top = base + [102.0]
    bottom = base + [98.0]
    assert williams_trits(top) == [1]
    assert williams_trits(bottom) == [-1]
    assert williams_trits(base + [100.0]) == [0]
    assert williams_r([1.0, 1.0, 1.0], window=2) == [0.5] and williams_trits(base) == []
    t = williams_trits(top + [97.0, 99.0])
    d = williams_commit(top, "AAA")
    assert len(d["commit"]) == 16 and d["commit"] == side_commit(GENESIS, pack(d["trits"]), "AAA")
    pc = port_commits(t, "AAA")
    assert tuple(pc) == PORTS and len(set(pc.values())) == 5
    heads = port_chain([(t, "AAA"), ([1, 0], "BBB")])
    assert heads == port_commits([1, 0], "BBB", pc)
    assert engines_agree(t) and engines_agree([]) and engines_agree([-1, -1, 0, 1, 1, 0, -1])
    assert abs(rate_williams([1]) - 0.05) < 1e-12
    assert RATE == 0.05 and not (MINT or SOCKET or LAYER_ONE or FETCH or UE5_LAUNCH)
    print({"trits": t, "pack": d["pack"], "commit": d["commit"], "agree": True, "ok": True})
