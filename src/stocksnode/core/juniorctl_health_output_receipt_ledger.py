"""juniorctl health output receipt ledger: field receipts + side-commit + rate lock.

Roadmap item: JuniorLLM docs/BETA_TO_OS.md "Live beta" step 1,
`PYTHONPATH=. python rails/linux/juniorctl.py health`, the health *output*
part, as named for pair B by Quant Chief on 2026-10-19 05:11 MT (live beta
remaining gaps only; "juniorctl ask or health output receipts" listed as
uncovered; step 2 night, per-step exit codes, linux security findings, e2e exit
trits, and test_junior_aie per-case already landed; pair A covers juniorctl
security). The matching handshake/port check belongs to Handshake & Ports in a
different file.

This is a new capability. It never imports, runs, wraps, tests, rewrites, or
re-derives rails/linux/juniorctl.py, ports/registry.py, ctl_cli.py,
backfill_check.py, or any other team file, including my own earlier ledgers
(those see `juniorctl health` only as one exit code; none read what it says).

The gap it fills, from the caller-declared stdout text + exit code of one
`juniorctl health` run (the JSON object health() prints):
  1. Per-field receipts, one trit each (+1 holds, 0 not reported, -1 breaks):
     json (stdout is one JSON object), keys (exactly product/bitnetd/security/
     ports/cmds), product ("JuniorOS overlay"), bind (bitnetd exactly
     127.0.0.1:8765, never 0.0.0.0 or another host), security_doc (ends with
     rails/linux/CONTAINER_SECURITY.md), ports_core (registry names behind the
     team ports present), ports_unique, cmds_live_beta (health, ask <q>, night,
     security advertised), cmds_unique, cmds_safe (no pull/download/fetch/
     ue5/mint/launch/0.0.0.0/--no-verify verb advertised), exit (0 iff the
     output parsed), guard.
  2. A surface digest over the sorted ports and cmds lists, so a later run can
     show which ports or cmds appeared or vanished.
  3. One run receipt that folds the field trits, closing over the tip of that
     run's field chain.
  4. backfill_check: chain + rate lock replay, failed fields per run, missing
     core ports and live-beta cmds, cross-run drift (ports added/removed, cmds
     removed, bind changed), field regressions (+1 -> -1), guard breaches.
Offline: no subprocess, no file reads, no network, no sockets, no model pull,
no GGUF download, no UE5 launch.

Team port map (registry name the health output must list):
  Home -> JuniorOSai ("Home kernel + Flagstaff"), OSai -> JuniorOSai,
  FieldCore -> JuniorBitNetFieldCore, Flagstaff -> JuniorOSai (backend
  flagstaff), JuniorLLM -> the registry itself, plus web3node and BitNet-2B4T
  (I2_S, header only if already on disk).

Stdlib only. Close: sha256(prev || pack || text)[:16] with i2s 2-bit pack
(0->0, 1->1, -1->2), MSB first, zero-padded (pack vector 4a44). Rate lock
commits rate 0.05 beside the pack as sha256(prev || pack || b"0.05") full
hexdigest (JuniorHome docs/JUNIORS_RATE.md).

Ports touched: Home, OSai, FieldCore, Flagstaff, JuniorLLM. Bind 127.0.0.1.

Run: python3 juniorctl_health_output_receipt_ledger.py --selftest
     python3 juniorctl_health_output_receipt_ledger.py --run '{"stdout":"{...}","exit":0}'
"""
from __future__ import annotations

import hashlib
import json
import sys
from typing import Any, Mapping

RATE = 0.05
RATE_BYTES = b"0.05"
GENESIS = "0" * 16
ROADMAP_ITEM = (
    "JuniorLLM docs/BETA_TO_OS.md Live beta step 1: juniorctl health output receipts"
)

