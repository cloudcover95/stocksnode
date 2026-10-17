"""Live beta run receipt ledger: per-step outcome receipts + side-commit + rate lock.

Roadmap item: JuniorLLM docs/BETA_TO_OS.md, item "Live beta" (fresh clone:
1. juniorctl health, 2. juniorctl ask / night / security, 3. test_junior_aie
and test_linux_security, 4. stonefield stdlib probe, 5. backfill_check exits
0, 6. no deletes, no >8GB pull, bitnetd on 127.0.0.1:8765 only). This is the
item Quant Chief assigned pair B on 2026-10-17 02:08 MT.

New capability: a receipt chain for one live-beta run. The operator (or a
runner they own) passes in the exit code each step produced; this module
never runs juniorctl, the tests, the probe, or backfill_check itself, never
imports them, and opens no sockets. Each step becomes one chained receipt.
A final guard receipt records step 6: deletes == 0, pulled bytes <= 8 GB,
and bitnetd bind exactly 127.0.0.1:8765 (0.0.0.0 is refused). verdict()
says whether the whole run passed, which steps are missing, and which failed.

Receipts chain with the close rule sha256(prev || pack || text)[:16]
(i2s 2-bit pack 0->0, 1->1, -1->2, MSB first, zero-padded) and lock rate
0.05 beside the pack as sha256(prev || pack || b"0.05") per JuniorHome
docs/JUNIORS_RATE.md. backfill_check lists broken indices and bind leaks.

Ports: Home, OSai, FieldCore, Flagstaff, JuniorLLM. Bind 127.0.0.1 only.
mint/socket/layer_one/fetch/ue5_launch False, released 0.

Run: python3 live_beta_receipt_ledger.py --selftest
"""
from __future__ import annotations

import hashlib
import json
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
BITNETD_BIND = "127.0.0.1:8765"
MAX_PULL_BYTES = 8 * 1024 ** 3
PORTS = ("Home", "OSai", "FieldCore", "Flagstaff", "JuniorLLM")
COMPATIBLE_ENGINES = ("web3node", "stocksnode", "JuniorLLM", "BitNet-mlx")

# Live beta steps in BETA_TO_OS.md order; (step number, name).
STEPS: tuple[tuple[int, str], ...] = (
    (1, "juniorctl_health"),
    (2, "juniorctl_ask"),
    (2, "juniorctl_night"),
    (2, "juniorctl_security"),
    (3, "test_junior_aie"),
    (3, "test_linux_security"),
    (4, "stonefield_stdlib_probe"),
    (5, "backfill_check"),
)
STEP_NAMES = tuple(n for _, n in STEPS)
GUARD = "guard_step6"

_TRIT_TO_BITS = {0: 0, 1: 1, -1: 2}


def pack(trits: list[int]) -> bytes:
    """i2s 2-bit pack (0->0, 1->1, -1->2), MSB first, zero-padded."""
    out = bytearray()
    acc = 0
    n = 0
    for t in trits:
        acc = (acc << 2) | _TRIT_TO_BITS[t]
        n += 1
        if n == 4:
            out.append(acc)
            acc, n = 0, 0
    if n:
        out.append(acc << (2 * (4 - n)))
    return bytes(out)


def side_commit(prev: str, pk: bytes, text: str) -> str:
    """Close rule: sha256(prev || pack || text)[:16]."""
    return hashlib.sha256(prev.encode() + pk + text.encode()).hexdigest()[:16]


def rate_lock(prev: str, pk: bytes) -> str:
    """Rate committed beside the pack: sha256(prev || pack || b"0.05")."""
    return hashlib.sha256(prev.encode() + pk + RATE_BYTES).hexdigest()


def _canon(obj: dict[str, Any]) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def _link(ledger: list[dict[str, Any]], body: dict[str, Any], trits: list[int]) -> dict[str, Any]:
    prev = ledger[-1]["commit"] if ledger else GENESIS
    text = _canon(body)
    pk = pack(trits)
    link = {
        "prev": prev,
        "trits": trits,
        "text": text,
        "body": body,
        "rate": RATE,
        "commit": side_commit(prev, pk, text),
        "rate_commit": rate_lock(prev, pk),
    }
    ledger.append(link)
    return link


