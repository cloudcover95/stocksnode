"""os-release.junior receipt ledger: field-level receipts + side-commit + rate lock.

ROADMAP item: JuniorLLM docs/BETA_TO_OS.md "JuniorOS overlay", os-release.junior
part only (Debian/Alpine + os-release.junior + hardened bitnetd.service +
juniorctl on PATH). The hardened bitnetd.service part shipped earlier as
web3node bitnetd_unit_hardening_receipt.py; juniorctl on PATH is a later run.
Pair B receipt and ledger piece; the matching handshake/port check belongs to
Handshake & Ports. This file is a new capability: it never imports, wraps,
tests, rewrites, or re-derives any team file (including stocksnode
junioros_overlay_receipt_ledger.py, JuniorLLM rails/linux/install-overlay.sh,
ports/junioros.py, or tests/test_linux_overlay.py).
Advances live-beta receipt chains / backfill_check at rate 0.05.

What it records: one receipt per os-release.junior snapshot. The caller hands in
the text (and, optionally, the text of the second install copy so the
/etc and /usr/lib copies can be compared). It parses freedesktop os-release
KEY=VALUE lines and scores 10 trits: ID=junioros, ID_LIKE names debian and
alpine, VARIANT_ID=overlay, NAME present, JUNIOR_BITNETD=127.0.0.1:8765,
JUNIOR_OFFLINE=1, JUNIOR_CHARTER=docs/BETA_TO_OS.md, syntax clean, the two
install copies match (0 when only one copy is given), and a guard trit (no
0.0.0.0, no kernel-blob or OSWorld-score claim). Offline: reads only the
strings it is given (or, from the CLI, at most 4096 bytes of one local file the
operator names). No subprocess, no network, no sockets, no model pull, no UE5.

Stdlib only. Close: sha256(prev || pack || text)[:16] with i2s 2-bit pack
(0->0, 1->1, -1->2), MSB first, zero-padded (pack vector 4a44). Rate lock
commits rate 0.05 beside the pack as sha256(prev || pack || b"0.05") full
hexdigest (JuniorHome docs/JUNIORS_RATE.md).

Ports touched: Home, OSai, FieldCore, Flagstaff, JuniorLLM. Bind 127.0.0.1.

Run: python3 os_release_junior_receipt_ledger.py --selftest
     python3 os_release_junior_receipt_ledger.py --file /opt/junioros/etc/os-release.junior
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from typing import Any

RATE = 0.05
RATE_BYTES = b"0.05"
GENESIS = "0" * 16
ROADMAP_ITEM = "JuniorLLM docs/BETA_TO_OS.md JuniorOS overlay - os-release.junior part"
MAX_READ = 4096

MINT = False
SOCKET = False
LAYER_ONE = False
FETCH = False
UE5_LAUNCH = False
MODEL_PULL = False
RELEASED = 0
BIND = "127.0.0.1"
BITNETD = "127.0.0.1:8765"
PORTS = ("Home", "OSai", "FieldCore", "Flagstaff", "JuniorLLM")
COMPATIBLE_ENGINES = ("web3node", "stocksnode", "JuniorLLM", "BitNet-mlx")

FIELD_KEYS = ("ID", "ID_LIKE", "VARIANT_ID", "NAME", "JUNIOR_BITNETD",
              "JUNIOR_OFFLINE", "JUNIOR_CHARTER", "syntax", "copies_match", "guard")
LEAK_KEY_RE = re.compile(r"(KERNEL|VMLINUZ|INITRD|OSWORLD)", re.I)
_LINE_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)=(.*)$")
_TRIT_TO_BITS = {0: 0, 1: 1, -1: 2}


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


def side_commit(prev: str, pk: bytes, text: str) -> str:
    """Close rule: sha256(prev || pack || text)[:16]."""
    return hashlib.sha256(prev.encode() + pk + text.encode()).hexdigest()[:16]


def rate_lock_commit(prev: str, pk: bytes) -> str:
    """Rate lock: sha256(prev || pack || b"0.05") full hexdigest."""
    return hashlib.sha256(prev.encode() + pk + RATE_BYTES).hexdigest()


def parse_os_release(text: str) -> tuple[dict[str, str], list[int]]:
    """Parse os-release KEY=VALUE lines. Returns (fields, bad_line_numbers)."""
    fields: dict[str, str] = {}
    bad: list[int] = []
    for i, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        m = _LINE_RE.match(line)
        if not m:
            bad.append(i)
            continue
        key, val = m.group(1), m.group(2)
        if len(val) >= 2 and val[0] == val[-1] and val[0] in "\"'":
            val = val[1:-1]
        elif any(c in val for c in " \"'`$\\"):
            bad.append(i)
        fields[key] = val
    return fields, bad


def _eq(fields: dict[str, str], key: str, want: str) -> int:
    if key not in fields:
        return 0
    return 1 if fields[key] == want else -1


def audit_os_release(text: str, second_copy: str | None = None) -> dict[str, Any]:
    """Score one os-release.junior snapshot into 10 trits."""
    fields, bad = parse_os_release(text)
    like = fields.get("ID_LIKE")
    like_t = 0 if like is None else (1 if {"debian", "alpine"} <= set(like.split()) else -1)
    name_t = 1 if fields.get("NAME") else (0 if "NAME" not in fields else -1)
    leaks: list[str] = []
    if "0.0.0.0" in text:
        leaks.append("wildcard_bind")
    leaks += [f"key:{k}" for k in sorted(fields) if LEAK_KEY_RE.search(k)]
    bitnetd = fields.get("JUNIOR_BITNETD")
    if bitnetd is not None and not bitnetd.startswith(BIND + ":"):
        leaks.append("non_loopback_bitnetd")
    if second_copy is None:
        copies_t = 0
    else:
        same = hashlib.sha256(text.encode()).digest() == hashlib.sha256(second_copy.encode()).digest()
        copies_t = 1 if same else -1
    trits = [
        _eq(fields, "ID", "junioros"),
        like_t,
        _eq(fields, "VARIANT_ID", "overlay"),
        name_t,
        _eq(fields, "JUNIOR_BITNETD", BITNETD),
        _eq(fields, "JUNIOR_OFFLINE", "1"),
        _eq(fields, "JUNIOR_CHARTER", "docs/BETA_TO_OS.md"),
        -1 if bad else 1,
        copies_t,
        -1 if leaks else 1,
    ]
    missing = [k for k, t in zip(FIELD_KEYS, trits) if t == 0 and k != "copies_match"]
    wrong = [k for k, t in zip(FIELD_KEYS, trits) if t == -1]
    return {
        "item": ROADMAP_ITEM,
        "text_sha256": hashlib.sha256(text.encode()).hexdigest(),
        "fields": {k: fields.get(k) for k in FIELD_KEYS[:7]},
        "bad_lines": bad,
        "leaks": leaks,
        "missing": missing,
        "wrong": wrong,
        "trits": trits,
        "conforms": not missing and not wrong,
    }


def audit_text(audit: dict[str, Any]) -> str:
    return json.dumps(audit, sort_keys=True, separators=(",", ":"))


def append_os_release_receipt(ledger: list[dict[str, Any]], prev: str, text: str,
                              second_copy: str | None = None) -> dict[str, Any]:
    """Audit one snapshot and append a receipt with side-commit and rate_commit."""
    audit = audit_os_release(text, second_copy)
    trits = list(audit["trits"])
    body = audit_text(audit)
    pk = pack(trits)
    link = {
        "prev": prev,
        "trits": trits,
        "text": body,
        "conforms": audit["conforms"],
        "commit": side_commit(prev, pk, body),
        "rate_commit": rate_lock_commit(prev, pk),
        "rate": RATE,
    }
    ledger.append(link)
    return link


def backfill_check(ledger: list[dict[str, Any]], prev: str = GENESIS) -> dict[str, Any]:
    """Live-beta backfill gate: contiguous chain; gaps lists broken links,
    nonconforming lists snapshots with missing or wrong fields, leaks lists
    snapshots that name 0.0.0.0, a non-loopback bitnetd, or a kernel/OSWorld key."""
    gaps: list[int] = []
    nonconforming: list[int] = []
    leaks: list[int] = []
    cur = prev
    for i, link in enumerate(ledger):
        try:
            pk = pack(link["trits"])
            body = json.loads(link["text"])
        except (KeyError, ValueError, TypeError):
            gaps.append(i)
            cur = link.get("commit", cur)
            continue
        if (
            link.get("prev") != cur
            or link.get("commit") != side_commit(cur, pk, link["text"])
            or link.get("rate_commit") != rate_lock_commit(cur, pk)
            or link.get("rate") != RATE
            or body.get("trits") != link["trits"]
            or body.get("conforms") != link.get("conforms")
        ):
            gaps.append(i)
        if not body.get("conforms"):
            nonconforming.append(i)
        if body.get("leaks"):
            leaks.append(i)
        cur = link.get("commit", cur)
    return {"ok": not gaps and not leaks, "gaps": gaps, "nonconforming": nonconforming,
            "leaks": leaks, "tip": cur, "n": len(ledger)}


GOOD = """NAME="JuniorOS"
ID=junioros
ID_LIKE="debian alpine"
PRETTY_NAME="JuniorOS overlay (BitNet rail)"
VARIANT="overlay"
VARIANT_ID=overlay
JUNIOR_BITNETD="127.0.0.1:8765"
JUNIOR_OFFLINE="1"
JUNIOR_CHARTER="docs/BETA_TO_OS.md"
# Overlay only. Not a custom kernel.
"""


def self_check() -> dict[str, Any]:
    """Flags, bind, ports, pack vector 4a44, known close, field audits, tamper and gap detection."""
    assert BIND == "127.0.0.1" and BITNETD.startswith(BIND + ":")
    assert PORTS == ("Home", "OSai", "FieldCore", "Flagstaff", "JuniorLLM")
    assert not (MINT or SOCKET or LAYER_ONE or FETCH or UE5_LAUNCH or MODEL_PULL)
    assert RELEASED == 0 and RATE == 0.05

    vec = pack([1, 0, -1, -1, 1, 0, 1])
    assert vec.hex() == "4a44", vec.hex()
    known = side_commit(GENESIS, vec, "home")
    assert known == "dd07dea74a142604", known

    a = audit_os_release(GOOD, GOOD)
    assert a["conforms"] and a["trits"] == [1] * 10, a
    one = audit_os_release(GOOD)
    assert one["conforms"] and one["trits"][8] == 0
    drift = audit_os_release(GOOD, GOOD.replace("alpine", "ubuntu"))
    assert drift["trits"][8] == -1 and "copies_match" in drift["wrong"]
    wide = audit_os_release(GOOD.replace("127.0.0.1:8765", "0.0.0.0:8765"))
    assert wide["trits"][4] == -1 and wide["trits"][9] == -1
    assert "wildcard_bind" in wide["leaks"] and "non_loopback_bitnetd" in wide["leaks"]
    blob = audit_os_release(GOOD + "JUNIOR_KERNEL=vmlinuz-junior\nOSWORLD_SCORE=0.9\n")
    assert blob["leaks"] == ["key:JUNIOR_KERNEL", "key:OSWORLD_SCORE"] and not blob["conforms"]
    bare = audit_os_release("ID=debian\n")
    assert bare["trits"][0] == -1 and "JUNIOR_BITNETD" in bare["missing"] and not bare["conforms"]
    junk = audit_os_release(GOOD + "this is not a field\nPRETTY=two words\n")
    assert junk["bad_lines"] == [11, 12] and junk["trits"][7] == -1
    like = audit_os_release(GOOD.replace('"debian alpine"', "debian"))
    assert like["trits"][1] == -1

    ledger: list[dict[str, Any]] = []
    r0 = append_os_release_receipt(ledger, GENESIS, GOOD, GOOD)
    r1 = append_os_release_receipt(ledger, r0["commit"], GOOD)
    r2 = append_os_release_receipt(ledger, r1["commit"], "ID=debian\n")
    bf = backfill_check(ledger)
    assert bf["ok"] and bf["gaps"] == [] and bf["n"] == 3 and bf["tip"] == r2["commit"]
    assert bf["nonconforming"] == [2] and bf["leaks"] == []

    lk = list(ledger)
    append_os_release_receipt(lk, r2["commit"], GOOD.replace("127.0.0.1", "0.0.0.0"))
    bl = backfill_check(lk)
    assert bl["leaks"] == [3] and not bl["ok"] and bl["gaps"] == []

    t = [dict(x) for x in ledger]
    t[1] = dict(t[1], text=t[1]["text"].replace('"conforms":true', '"conforms":false'))
    assert 1 in backfill_check(t)["gaps"]
    r = [dict(x) for x in ledger]
    r[0] = dict(r[0], rate_commit=hashlib.sha256(b"x").hexdigest())
    assert 0 in backfill_check(r)["gaps"]
    d = [ledger[0], ledger[2]]
    assert 1 in backfill_check(d)["gaps"]

    return {
        "ok": True,
        "item": ROADMAP_ITEM,
        "bind": BIND,
        "bitnetd": BITNETD,
        "ports": list(PORTS),
        "rate": RATE,
        "pack_vector": vec.hex(),
        "close_home_4a44": known,
        "engines": list(COMPATIBLE_ENGINES),
        "tip": bf["tip"],
        "flags": {"mint": MINT, "socket": SOCKET, "layer_one": LAYER_ONE, "fetch": FETCH,
                  "ue5_launch": UE5_LAUNCH, "model_pull": MODEL_PULL, "released": RELEASED},
    }


def _read_local(path: str) -> str:
    with open(path, "rb") as fh:
        return fh.read(MAX_READ).decode("utf-8", "replace")


def main(argv: list[str]) -> int:
    if "--selftest" in argv:
        print(json.dumps(self_check(), sort_keys=True))
        return 0
    text = GOOD
    second: str | None = None
    if "--file" in argv:
        i = argv.index("--file")
        if i + 1 >= len(argv):
            print("usage: --file PATH [--second PATH]", file=sys.stderr)
            return 2
        text = _read_local(argv[i + 1])
    if "--second" in argv:
        i = argv.index("--second")
        if i + 1 < len(argv):
            second = _read_local(argv[i + 1])
    ledger: list[dict[str, Any]] = []
    link = append_os_release_receipt(ledger, GENESIS, text, second)
    print(json.dumps({"receipt": link, "backfill": backfill_check(ledger)}, sort_keys=True))
    return 0 if link["conforms"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
