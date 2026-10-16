"""UE5 launch gate receipt ledger: offline gate-state receipts + side-commit + rate lock.

ROADMAP item: JuniorHome docs/ROADMAP.md #5 "UE5 launched" (JUNIOR_UE5=1 and
watts>=80, default FrameForge2D, os_route.launch false until then), the item
Quant Chief assigned pair B on 2026-10-16 14:15 MT.

New capability: each receipt records one observed gate state (env flag and a
caller-supplied watts reading) and whether the gate condition would be met.
It never launches UE5: ue5_launch and os_route.launch are always False here,
even when the gate condition reads true. No hardware calls, no downloads, no
sockets. The env flag is read only when the caller asks (from_env=True).

Live beta: receipts chain with the close rule sha256(prev || pack || text)[:16]
(i2s 2-bit pack 0->0, 1->1, -1->2, MSB first, zero-padded) and lock rate 0.05
beside the pack as sha256(prev || pack || b"0.05") per JuniorHome
docs/JUNIORS_RATE.md. backfill_check lists broken indices.

Ports: Home, OSai, FieldCore, Flagstaff, JuniorLLM. Bind 127.0.0.1 only.
mint/socket/layer_one/fetch/ue5_launch False, released 0.

Run: python3 ue5_gate_receipt_ledger.py --selftest
"""
from __future__ import annotations

import hashlib
import json
import os
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
OS_ROUTE_LAUNCH = False
RELEASED = 0
BIND = "127.0.0.1"
PORTS = ("Home", "OSai", "FieldCore", "Flagstaff", "JuniorLLM")
COMPATIBLE_ENGINES = ("web3node", "stocksnode", "JuniorLLM", "BitNet-mlx")

GATE_ENV = "JUNIOR_UE5"
GATE_WATTS_MIN = 80.0
DEFAULT_RENDERER = "FrameForge2D"

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


def gate_state(env_flag: str | None, watts: float) -> dict[str, Any]:
    """Pure gate evaluation. Never launches; launch fields stay False."""
    env_on = env_flag == "1"
    watts_ok = float(watts) >= GATE_WATTS_MIN
    return {
        "env": GATE_ENV,
        "env_on": env_on,
        "watts": float(watts),
        "watts_min": GATE_WATTS_MIN,
        "watts_ok": watts_ok,
        "gate_met": env_on and watts_ok,
        "renderer": DEFAULT_RENDERER,
        "ue5_launch": UE5_LAUNCH,
        "os_route_launch": OS_ROUTE_LAUNCH,
    }


def gate_trits(state: dict[str, Any]) -> list[int]:
    """Encode gate state as trits: +1 yes, -1 no, 0 for the launch slots (held)."""
    yn = lambda b: 1 if b else -1  # noqa: E731
    return [yn(state["env_on"]), yn(state["watts_ok"]), yn(state["gate_met"]), 0, 0]


def gate_text(state: dict[str, Any]) -> str:
    """Canonical receipt text for a gate state."""
    return json.dumps(
        {k: state[k] for k in sorted(state)}, sort_keys=True, separators=(",", ":")
    )


def append_gate_receipt(
    ledger: list[dict[str, Any]],
    watts: float,
    env_flag: str | None = None,
    from_env: bool = False,
) -> dict[str, Any]:
    """Append one gate-state receipt chained to the ledger tip."""
    if from_env:
        env_flag = os.environ.get(GATE_ENV)
    state = gate_state(env_flag, watts)
    prev = ledger[-1]["commit"] if ledger else GENESIS
    trits = gate_trits(state)
    text = gate_text(state)
    pk = pack(trits)
    link = {
        "prev": prev,
        "trits": trits,
        "text": text,
        "state": state,
        "rate": RATE,
        "commit": side_commit(prev, pk, text),
        "rate_commit": rate_lock(prev, pk),
    }
    ledger.append(link)
    return link


def backfill_check(ledger: list[dict[str, Any]], prev: str = GENESIS) -> dict[str, Any]:
    """Walk the chain; report gaps, rate-lock breaks, and any launch=True leak."""
    gaps: list[int] = []
    launch_leaks: list[int] = []
    cur = prev
    for i, link in enumerate(ledger):
        pk = pack(link["trits"])
        bad = (
            link.get("prev") != cur
            or link.get("commit") != side_commit(cur, pk, link["text"])
            or link.get("rate_commit") != rate_lock(cur, pk)
            or link.get("rate") != RATE
        )
        if bad:
            gaps.append(i)
        st = link.get("state", {})
        if st.get("ue5_launch") is not False or st.get("os_route_launch") is not False:
            launch_leaks.append(i)
        cur = link.get("commit", cur)
    return {
        "ok": not gaps and not launch_leaks,
        "gaps": gaps,
        "launch_leaks": launch_leaks,
        "tip": cur,
        "n": len(ledger),
    }


def selftest() -> dict[str, Any]:
    assert BIND == "127.0.0.1"
    assert PORTS == ("Home", "OSai", "FieldCore", "Flagstaff", "JuniorLLM")
    assert not (MINT or SOCKET or LAYER_ONE or FETCH or UE5_LAUNCH or OS_ROUTE_LAUNCH)
    assert RELEASED == 0 and RATE == 0.05

    vec = pack([1, 0, -1, -1, 1, 0, 1])
    assert vec.hex() == "4a44", vec.hex()
    known = side_commit(GENESIS, vec, "home")
    assert len(known) == 16

    ledger: list[dict[str, Any]] = []
    a = append_gate_receipt(ledger, 40.0, env_flag=None)
    b = append_gate_receipt(ledger, 95.0, env_flag="0")
    c = append_gate_receipt(ledger, 95.0, env_flag="1")
    assert a["state"]["gate_met"] is False
    assert b["state"]["gate_met"] is False
    assert c["state"]["gate_met"] is True
    for link in ledger:
        assert link["state"]["ue5_launch"] is False
        assert link["state"]["os_route_launch"] is False
        assert link["state"]["renderer"] == "FrameForge2D"
    assert append_gate_receipt([], 80.0, "1")["state"]["watts_ok"] is True
    assert append_gate_receipt([], 79.9, "1")["state"]["watts_ok"] is False

    bf = backfill_check(ledger)
    assert bf["ok"] and bf["gaps"] == [] and bf["n"] == 3 and bf["tip"] == c["commit"]

    t = [dict(x) for x in ledger]
    t[1] = dict(t[1], text=t[1]["text"].replace("95.0", "99.0"))
    assert 1 in backfill_check(t)["gaps"]

    r = [dict(x) for x in ledger]
    r[0] = dict(r[0], rate_commit=hashlib.sha256(b"x").hexdigest())
    assert 0 in backfill_check(r)["gaps"]

    leak = [dict(x) for x in ledger]
    leak[2] = dict(leak[2], state=dict(leak[2]["state"], ue5_launch=True))
    assert backfill_check(leak)["launch_leaks"] == [2]

    return {
        "ok": True,
        "bind": BIND,
        "ports": list(PORTS),
        "rate": RATE,
        "pack_vector": vec.hex(),
        "close_home_4a44": known,
        "engines": list(COMPATIBLE_ENGINES),
        "tip": bf["tip"],
        "ue5_launch": UE5_LAUNCH,
    }


if __name__ == "__main__":
    if "--selftest" in sys.argv[1:]:
        try:
            print(json.dumps(selftest()))
            sys.exit(0)
        except AssertionError as e:
            print(json.dumps({"ok": False, "error": str(e) or "assertion failed"}))
            sys.exit(1)
    print(json.dumps(gate_state(os.environ.get(GATE_ENV), 0.0)))