def append_step(ledger: list[dict[str, Any]], name: str, exit_code: int | None) -> dict[str, Any]:
    """Record one live-beta step outcome. exit_code None means not run (trit 0)."""
    if name not in STEP_NAMES:
        raise ValueError(f"unknown live beta step: {name}")
    step = dict((n, s) for s, n in STEPS)[name]
    if exit_code is None:
        status, t = "not_run", 0
    elif int(exit_code) == 0:
        status, t = "pass", 1
    else:
        status, t = "fail", -1
    body = {
        "kind": "step",
        "step": step,
        "name": name,
        "exit_code": None if exit_code is None else int(exit_code),
        "status": status,
    }
    return _link(ledger, body, [t, 1 if step % 2 else -1])


def append_guard(
    ledger: list[dict[str, Any]], deletes: int, pulled_bytes: int, bitnetd_bind: str
) -> dict[str, Any]:
    """Record step 6: no deletes, no >8GB pull, bitnetd on 127.0.0.1:8765 only."""
    no_del = int(deletes) == 0
    pull_ok = 0 <= int(pulled_bytes) <= MAX_PULL_BYTES
    bind_ok = bitnetd_bind == BITNETD_BIND
    yn = lambda b: 1 if b else -1  # noqa: E731
    body = {
        "kind": "guard",
        "step": 6,
        "name": GUARD,
        "deletes": int(deletes),
        "pulled_bytes": int(pulled_bytes),
        "max_pull_bytes": MAX_PULL_BYTES,
        "bitnetd_bind": bitnetd_bind,
        "no_deletes": no_del,
        "pull_ok": pull_ok,
        "bind_ok": bind_ok,
        "status": "pass" if (no_del and pull_ok and bind_ok) else "fail",
    }
    return _link(ledger, body, [yn(no_del), yn(pull_ok), yn(bind_ok)])


def backfill_check(ledger: list[dict[str, Any]], prev: str = GENESIS) -> dict[str, Any]:
    """Walk the chain; report gaps, rate-lock breaks, and non-loopback bind leaks."""
    gaps: list[int] = []
    bind_leaks: list[int] = []
    cur = prev
    for i, link in enumerate(ledger):
        pk = pack(link["trits"])
        bad = (
            link.get("prev") != cur
            or link.get("commit") != side_commit(cur, pk, link["text"])
            or link.get("rate_commit") != rate_lock(cur, pk)
            or link.get("rate") != RATE
            or _canon(link.get("body", {})) != link["text"]
        )
        if bad:
            gaps.append(i)
        b = link.get("body", {})
        if b.get("kind") == "guard" and b.get("bitnetd_bind") != BITNETD_BIND:
            bind_leaks.append(i)
        cur = link.get("commit", cur)
    return {
        "ok": not gaps and not bind_leaks,
        "gaps": gaps,
        "bind_leaks": bind_leaks,
        "tip": cur,
        "n": len(ledger),
    }


def verdict(ledger: list[dict[str, Any]]) -> dict[str, Any]:
    """Whole-run verdict: every step passed, guard passed, chain intact."""
    seen: dict[str, str] = {}
    guard = None
    for link in ledger:
        b = link["body"]
        if b["kind"] == "step":
            seen[b["name"]] = b["status"]
        elif b["kind"] == "guard":
            guard = b["status"]
    missing = [n for n in STEP_NAMES if seen.get(n, "not_run") == "not_run"]
    failed = [n for n in STEP_NAMES if seen.get(n) == "fail"]
    bf = backfill_check(ledger)
    live = not missing and not failed and guard == "pass" and bf["ok"]
    return {
        "live_beta_pass": live,
        "missing": missing,
        "failed": failed,
        "guard": guard or "not_run",
        "chain_ok": bf["ok"],
        "tip": bf["tip"],
        "rate": RATE,
    }


