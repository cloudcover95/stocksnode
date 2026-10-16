"""JuniorOS overlay receipt ledger — component receipts + side-commit + rate lock.

ROADMAP / BETA_TO_OS item: JuniorOS overlay (Debian/Alpine + os-release.junior
+ hardened bitnetd.service + juniorctl on PATH).
Advances live-beta receipt chains / backfill_check at rate 0.05.

Stdlib only. Close: sha256(prev || pack || text)[:16] with i2s 2-bit pack
(0->0, 1->1, -1->2), MSB first, zero-padded. Rate lock commits rate 0.05 beside
the pack as sha256(prev || pack || b"0.05") full hexdigest (JUNIORS_RATE.md).
"""
from __future__ import annotations

import hashlib
import sys
from typing import Any

RATE = 0.05
RATE_BYTES = b"0.05"
GENESIS = "0" * 16

MINT = False
SOCKET = False
LAYER_ONE = False
FETCH = False
UE5_LAUNCH = False
RELEASED = 0
BIND = "127.0.0.1"
PORTS = ("Home", "OSai", "FieldCore", "Flagstaff", "JuniorLLM")

# Named JuniorOS overlay component ids for receipt tagging
OVERLAY_COMPONENTS = (
    "os-release.junior",
    "bitnetd.service",
    "juniorctl.path",
)

COMPATIBLE_ENGINES = ("web3node", "stocksnode", "JuniorLLM", "BitNet-mlx")

_TRIT_TO_BITS = {0: 0, 1: 1, -1: 2}
_BITS_TO_TRIT = {0: 0, 1: 1, 2: -1}


def pack(trits: list[int]) -> bytes:
    """Pack trits to bytes: 2-bit i2s (0->0, 1->1, -1->2), MSB first, zero-padded."""
    bits = 0
    n = 0
    out = bytearray()
    for t in trits:
        bits = (bits << 2) | _TRIT_TO_BITS[t]
        n += 2
        while n >= 8:
            n -= 8
            out.append((bits >> n) & 0xFF)
            bits &= (1 << n) - 1 if n else 0
    if n:
        out.append((bits << (8 - n)) & 0xFF)
    return bytes(out)


def unpack(data: bytes, count: int | None = None) -> list[int]:
    """Unpack i2s 2-bit bytes back to trits. count limits trit count if given."""
    trits: list[int] = []
    for b in data:
        for shift in (6, 4, 2, 0):
            bits = (b >> shift) & 0x3
            if bits == 3:
                continue
            trits.append(_BITS_TO_TRIT[bits])
            if count is not None and len(trits) >= count:
                return trits
    if count is not None:
        return trits[:count]
    return trits


def side_commit(prev: str, pk: bytes, text: str) -> str:
    """Close rule: sha256(prev || pack || text)[:16]."""
    return hashlib.sha256(prev.encode() + pk + text.encode()).hexdigest()[:16]


def rate_lock_commit(prev: str, pk: bytes) -> str:
    """Rate lock: sha256(prev || pack || rate_bytes) full hexdigest (JUNIORS_RATE)."""
    return hashlib.sha256(prev.encode() + pk + RATE_BYTES).hexdigest()


def overlay_manifest() -> dict[str, Any]:
    """Static expected overlay bind + component list. No OS/network/file reads."""
    return {
        "bind": BIND,
        "components": list(OVERLAY_COMPONENTS),
        "ports": list(PORTS),
        "rate": RATE,
        "engines": list(COMPATIBLE_ENGINES),
    }


def append_overlay_receipt(
    ledger: list[dict[str, Any]],
    prev: str,
    trits: list[int],
    text: str,
    component: str,
) -> dict[str, Any]:
    """Append one overlay component receipt; stores component + side-commit + rate_commit."""
    if component not in OVERLAY_COMPONENTS:
        raise ValueError(f"unknown overlay component: {component!r}")
    pk = pack(trits)
    commit = side_commit(prev, pk, text)
    rate_commit = rate_lock_commit(prev, pk)
    link = {
        "prev": prev,
        "trits": list(trits),
        "text": text,
        "component": component,
        "commit": commit,
        "rate_commit": rate_commit,
    }
    ledger.append(link)
    return link


