"""Price-trit side-commit chain + rate-weighted signal next to trit_side_commit.py. Pure math."""
from __future__ import annotations

try:
    from .trit_side_commit import LAYER_ONE, MINT, RATE, SOCKET, pack, price_trits, side_commit
except ImportError:
    from trit_side_commit import LAYER_ONE, MINT, RATE, SOCKET, pack, price_trits, side_commit

GENESIS = "0" * 16


def build_chain(windows, prev: str = GENESIS, dead_band: float = 0.0) -> list[dict]:
    """windows: iterable of (prices, ticker). Each link = sha256(prev || pack || text)[:16]."""
    out = []
    for prices, text in windows:
        t = price_trits(prices, dead_band)
        c = side_commit(prev, pack(t), text)
        out.append({"prev": prev, "trits": t, "text": text, "commit": c})
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


def rate_signal(trits, s0: float = 0.0) -> float:
    """EMA-style accumulator: s <- (1 - RATE) * s + RATE * t."""
    s = s0
    for t in trits:
        s = (1.0 - RATE) * s + RATE * t
    return s


if __name__ == "__main__":
    ch = build_chain([([100.0, 101.0, 100.5], "AAA"), ([50.0, 50.0, 51.0], "BBB")], dead_band=0.001)
    v = verify_chain(ch)
    assert v["ok"] and v["n"] == 2
    bad = [dict(link) for link in ch]
    bad[0]["trits"] = [0, 0]
    assert verify_chain(bad) == {"ok": False, "at": 0, "reason": "commit"}
    assert abs(rate_signal([1]) - 0.05) < 1e-12
    assert abs(rate_signal([1, 1]) - (0.05 * 0.95 + 0.05)) < 1e-12
    assert not (MINT or SOCKET or LAYER_ONE)
    print({"tip": v["tip"], "signal": rate_signal(ch[0]["trits"] + ch[1]["trits"]), "ok": True})
