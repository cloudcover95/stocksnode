"""CCI-band trits next to trit_side_commit.py: close vs trailing SMA / mean-dev -> balanced trits -> pack -> side_commit. Pure math.

CCI = (close - SMA) / (0.015 * mean_absolute_deviation) over the prior `window` closes plus the current one.
CCI > hi -> +1 (above the upper band), CCI < lo -> -1 (below the lower band), otherwise 0.
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
_SCALE = 0.015


def cci(prices, window: int = 5) -> list[float]:
    """CCI per index i >= window - 1 over prices[i - window + 1 : i + 1]; 0.0 when MAD is flat."""
    if window < 2:
        raise ValueError("need window >= 2")
    out = []
    for i in range(window - 1, len(prices)):
        w = prices[i - window + 1 : i + 1]
        m = sum(w) / window
        mad = sum(abs(x - m) for x in w) / window
        out.append((prices[i] - m) / (_SCALE * mad) if mad else 0.0)
    return out


def cci_trits(prices, window: int = 5, lo: float = -100.0, hi: float = 100.0) -> list[int]:
    """+1 when CCI > hi, -1 when CCI < lo, else 0."""
    if lo >= hi:
        raise ValueError("need lo < hi")
    return [1 if v > hi else (-1 if v < lo else 0) for v in cci(prices, window)]


def cci_commit(prices, text: str, prev: str = GENESIS, window: int = 5, lo: float = -100.0, hi: float = 100.0) -> dict:
    t = cci_trits(prices, window, lo, hi)
    pk = pack(t)
    return {"prev": prev, "trits": t, "text": text, "pack": pk.hex(), "commit": side_commit(prev, pk, text)}


def port_commits(trits, text: str, prevs=None) -> dict:
    """One side_commit per port; text is tagged with the port name."""
    prevs = prevs or {}
    pk = pack(trits)
    return {p: side_commit(prevs.get(p, GENESIS), pk, f"{p}:{text}") for p in PORTS}


def rate_cci(trits, s0: float = 0.0) -> float:
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
    # Flat window -> CCI 0 -> trit 0
    flat = [100.0, 100.0, 100.0, 100.0, 100.0]
    assert cci(flat) == [0.0] and cci_trits(flat) == [0]
    # Strong up-close vs prior window drives CCI above +100
    up = [100.0, 100.5, 101.0, 101.5, 102.0, 110.0]
    assert cci_trits(up, window=5)[-1] == 1
    # Strong down-close drives CCI below -100
    down = [100.0, 99.5, 99.0, 98.5, 98.0, 90.0]
    assert cci_trits(down, window=5)[-1] == -1
    assert cci([], window=5) == [] and cci([1.0], window=2) == []
    t = cci_trits(up, window=5)
    d = cci_commit(up, "AAA", window=5)
    assert len(d["commit"]) == 16 and d["commit"] == side_commit(GENESIS, pack(t), "AAA")
    pc = port_commits(t, "AAA")
    assert tuple(pc) == PORTS and len(set(pc.values())) == 5
    assert engines_agree(t) and engines_agree([]) and engines_agree([-1, -1, 0, 1, 1, 0, -1])
    assert abs(rate_cci([1]) - 0.05) < 1e-12
    assert RATE == 0.05 and not (MINT or SOCKET or LAYER_ONE or FETCH or UE5_LAUNCH)
    assert PORTS == ("Home", "OSai", "FieldCore", "Flagstaff", "JuniorLLM")
    print({"trits": t, "pack": d["pack"], "commit": d["commit"], "agree": True, "ok": True})