MINT = False
SOCKET = False
LAYER_ONE = False
FETCH = False
UE5_LAUNCH = False
MODEL_PULL = False
SUBPROCESS = False
RELEASED = 0
BIND = "127.0.0.1"
BITNETD_BIND = "127.0.0.1:8765"
PORTS = ("Home", "OSai", "FieldCore", "Flagstaff", "JuniorLLM")
COMPATIBLE_ENGINES = ("web3node", "stocksnode", "JuniorLLM", "BitNet-mlx")

EXPECTED_PRODUCT = "JuniorOS overlay"
SECURITY_DOC_SUFFIX = "rails/linux/CONTAINER_SECURITY.md"
EXPECTED_KEYS = ("bitnetd", "cmds", "ports", "product", "security")
TEAM_PORT_MAP = {
    "Home": "JuniorOSai",
    "OSai": "JuniorOSai",
    "FieldCore": "JuniorBitNetFieldCore",
    "Flagstaff": "JuniorOSai",
    "JuniorLLM": None,  # the registry itself serves the list
}
CORE_PORTS = ("JuniorOSai", "JuniorBitNetFieldCore", "web3node", "BitNet-2B4T")
LIVE_BETA_CMDS = ("health", "ask <q>", "night", "security")
UNSAFE_TOKENS = ("pull", "download", "fetch", "ue5", "mint", "launch",
                 "0.0.0.0", "--no-verify", "force-push")
FIELDS = ("json", "keys", "product", "bind", "security_doc", "ports_core",
          "ports_unique", "cmds_live_beta", "cmds_unique", "cmds_safe", "exit", "guard")

_TRIT_TO_BITS = {0: 0, 1: 1, -1: 2}
_GUARD_KEYS = ("fetch", "socket", "mint", "exec", "layer_one", "model_pull", "ue5_launch")


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


