"""Deck sheet receipt ledger: per-claim receipts + side-commit + rate lock.

Roadmap item: JuniorLLM docs/BETA_TO_OS.md, item "Deck sheet" ("Deck
controls and Gaia helper stay separate. Package ports: JuniorLLM, AGI_SDK,
JuniorOSai, JuniorOS, web3node, obsidian. Vault not synced. Device not
opened." Schematic: JuniorHome docs/deck_capability.svg). This is the item
Quant Chief assigned pair B on 2026-10-17 10:11 MT.

New capability: a receipt chain for one Deck sheet attestation. The operator
passes in what they observed (identity labels, which package ports are
present and whether any is synced, vault sync, device opened, flashed,
live, admit, and the deck bind). This module never opens the device, never
flashes, never syncs the vault, never imports any other team file, and
opens no sockets. Each claim becomes one chained receipt:

  * identity  - "Deck controls" and "Gaia helper" are distinct, clone_of none
  * package   - one receipt per package port, present and synced False
  * vault     - vault synced False
  * device    - device opened False, flashed False, live False, admit False
  * bind      - deck bind exactly 127.0.0.1:8766 (0.0.0.0 refused)

sheet_verdict() says whether the sheet holds, which ports are missing, and
which claims broke. backfill_check() walks the chain and lists gaps, sync
leaks, device leaks, identity merges, and bind leaks.

Receipts chain with the close rule sha256(prev || pack || text)[:16]
(i2s 2-bit pack 0->0, 1->1, -1->2, MSB first, zero-padded) and lock rate
0.05 beside the pack as sha256(prev || pack || b"0.05") per JuniorHome
docs/JUNIORS_RATE.md. released 0, layer_one False.

Ports: Home, OSai, FieldCore, Flagstaff, JuniorLLM. Bind 127.0.0.1 only.
mint/socket/layer_one/fetch/ue5_launch False.

Run: python3 deck_sheet_receipt_ledger.py --selftest
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
DECK_BIND = "127.0.0.1:8766"
PORTS = ("Home", "OSai", "FieldCore", "Flagstaff", "JuniorLLM")
COMPATIBLE_ENGINES = ("web3node", "stocksnode", "JuniorLLM", "BitNet-mlx")

# Deck sheet facts, as written in BETA_TO_OS.md and deck_capability.svg.
IDENTITIES = ("Deck controls", "Gaia helper")
PACKAGE_PORTS = ("JuniorLLM", "AGI_SDK", "JuniorOSai", "JuniorOS", "web3node", "obsidian")
SCHEMATIC = "JuniorHome docs/deck_capability.svg"

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


def _yn(b: bool) -> int:
    return 1 if b else -1


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


def append_identity(
    ledger: list[dict[str, Any]], controls: str, helper: str, clone_of: str | None
) -> dict[str, Any]:
    """Deck controls and Gaia helper stay separate; neither is a clone."""
    named = controls == IDENTITIES[0] and helper == IDENTITIES[1]
    separate = controls.strip().lower() != helper.strip().lower()
    no_clone = clone_of in (None, "", "none")
    body = {
        "kind": "identity",
        "controls": controls,
        "helper": helper,
        "clone_of": "none" if no_clone else clone_of,
        "named": named,
        "separate": separate,
        "status": "pass" if (named and separate and no_clone) else "fail",
    }
    return _link(ledger, body, [_yn(named), _yn(separate), _yn(no_clone)])


def append_package(
    ledger: list[dict[str, Any]], port: str, present: bool, synced: bool
) -> dict[str, Any]:
    """One package port: listed on the sheet, present, and not synced."""
    if port not in PACKAGE_PORTS:
        raise ValueError(f"not a Deck sheet package port: {port}")
    body = {
        "kind": "package",
        "port": port,
        "present": bool(present),
        "synced": bool(synced),
        "status": "pass" if (present and not synced) else "fail",
    }
    return _link(ledger, body, [_yn(bool(present)), _yn(not synced)])


def append_vault(ledger: list[dict[str, Any]], synced: bool) -> dict[str, Any]:
    """Vault not synced."""
    body = {"kind": "vault", "synced": bool(synced), "status": "fail" if synced else "pass"}
    return _link(ledger, body, [_yn(not synced)])


def append_device(
    ledger: list[dict[str, Any]], opened: bool, flashed: bool, live: bool, admit: bool
) -> dict[str, Any]:
    """Device not opened, not flashed, not live, not admitted."""
    flags = {"opened": bool(opened), "flashed": bool(flashed), "live": bool(live), "admit": bool(admit)}
    body = dict(flags, kind="device", status="fail" if any(flags.values()) else "pass")
    return _link(ledger, body, [_yn(not v) for v in flags.values()])


def append_bind(ledger: list[dict[str, Any]], bind: str) -> dict[str, Any]:
    """Deck bind is exactly 127.0.0.1:8766; 0.0.0.0 or anything else fails."""
    ok = bind == DECK_BIND
    body = {"kind": "bind", "bind": bind, "expected": DECK_BIND, "status": "pass" if ok else "fail"}
    return _link(ledger, body, [_yn(ok), 0 if ok else -1])


def backfill_check(ledger: list[dict[str, Any]], prev: str = GENESIS) -> dict[str, Any]:
    """Walk the chain; report gaps and every kind of Deck sheet leak."""
    gaps: list[int] = []
    sync_leaks: list[int] = []
    device_leaks: list[int] = []
    identity_merges: list[int] = []
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
        k = b.get("kind")
        if k in ("package", "vault") and b.get("synced"):
            sync_leaks.append(i)
        elif k == "device" and any(b.get(f) for f in ("opened", "flashed", "live", "admit")):
            device_leaks.append(i)
        elif k == "identity" and (not b.get("separate") or b.get("clone_of") != "none"):
            identity_merges.append(i)
        elif k == "bind" and b.get("bind") != DECK_BIND:
            bind_leaks.append(i)
        cur = link.get("commit", cur)
    return {
        "ok": not (gaps or sync_leaks or device_leaks or identity_merges or bind_leaks),
        "gaps": gaps,
        "sync_leaks": sync_leaks,
        "device_leaks": device_leaks,
        "identity_merges": identity_merges,
        "bind_leaks": bind_leaks,
        "tip": cur,
        "n": len(ledger),
    }


def sheet_verdict(ledger: list[dict[str, Any]]) -> dict[str, Any]:
    """Whole-sheet verdict: every claim recorded and passing, chain intact."""
    kinds: dict[str, str] = {}
    ports: dict[str, str] = {}
    for link in ledger:
        b = link["body"]
        if b["kind"] == "package":
            ports[b["port"]] = b["status"]
        else:
            prior = kinds.get(b["kind"])
            kinds[b["kind"]] = "fail" if prior == "fail" else b["status"]
    missing_ports = [p for p in PACKAGE_PORTS if p not in ports]
    failed_ports = [p for p in PACKAGE_PORTS if ports.get(p) == "fail"]
    claims = ("identity", "vault", "device", "bind")
    missing = [c for c in claims if c not in kinds]
    failed = [c for c in claims if kinds.get(c) == "fail"]
    bf = backfill_check(ledger)
    holds = not (missing_ports or failed_ports or missing or failed) and bf["ok"]
    return {
        "deck_sheet_holds": holds,
        "missing_ports": missing_ports,
        "failed_ports": failed_ports,
        "missing_claims": missing,
        "failed_claims": failed,
        "chain_ok": bf["ok"],
        "tip": bf["tip"],
        "rate": RATE,
        "schematic": SCHEMATIC,
    }


def _good_sheet() -> list[dict[str, Any]]:
    ledger: list[dict[str, Any]] = []
    append_identity(ledger, "Deck controls", "Gaia helper", None)
    for p in PACKAGE_PORTS:
        append_package(ledger, p, True, False)
    append_vault(ledger, False)
    append_device(ledger, False, False, False, False)
    append_bind(ledger, DECK_BIND)
    return ledger


def selftest() -> dict[str, Any]:
    assert BIND == "127.0.0.1" and DECK_BIND.startswith("127.0.0.1:")
    assert PORTS == ("Home", "OSai", "FieldCore", "Flagstaff", "JuniorLLM")
    assert not (MINT or SOCKET or LAYER_ONE or FETCH or UE5_LAUNCH)
    assert RELEASED == 0 and RATE == 0.05

    vec = pack([1, 0, -1, -1, 1, 0, 1])
    assert vec.hex() == "4a44", vec.hex()
    known = side_commit(GENESIS, vec, "home")
    assert known == "dd07dea74a142604", known

    ledger = _good_sheet()
    v = sheet_verdict(ledger)
    assert v["deck_sheet_holds"], v
    bf = backfill_check(ledger)
    assert bf["ok"] and bf["n"] == len(PACKAGE_PORTS) + 4 and bf["tip"] == ledger[-1]["commit"]

    # Missing port and missing claims are reported, not guessed.
    part: list[dict[str, Any]] = []
    append_identity(part, "Deck controls", "Gaia helper", "none")
    append_package(part, "JuniorLLM", True, False)
    pv = sheet_verdict(part)
    assert not pv["deck_sheet_holds"]
    assert "obsidian" in pv["missing_ports"] and pv["missing_claims"] == ["vault", "device", "bind"]

    # Each leak kind lands in its own list.
    bad: list[dict[str, Any]] = []
    append_identity(bad, "Deck controls", "deck controls", "Gaia helper")
    append_package(bad, "obsidian", True, True)
    append_vault(bad, True)
    append_device(bad, True, False, False, False)
    append_bind(bad, "0.0.0.0:8766")
    bb = backfill_check(bad)
    assert bb["gaps"] == [] and bb["identity_merges"] == [0] and bb["sync_leaks"] == [1, 2]
    assert bb["device_leaks"] == [3] and bb["bind_leaks"] == [4] and not bb["ok"]
    bv = sheet_verdict(bad)
    assert bv["failed_claims"] == ["identity", "vault", "device", "bind"]
    assert bv["failed_ports"] == ["obsidian"]

    try:
        append_package([], "JuniorSolana", True, False)
        raise AssertionError("unknown package port accepted")
    except ValueError:
        pass

    # Tampering with text, rate lock, or body breaks the chain.
    t = [dict(x) for x in ledger]
    t[1] = dict(t[1], text=t[1]["text"].replace('"synced":false', '"synced":true'))
    assert 1 in backfill_check(t)["gaps"]
    r = [dict(x) for x in ledger]
    r[0] = dict(r[0], rate_commit=hashlib.sha256(b"x").hexdigest())
    assert 0 in backfill_check(r)["gaps"]
    d = [dict(x) for x in ledger]
    d[-2] = dict(d[-2], body=dict(d[-2]["body"], opened=True))
    db = backfill_check(d)
    assert (len(d) - 2) in db["gaps"] and db["device_leaks"] == [len(d) - 2]
    assert not sheet_verdict(d)["deck_sheet_holds"]

    return {
        "ok": True,
        "bind": BIND,
        "deck_bind": DECK_BIND,
        "ports": list(PORTS),
        "package_ports": list(PACKAGE_PORTS),
        "rate": RATE,
        "pack_vector": vec.hex(),
        "close_home_4a44": known,
        "engines": list(COMPATIBLE_ENGINES),
        "receipts": bf["n"],
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
    print(json.dumps({"package_ports": list(PACKAGE_PORTS), "identities": list(IDENTITIES), "rate": RATE, "bind": BIND}))
