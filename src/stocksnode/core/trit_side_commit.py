"""Trit side commit for price series: returns -> balanced trits -> pack -> side_commit. Pure math."""
from __future__ import annotations

import hashlib

RATE = 0.05
MINT = False
SOCKET = False
LAYER_ONE = False


def price_trits(prices, dead_band: float = 0.0) -> list[int]:
    out = []
    for a, b in zip(prices, prices[1:]):
        r = (b - a) / a if a else 0.0
        out.append(1 if r > dead_band else (-1 if r < -dead_band else 0))
    return out


def pack(trits) -> bytes:
    """Balanced trits (-1/0/1) packed 2 bits each, prefixed with 4-byte count."""
    bits = 0
    for t in trits:
        if t not in (-1, 0, 1):
            raise ValueError("trit must be -1, 0 or 1")
        bits = (bits << 2) | (t + 1)
    n = len(trits)
    return n.to_bytes(4, "big") + bits.to_bytes((2 * n + 7) // 8 or 1, "big")


def unpack(data: bytes) -> list[int]:
    n = int.from_bytes(data[:4], "big")
    bits = int.from_bytes(data[4:], "big")
    return [((bits >> (2 * (n - 1 - i))) & 3) - 1 for i in range(n)]


def side_commit(prev: str, pk: bytes, text: str) -> str:
    """sha256(prev || pack || text)[:16]."""
    return hashlib.sha256(prev.encode() + pk + text.encode()).hexdigest()[:16]


def rate_step(x: float) -> float:
    return x * RATE


if __name__ == "__main__":
    t = price_trits([100.0, 101.0, 101.0, 99.5, 100.2], dead_band=0.001)
    assert t == [1, 0, -1, 1]
    p = pack(t)
    assert unpack(p) == t
    c = side_commit("0" * 16, p, "stocks")
    assert len(c) == 16 and c == side_commit("0" * 16, p, "stocks")
    assert not (MINT or SOCKET or LAYER_ONE) and abs(rate_step(1.0) - 0.05) < 1e-12
    print({"pack": p.hex(), "commit": c, "ok": True})
