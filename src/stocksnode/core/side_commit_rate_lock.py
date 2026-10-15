"""Side-commit chain + rate lock for stocksnode price trits. Pure math; stdlib only; no network.

Close rule: sha256(prev || pack || text)[:16], with the i2s 2-bit pack (0->0, 1->1, -1->2)
used by web3node side_commit_rate_lock.py and JuniorLLM scripts/i2s_key_builder.py.
Note: src/stocksnode/core/trit_side_commit.py uses a count-prefixed pack, so its commits
differ from this file's even though the close rule is the same.
"""
from __future__ import annotations

import hashlib

RATE = 0.05
MINT = False
SOCKET = False
LAYER_ONE = False
FETCH = False
UE5_LAUNCH = False
BIND = "127.0.0.1"
PORTS = ("Home", "OSai", "FieldCore", "Flagstaff", "JuniorLLM")
GENESIS = "0" * 16
ENGINES = ("web3node", "JuniorLLM")

_ENC = {0: 0, 1: 1, -1: 2}
_DEC = {0: 0, 1: 1, 2: -1}

# Cross-engine vector: web3node side_commit_rate_lock.py gives these for trits [1,0,-1,-1,1,0,1].
_VEC_TRITS = (1, 0, -1, -1, 1, 0, 1)
_VEC_PACK = "4a44"
_VEC_COMMIT = "e038848e2422d22a"  # side_commit(GENESIS, pack, "stocks")


def price_trits(prices, dead_band: float = 0.0) -> list[int]:
    """Price series -> balanced trits by step return vs. dead band."""
    out = []
    for a, b in zip(prices, prices[1:]):
        r = (b - a) / a if a else 0.0
        out.append(1 if r > dead_band else (-1 if r < -dead_band else 0))
    return out


def pack(trits) -> bytes:
    """Balanced trits as 2-bit i2s codes, MSB first, zero-padded."""
    acc = bits = 0
    out = bytearray()
    for t in trits:
        if t not in _ENC:
            raise ValueError("trit must be -1, 0 or 1")
        acc = (acc << 2) | _ENC[t]
        bits += 2
        if bits == 8:
            out.append(acc)
            acc = bits = 0
    if bits:
        out.append(acc << (8 - bits))
    return bytes(out)


def unpack(data: bytes, n: int) -> list[int]:
    out = []
    for b in data:
        for s in (6, 4, 2, 0):
            out.append(_DEC[(b >> s) & 3])
    return out[:n]


def side_commit(prev: str, pk: bytes, text: str) -> str:
    """sha256(prev || pack || text)[:16]."""
    return hashlib.sha256(prev.encode() + pk + text.encode()).hexdigest()[:16]


def rate_lock(level: float, x: float) -> float:
    """Lock step: move level toward x at RATE (0.05)."""
    return level + RATE * (x - level)


def build_chain(windows, prev: str = GENESIS, dead_band: float = 0.0) -> list[dict]:
    """windows: iterable of (prices, ticker). Each link = sha256(prev || pack || text)[:16]."""
    out = []
    lock = 0.0
    for prices, text in windows:
        t = price_trits(prices, dead_band)
        c = side_commit(prev, pack(t), text)
        lock = rate_lock(lock, (sum(t) / len(t)) if t else 0.0)
        out.append({"prev": prev, "trits": t, "text": text, "commit": c, "lock": lock})
        prev = c
    return out


def verify_chain(chain, prev: str = GENESIS) -> dict:
    for i, link in enumerate(chain):
        if link["prev"] != prev:
            return {"ok": False, "at": i, "reason": "prev"}
        if side_commit(prev, pack(link["trits"]), link["text"]) != link["commit"]:
            return {"ok": False, "at": i, "reason": "commit"}
        prev = link["commit"]
    return {"ok": True, "n": len(chain), "tip": prev}


def self_check() -> dict:
    assert BIND == "127.0.0.1"
    assert PORTS == ("Home", "OSai", "FieldCore", "Flagstaff", "JuniorLLM")
    assert not (MINT or SOCKET or LAYER_ONE or FETCH or UE5_LAUNCH)
    assert abs(RATE - 0.05) < 1e-12 and abs(rate_lock(0.0, 1.0) - 0.05) < 1e-12
    p = pack(_VEC_TRITS)
    assert p.hex() == _VEC_PACK and unpack(p, len(_VEC_TRITS)) == list(_VEC_TRITS)
    assert side_commit(GENESIS, p, "stocks") == _VEC_COMMIT
    assert price_trits([100.0, 101.0, 101.0, 99.5, 100.2], 0.001) == [1, 0, -1, 1]
    ch = build_chain([([100.0, 101.0, 101.0, 99.5], "AAPL"), ([50.0, 49.0, 49.5], "MSFT")])
    v = verify_chain(ch)
    assert v["ok"] and v["n"] == 2
    bad = [dict(link) for link in ch]
    bad[1]["text"] = "XXXX"
    assert verify_chain(bad) == {"ok": False, "at": 1, "reason": "commit"}
    return {
        "ok": True,
        "rate": RATE,
        "close": "sha256(prev || pack || text)[:16]",
        "bind": BIND,
        "ports": list(PORTS),
        "engines": list(ENGINES),
        "tip": v["tip"],
    }


if __name__ == "__main__":
    print(self_check())