def verify_ledger(
    ledger: list[dict[str, Any]],
    prev: str = GENESIS,
) -> dict[str, Any]:
    """Verify contiguous overlay side-commit chain from prev/GENESIS."""
    cur = prev
    for i, link in enumerate(ledger):
        if link.get("prev") != cur:
            return {"ok": False, "at": i, "reason": "prev_mismatch"}
        comp = link.get("component")
        if comp not in OVERLAY_COMPONENTS:
            return {"ok": False, "at": i, "reason": "bad_component"}
        pk = pack(link["trits"])
        expected = side_commit(cur, pk, link["text"])
        if link.get("commit") != expected:
            return {"ok": False, "at": i, "reason": "commit_mismatch"}
        rc = rate_lock_commit(cur, pk)
        if link.get("rate_commit") != rc:
            return {"ok": False, "at": i, "reason": "rate_commit_mismatch"}
        cur = link["commit"]
    return {"ok": True, "tip": cur}


def backfill_check(
    ledger: list[dict[str, Any]],
    prev: str = GENESIS,
) -> dict[str, Any]:
    """Live-beta backfill gate: contiguous chain, gaps list at broken indices."""
    gaps: list[int] = []
    cur = prev
    tip = cur
    for i, link in enumerate(ledger):
        if link.get("prev") != cur:
            gaps.append(i)
            tip = link.get("commit", tip)
            cur = link.get("commit", cur)
            continue
        pk = pack(link["trits"])
        expected = side_commit(cur, pk, link["text"])
        if link.get("commit") != expected:
            gaps.append(i)
        rc = rate_lock_commit(cur, pk)
        if link.get("rate_commit") != rc and i not in gaps:
            gaps.append(i)
        tip = link["commit"]
        cur = link["commit"]
    return {"ok": len(gaps) == 0, "gaps": gaps, "tip": tip, "n": len(ledger)}


def self_check() -> dict[str, Any]:
    """Assert bind/ports/flags/rate, pack vector 4a44, ledger verify, backfill, rate lock."""
    assert BIND == "127.0.0.1"
    assert PORTS == ("Home", "OSai", "FieldCore", "Flagstaff", "JuniorLLM")
    assert MINT is False and SOCKET is False and LAYER_ONE is False
    assert FETCH is False and UE5_LAUNCH is False and RELEASED == 0
    assert RATE == 0.05 and RATE_BYTES == b"0.05"

    vec = pack([1, 0, -1, -1, 1, 0, 1])
    assert vec.hex() == "4a44", vec.hex()
    assert unpack(vec, 7) == [1, 0, -1, -1, 1, 0, 1]

    manifest = overlay_manifest()
    assert manifest["bind"] == "127.0.0.1"
    assert manifest["components"] == list(OVERLAY_COMPONENTS)
    assert "os-release.junior" in manifest["components"]
    assert "bitnetd.service" in manifest["components"]
    assert "juniorctl.path" in manifest["components"]

    ledger: list[dict[str, Any]] = []
    a = append_overlay_receipt(
        ledger, GENESIS, [1, 0, -1], "os-release.junior present", "os-release.junior"
    )
    b = append_overlay_receipt(
        ledger, a["commit"], [0, 1, 1], "hardened unit", "bitnetd.service"
    )
    c = append_overlay_receipt(
        ledger, b["commit"], [1, -1, 0], "juniorctl on PATH", "juniorctl.path"
    )
    v = verify_ledger(ledger)
    assert v["ok"] is True and v["tip"] == c["commit"]

    tampered = [dict(x) for x in ledger]
    tampered[1]["text"] = "TAMPER"
    assert verify_ledger(tampered)["ok"] is False

    bf = backfill_check(ledger)
    assert bf["ok"] is True and bf["gaps"] == [] and bf["n"] == 3

    gapped = [dict(x) for x in ledger]
    gapped[1]["prev"] = "deadbeefdeadbeef"
    bf2 = backfill_check(gapped)
    assert bf2["ok"] is False and 1 in bf2["gaps"]

    pk = pack([1, 0, -1])
    r1 = rate_lock_commit(GENESIS, pk)
    r2 = rate_lock_commit(GENESIS, pk)
    assert r1 == r2 and len(r1) == 64

    return {
        "ok": True,
        "bind": BIND,
        "ports": list(PORTS),
        "rate": RATE,
        "pack_vector": vec.hex(),
        "engines": list(COMPATIBLE_ENGINES),
        "components": list(OVERLAY_COMPONENTS),
        "tip": v["tip"],
        "backfill_ok": bf["ok"],
    }


if __name__ == "__main__":
    try:
        result = self_check()
        print(result)
        sys.exit(0)
    except AssertionError as e:
        print({"ok": False, "error": str(e) or "assertion failed"})
        sys.exit(1)
    except Exception as e:
        print({"ok": False, "error": repr(e)})
        sys.exit(1)