def _canon(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def fold(trits: list[int]) -> int:
    if any(t == -1 for t in trits):
        return -1
    if any(t == 0 for t in trits):
        return 0
    return 1


def parse_health(stdout: Any) -> tuple[int, dict[str, Any] | None]:
    """Parse declared stdout: (+1, obj) one JSON object; (0, None) empty; (-1, None) bad."""
    text = "" if stdout is None else str(stdout).strip()
    if not text:
        return 0, None
    try:
        obj = json.loads(text)
    except ValueError:
        return -1, None
    if not isinstance(obj, dict):
        return -1, None
    return 1, obj


def _str_list(v: Any) -> list[str] | None:
    if not isinstance(v, list) or not all(isinstance(x, str) for x in v):
        return None
    return list(v)


def _dupes(xs: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for x in xs:
        if x in seen and x not in out:
            out.append(x)
        seen.add(x)
    return out


def _guard(run: Mapping[str, Any]) -> list[str]:
    g = run.get("guard") or {}
    bad = [k for k in _GUARD_KEYS if g.get(k)]
    bind = g.get("bind")
    if bind is not None and str(bind) != BITNETD_BIND:
        bad.append("bind")
    return bad


def surface_digest(ports: list[str], cmds: list[str]) -> str:
    """16-hex digest of the sorted ports and cmds surface."""
    body = _canon({"cmds": sorted(set(cmds)), "ports": sorted(set(ports))})
    return hashlib.sha256(body.encode()).hexdigest()[:16]


def audit_run(run: Mapping[str, Any]) -> dict[str, Any]:
    """Audit one declared `juniorctl health` run, field by field (no exec)."""
    json_t, obj = parse_health(run.get("stdout"))
    o = obj or {}
    reported = obj is not None
    t: dict[str, int] = {"json": json_t}

    missing_keys = [k for k in EXPECTED_KEYS if k not in o]
    extra_keys = sorted(k for k in o if k not in EXPECTED_KEYS)
    if not reported:
        t["keys"] = 0
    else:
        t["keys"] = -1 if missing_keys else (0 if extra_keys else 1)

    if "product" not in o:
        t["product"] = 0
    else:
        t["product"] = 1 if o["product"] == EXPECTED_PRODUCT else -1

    bind = o.get("bitnetd")
    if bind is None:
        t["bind"] = 0
    else:
        t["bind"] = 1 if bind == BITNETD_BIND else -1

    sec = o.get("security")
    if sec is None:
        t["security_doc"] = 0
    else:
        t["security_doc"] = 1 if (isinstance(sec, str)
                                  and sec.replace("\\", "/").endswith(SECURITY_DOC_SUFFIX)) else -1

    ports = _str_list(o.get("ports")) if "ports" in o else None
    port_dupes: list[str] = []
    missing_ports: list[str] = []
    if "ports" not in o:
        t["ports_core"] = t["ports_unique"] = 0
    elif ports is None:
        t["ports_core"] = t["ports_unique"] = -1
    else:
        missing_ports = [p for p in CORE_PORTS if p not in ports]
        port_dupes = _dupes(ports)
        t["ports_core"] = -1 if missing_ports else 1
        t["ports_unique"] = -1 if port_dupes else 1

    cmds = _str_list(o.get("cmds")) if "cmds" in o else None
    cmd_dupes: list[str] = []
    missing_cmds: list[str] = []
    unsafe_cmds: list[str] = []
    if "cmds" not in o:
        t["cmds_live_beta"] = t["cmds_unique"] = t["cmds_safe"] = 0
    elif cmds is None:
        t["cmds_live_beta"] = t["cmds_unique"] = t["cmds_safe"] = -1
    else:
        missing_cmds = [c for c in LIVE_BETA_CMDS if c not in cmds]
        cmd_dupes = _dupes(cmds)
        unsafe_cmds = [c for c in cmds if any(tok in c.lower() for tok in UNSAFE_TOKENS)]
        t["cmds_live_beta"] = -1 if missing_cmds else 1
        t["cmds_unique"] = -1 if cmd_dupes else 1
        t["cmds_safe"] = -1 if unsafe_cmds else 1

    code = run.get("exit")
    if code is None:
        t["exit"] = 0
    elif isinstance(code, bool) or not isinstance(code, int):
        t["exit"] = -1
    else:
        t["exit"] = 1 if (code == 0) == (json_t == 1) else -1

    breach = _guard(run)
    t["guard"] = -1 if breach else 1
    trits = [t[f] for f in FIELDS]
    return {
        "field_trits": t, "trits": trits, "verdict": fold(trits),
        "missing_keys": missing_keys, "extra_keys": extra_keys,
        "missing_ports": missing_ports, "port_dupes": port_dupes,
        "missing_cmds": missing_cmds, "cmd_dupes": cmd_dupes, "unsafe_cmds": unsafe_cmds,
        "ports": sorted(set(ports or [])), "cmds": sorted(set(cmds or [])),
        "bitnetd": bind if isinstance(bind, str) else None,
        "surface": surface_digest(ports or [], cmds or []) if reported else None,
        "guard_breach": breach,
    }


def _link(prev: str, kind: str, trits: list[int], body: dict[str, Any]) -> dict[str, Any]:
    pk = pack(trits)
    text = _canon(body)
    return {"kind": kind, "prev": prev, "trits": trits, "pack": pk.hex(),
            "body": body, "close": side_commit(prev, pk, text),
            "rate_commit": rate_lock_commit(prev, pk), "rate": RATE}


def append_run(ledger: list[dict[str, Any]], prev: str, run: Mapping[str, Any]) -> dict[str, Any]:
    """Append one field receipt per health field, then one run receipt over them."""
    a = audit_run(run)
    run_id = str(run.get("run_id", len([x for x in ledger if x["kind"] == "run"])))
    cur = prev
    for f in FIELDS:
        tr = a["field_trits"][f]
        body = {"run_id": run_id, "field": f, "trit": tr, "rate": RATE,
                "roadmap": ROADMAP_ITEM}
        link = _link(cur, "field", [tr], body)
        ledger.append(link)
        cur = link["close"]
    body = {"run_id": run_id, "fields_tip": cur, "verdict": a["verdict"],
            "failed": [f for f in FIELDS if a["field_trits"][f] == -1],
            "unreported": [f for f in FIELDS if a["field_trits"][f] == 0],
            "missing_keys": a["missing_keys"], "extra_keys": a["extra_keys"],
            "missing_ports": a["missing_ports"], "port_dupes": a["port_dupes"],
            "missing_cmds": a["missing_cmds"], "cmd_dupes": a["cmd_dupes"],
            "unsafe_cmds": a["unsafe_cmds"], "ports_seen": a["ports"],
            "cmds_seen": a["cmds"], "bitnetd": a["bitnetd"], "surface": a["surface"],
            "guard_breach": a["guard_breach"], "team_ports": list(PORTS),
            "bind": BIND, "rate": RATE, "roadmap": ROADMAP_ITEM}
    link = _link(cur, "run", a["trits"], body)
    ledger.append(link)
    return link


def backfill_check(ledger: list[dict[str, Any]], prev: str = GENESIS) -> dict[str, Any]:
    """Replay chain and rate lock; list failures, gaps, drift, regressions, breaches.

    broken: indexes whose prev/close/rate_commit/rate do not replay;
    failed / missing_ports / missing_cmds: per run_id; drift: per run_id vs the
    previous run (ports_added, ports_removed, cmds_removed, bind_changed);
    regressions: fields +1 in the previous run, -1 now; breaches: guard."""
    broken: list[int] = []
    cur = prev
    failed: dict[str, list[str]] = {}
    missing_ports: dict[str, list[str]] = {}
    missing_cmds: dict[str, list[str]] = {}
    drift: dict[str, dict[str, Any]] = {}
    regressions: list[str] = []
    breaches: list[str] = []
    last: dict[str, Any] | None = None
    this_fields: dict[str, int] = {}
    for i, link in enumerate(ledger):
        pk = bytes.fromhex(link.get("pack", ""))
        ok = (link.get("prev") == cur
              and pack(list(link.get("trits", []))) == pk
              and link.get("close") == side_commit(cur, pk, _canon(link.get("body", {})))
              and link.get("rate_commit") == rate_lock_commit(cur, pk)
              and link.get("rate") == RATE
              and link.get("body", {}).get("rate") == RATE)
        if not ok:
            broken.append(i)
        cur = link.get("close", cur)
        body = link.get("body", {})
        if link.get("kind") == "field":
            this_fields[str(body.get("field"))] = body.get("trit", 0)
            continue
        rid = str(body.get("run_id"))
        for key, dest in (("failed", failed), ("missing_ports", missing_ports),
                          ("missing_cmds", missing_cmds)):
            if body.get(key):
                dest[rid] = list(body[key])
        if body.get("guard_breach"):
            breaches.append(rid)
        if last is not None and body.get("surface") and last["body"].get("surface"):
            lp, np_ = set(last["body"].get("ports_seen", [])), set(body.get("ports_seen", []))
            lc, nc = set(last["body"].get("cmds_seen", [])), set(body.get("cmds_seen", []))
            d: dict[str, Any] = {}
            if np_ - lp:
                d["ports_added"] = sorted(np_ - lp)
            if lp - np_:
                d["ports_removed"] = sorted(lp - np_)
            if lc - nc:
                d["cmds_removed"] = sorted(lc - nc)
            if last["body"].get("bitnetd") != body.get("bitnetd"):
                d["bind_changed"] = [last["body"].get("bitnetd"), body.get("bitnetd")]
            if d:
                drift[rid] = d
        if last is not None:
            for f in FIELDS:
                if last["fields"].get(f) == 1 and this_fields.get(f) == -1:
                    regressions.append(f"{rid}:{f}")
        last = {"body": body, "fields": this_fields}
        this_fields = {}
    shrink = any(("ports_removed" in d or "cmds_removed" in d or "bind_changed" in d)
                 for d in drift.values())
    return {"ok": not (broken or failed or missing_ports or missing_cmds or breaches or shrink),
            "broken": broken, "failed": failed, "missing_ports": missing_ports,
            "missing_cmds": missing_cmds, "drift": drift, "regressions": regressions,
            "breaches": breaches, "tip": cur, "n": len(ledger)}


_SAMPLE_PORTS = ["JuniorOSai", "JuniorOmega", "AGI_SDK", "JuniorStoneField", "web3node",
                 "JuniorBitNetFieldCore", "BitNet-2B4T", "JuniorGemma4-4B"]
_SAMPLE_CMDS = ["health", "port list", "ask <q>", "night", "security", "quant",
                "oci validate", "path pin", "skill-pin list"]


def _health_stdout(**over: Any) -> str:
    obj: dict[str, Any] = {
        "product": EXPECTED_PRODUCT, "bitnetd": BITNETD_BIND,
        "security": "/srv/JuniorLLM/" + SECURITY_DOC_SUFFIX,
        "ports": list(_SAMPLE_PORTS), "cmds": list(_SAMPLE_CMDS)}
    for k, v in over.items():
        if v is None:
            obj.pop(k, None)
        else:
            obj[k] = v
    return json.dumps(obj, indent=2)


def self_check() -> dict[str, Any]:
    """Flags, bind, ports, pack vector 4a44, known close, audit, chain, drift, tamper."""
    assert BIND == "127.0.0.1" and BITNETD_BIND.startswith(BIND + ":")
    assert PORTS == ("Home", "OSai", "FieldCore", "Flagstaff", "JuniorLLM")
    assert set(TEAM_PORT_MAP) == set(PORTS)
    assert not (MINT or SOCKET or LAYER_ONE or FETCH or UE5_LAUNCH or MODEL_PULL or SUBPROCESS)
    assert RELEASED == 0 and RATE == 0.05

    vec = pack([1, 0, -1, -1, 1, 0, 1])
    assert vec.hex() == "4a44", vec.hex()
    known = side_commit(GENESIS, vec, "home")
    assert known == "dd07dea74a142604", known

    green = {"run_id": "r0", "stdout": _health_stdout(), "exit": 0,
             "guard": {"bind": BITNETD_BIND}}
    a = audit_run(green)
    assert a["verdict"] == 1 and a["trits"] == [1] * len(FIELDS), a

    assert audit_run({"stdout": _health_stdout(bitnetd="0.0.0.0:8765"), "exit": 0})[
        "field_trits"]["bind"] == -1
    assert audit_run({"stdout": _health_stdout(product="JuniorOS"), "exit": 0})[
        "field_trits"]["product"] == -1
    assert audit_run({"stdout": _health_stdout(security="/tmp/README.md"), "exit": 0})[
        "field_trits"]["security_doc"] == -1
    a = audit_run({"stdout": _health_stdout(ports=_SAMPLE_PORTS[:5] + ["web3node"]), "exit": 0})
    assert a["missing_ports"] == ["JuniorBitNetFieldCore", "BitNet-2B4T"], a
    assert a["port_dupes"] == ["web3node"] and a["field_trits"]["ports_unique"] == -1
    a = audit_run({"stdout": _health_stdout(cmds=["health", "ask <q>", "security",
                                                   "model pull", "health"]), "exit": 0})
    assert a["missing_cmds"] == ["night"] and a["unsafe_cmds"] == ["model pull"]
    assert a["cmd_dupes"] == ["health"] and a["verdict"] == -1
    a = audit_run({"stdout": _health_stdout(cmds=None), "exit": 0})
    assert a["missing_keys"] == ["cmds"] and a["field_trits"]["keys"] == -1
    assert a["field_trits"]["cmds_live_beta"] == 0
    a = audit_run({"stdout": _health_stdout(extra="x"), "exit": 0})
    assert a["extra_keys"] == ["extra"] and a["field_trits"]["keys"] == 0 and a["verdict"] == 0
    tb = audit_run({"stdout": "Traceback (most recent call last):\n  ...", "exit": 1})
    assert tb["field_trits"]["json"] == -1 and tb["field_trits"]["exit"] == 1
    assert audit_run({"stdout": "[1, 2]", "exit": 0})["field_trits"]["exit"] == -1
    assert audit_run({"stdout": _health_stdout(), "exit": 3})["field_trits"]["exit"] == -1
    empty = audit_run({"stdout": "", "exit": None})
    assert empty["verdict"] == 0 and empty["surface"] is None
    breach = audit_run(dict(green, guard={"socket": True, "bind": "192.0.2.7:8765"}))
    assert breach["guard_breach"] == ["socket", "bind"] and breach["verdict"] == -1

    ledger: list[dict[str, Any]] = []
    r0 = append_run(ledger, GENESIS, green)
    r1 = append_run(ledger, r0["close"], {
        "run_id": "r1", "exit": 0,
        "stdout": _health_stdout(bitnetd="0.0.0.0:8765", ports=_SAMPLE_PORTS + ["Qwen-local"],
                                 cmds=[c for c in _SAMPLE_CMDS if c != "night"])})
    assert len(ledger) == 2 * (len(FIELDS) + 1) and r1["prev"] == ledger[-2]["close"]
    bc = backfill_check(ledger)
    assert bc["broken"] == [] and bc["tip"] == r1["close"], bc
    assert bc["failed"] == {"r1": ["bind", "cmds_live_beta"]}, bc
    assert bc["missing_cmds"] == {"r1": ["night"]}
    assert bc["drift"] == {"r1": {"ports_added": ["Qwen-local"], "cmds_removed": ["night"],
                                  "bind_changed": [BITNETD_BIND, "0.0.0.0:8765"]}}, bc
    assert bc["regressions"] == ["r1:bind", "r1:cmds_live_beta"] and bc["ok"] is False

    clean: list[dict[str, Any]] = []
    c0 = append_run(clean, GENESIS, green)
    append_run(clean, c0["close"], dict(green, run_id="r1"))
    bc = backfill_check(clean)
    assert bc["ok"] is True and bc["drift"] == {}, bc

    t = [dict(x) for x in clean]
    t[3] = dict(t[3], body=dict(t[3]["body"], trit=-1))
    assert backfill_check(t)["broken"][:1] == [3]
    t = [dict(x) for x in clean]
    t[0] = dict(t[0], rate_commit=hashlib.sha256(b"x").hexdigest())
    assert backfill_check(t)["broken"][:1] == [0]
    t = [dict(x) for x in clean]
    t[-1] = dict(t[-1], rate=0.06)
    assert backfill_check(t)["broken"] == [len(clean) - 1]

    return {
        "ok": True,
        "roadmap": ROADMAP_ITEM,
        "known_close": known,
        "pack_vector": vec.hex(),
        "bind": BIND,
        "bitnetd_bind": BITNETD_BIND,
        "ports": list(PORTS),
        "team_port_map": TEAM_PORT_MAP,
        "fields": list(FIELDS),
        "rate": RATE,
        "green_close": clean[len(FIELDS)]["close"],
        "green_surface": audit_run(green)["surface"],
        "compatible_engines": list(COMPATIBLE_ENGINES),
        "flags": {"mint": MINT, "socket": SOCKET, "layer_one": LAYER_ONE, "fetch": FETCH,
                  "ue5_launch": UE5_LAUNCH, "model_pull": MODEL_PULL,
                  "subprocess": SUBPROCESS, "released": RELEASED},
    }


def main(argv: list[str]) -> int:
    if "--selftest" in argv:
        print(json.dumps(self_check(), indent=2, sort_keys=True))
        return 0
    if "--run" in argv:
        i = argv.index("--run")
        run = json.loads(argv[i + 1])
        ledger: list[dict[str, Any]] = []
        link = append_run(ledger, GENESIS, run)
        print(json.dumps({"run": link, "backfill_check": backfill_check(ledger)},
                         indent=2, sort_keys=True))
        return 0 if link["body"]["verdict"] == 1 else 1
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