def selftest() -> dict[str, Any]:
    assert BIND == "127.0.0.1" and BITNETD_BIND.startswith("127.0.0.1:")
    assert PORTS == ("Home", "OSai", "FieldCore", "Flagstaff", "JuniorLLM")
    assert not (MINT or SOCKET or LAYER_ONE or FETCH or UE5_LAUNCH)
    assert RELEASED == 0 and RATE == 0.05

    vec = pack([1, 0, -1, -1, 1, 0, 1])
    assert vec.hex() == "4a44", vec.hex()
    known = side_commit(GENESIS, vec, "home")
    assert len(known) == 16

    ledger: list[dict[str, Any]] = []
    for n in STEP_NAMES:
        append_step(ledger, n, 0)
    append_guard(ledger, 0, 3 * 1024 ** 3, "127.0.0.1:8765")
    v = verdict(ledger)
    assert v["live_beta_pass"] and v["missing"] == [] and v["failed"] == [], v
    bf = backfill_check(ledger)
    assert bf["ok"] and bf["n"] == len(STEP_NAMES) + 1 and bf["tip"] == ledger[-1]["commit"]

    part: list[dict[str, Any]] = []
    append_step(part, "juniorctl_health", 0)
    append_step(part, "test_linux_security", 1)
    append_step(part, "backfill_check", None)
    pv = verdict(part)
    assert not pv["live_beta_pass"]
    assert pv["failed"] == ["test_linux_security"]
    assert "backfill_check" in pv["missing"] and "juniorctl_ask" in pv["missing"]
    assert pv["guard"] == "not_run"

    g: list[dict[str, Any]] = []
    assert append_guard(g, 1, 0, BITNETD_BIND)["body"]["status"] == "fail"
    assert append_guard(g, 0, MAX_PULL_BYTES + 1, BITNETD_BIND)["body"]["status"] == "fail"
    assert append_guard(g, 0, MAX_PULL_BYTES, BITNETD_BIND)["body"]["status"] == "pass"
    leak = append_guard(g, 0, 0, "0.0.0.0:8765")
    assert leak["body"]["bind_ok"] is False
    assert backfill_check(g)["bind_leaks"] == [3]

    try:
        append_step([], "rm_rf", 0)
        raise AssertionError("unknown step accepted")
    except ValueError:
        pass

    t = [dict(x) for x in ledger]
    t[2] = dict(t[2], text=t[2]["text"].replace('"pass"', '"fail"'))
    assert 2 in backfill_check(t)["gaps"]

    r = [dict(x) for x in ledger]
    r[0] = dict(r[0], rate_commit=hashlib.sha256(b"x").hexdigest())
    assert 0 in backfill_check(r)["gaps"]

    b = [dict(x) for x in ledger]
    b[-1] = dict(b[-1], body=dict(b[-1]["body"], bitnetd_bind="0.0.0.0:8765"))
    bb = backfill_check(b)
    assert (len(b) - 1) in bb["gaps"] and bb["bind_leaks"] == [len(b) - 1]
    assert not verdict(b)["live_beta_pass"]

    return {
        "ok": True,
        "bind": BIND,
        "bitnetd": BITNETD_BIND,
        "ports": list(PORTS),
        "rate": RATE,
        "pack_vector": vec.hex(),
        "close_home_4a44": known,
        "engines": list(COMPATIBLE_ENGINES),
        "steps": len(STEP_NAMES),
        "tip": bf["tip"],
    }


if __name__ == "__main__":
    if "--selftest" in sys.argv[1:]:
        try:
            print(json.dumps(selftest()))
            sys.exit(0)
        except AssertionError as e:
            print(json.dumps({"ok": False, "error": str(e) or "assertion failed"}))
            sys.exit(1)
    print(json.dumps({"steps": list(STEP_NAMES), "guard": GUARD, "rate": RATE, "bind": BIND}))
