"""bitnetd user-unit hardening parity receipt ledger: side-commit + rate lock.

ROADMAP item: JuniorLLM docs/BETA_TO_OS.md "JuniorOS overlay", overlay confirm
receipt, gaps only (Quant Chief pair B slot, 2026-10-18 14:15 MT). os-release.junior,
juniorctl on PATH, Debian/Alpine and bitnetd MemoryMax already landed; the known
open gap (Quant Verifier, JuniorLLM 574d1b3 advisory) is that the systemd --user
unit usr/lib/systemd/user/bitnetd.service lacks 11 hardening lines that the system
unit etc/systemd/system/bitnetd.service carries. This file is the receipt chain
for that one gap: each snapshot of the declared (system, user) unit pair gets a
receipt naming exactly which system hardening lines the user unit still lacks, and
backfill_check only goes green once the latest receipt shows parity closed with no
regression. Pair B receipt and ledger piece; the matching handshake/port check
belongs to Handshake & Ports. New capability: it never imports, wraps, tests,
rewrites, or re-derives any team file (not rails/linux/install-overlay.sh,
path_pin.py, ports/overlay_bind_agreement_port_map.py, or any earlier
stocksnode/web3node ledger, including web3node bitnetd_unit_hardening_receipt.py,
which audits a single unit, not the system-vs-user pair).
Advances live-beta receipt chains / backfill_check at rate 0.05.

What it records, from unit texts the caller declares (no filesystem walk):
the [Service] lines of both units, parity_lines = every system hardening line that
is not run-identity (User=/Group= are system-only by design) and not run config
(Type/ExecStart/Restart/Environment), then missing = parity lines absent from the
user unit, differs = keys present in the user unit with another value. 10 trits:
system_parsed, user_parsed, core_system and core_user (the shared core directives:
NoNewPrivileges, ProtectSystem=strict, PrivateTmp, MemoryDenyWriteExecute,
RestrictAddressFamilies, RestrictNamespaces, empty capability sets, MemoryMax=2G,
TasksMax=256), parity (no missing line), no_weaker (no differing value, no
explicit weakening such as NoNewPrivileges=no), bind (both JUNIOR_BIND
127.0.0.1:8765), offline (both JUNIOR_OFFLINE=1), targets (system
multi-user.target, user default.target), guard (no 0.0.0.0, no docker.sock, no
User= in the user unit).
Offline: no subprocess, no os.environ reads, no network, no sockets, no model
pull, no UE5.

Stdlib only. Close: sha256(prev || pack || text)[:16] with i2s 2-bit pack
(0->0, 1->1, -1->2), MSB first, zero-padded (pack vector 4a44). Rate lock
commits rate 0.05 beside the pack as sha256(prev || pack || b"0.05") full
hexdigest (JuniorHome docs/JUNIORS_RATE.md).

Ports touched: Home, OSai, FieldCore, Flagstaff, JuniorLLM. Bind 127.0.0.1.

Run: python3 bitnetd_user_unit_parity_receipt_ledger.py --selftest
     python3 bitnetd_user_unit_parity_receipt_ledger.py --facts pair.json
       (pair.json: {"label", "system_unit", "user_unit"} or a list of them)
"""
from __future__ import annotations

import hashlib
import json
import sys
from typing import Any

RATE = 0.05
RATE_BYTES = b"0.05"
GENESIS = "0" * 16
ROADMAP_ITEM = ("JuniorLLM docs/BETA_TO_OS.md JuniorOS overlay - overlay confirm "
                "receipt gap: bitnetd user-unit hardening parity")
MAX_READ = 65536

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

SYSTEM_ONLY_KEYS = ("User", "Group")
RUN_KEYS = ("Type", "ExecStart", "Restart", "Environment", "ExecStartPre",
            "ExecStartPost", "ExecReload", "ExecStop", "WorkingDirectory")
CORE_LINES = (
    "NoNewPrivileges=yes",
    "ProtectSystem=strict",
    "PrivateTmp=yes",
    "MemoryDenyWriteExecute=yes",
    "RestrictAddressFamilies=AF_UNIX AF_INET AF_INET6",
    "RestrictNamespaces=yes",
    "CapabilityBoundingSet=",
    "AmbientCapabilities=",
    "MemoryMax=2G",
    "TasksMax=256",
)
WEAKENING = (
    "NoNewPrivileges=no", "ProtectSystem=no", "ProtectSystem=false",
    "PrivateTmp=no", "MemoryDenyWriteExecute=no", "RestrictNamespaces=no",
    "ProtectHome=no", "PrivateDevices=no", "LockPersonality=no",
    "RestrictSUIDSGID=no", "RestrictRealtime=no",
)
# SystemCallFilter and RestrictAddressFamilies stack across lines, so a
# different value is an addition, not a replacement.
STACKING_KEYS = ("SystemCallFilter", "RestrictAddressFamilies")
TRIT_KEYS = ("system_parsed", "user_parsed", "core_system", "core_user", "parity",
             "no_weaker", "bind", "offline", "targets", "guard")
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


def sections(unit: str | None) -> dict[str, list[str]] | None:
    """Split unit text into {section: [normalized key=value lines]}; None if no [Service]."""
    if not unit:
        return None
    out: dict[str, list[str]] = {}
    cur = None
    for raw in unit.splitlines():
        line = raw.strip()
        if not line or line[0] in "#;":
            continue
        if line.startswith("[") and line.endswith("]"):
            cur = line[1:-1]
            out.setdefault(cur, [])
            continue
        if cur is None or "=" not in line:
            continue
        k, v = line.split("=", 1)
        out[cur].append(k.strip() + "=" + v.strip())
    return out if "Service" in out else None


def _key(line: str) -> str:
    return line.split("=", 1)[0]


def parity_lines(service: list[str]) -> list[str]:
    """System [Service] hardening lines the user unit must mirror."""
    return [ln for ln in service
            if _key(ln) not in SYSTEM_ONLY_KEYS and _key(ln) not in RUN_KEYS]


def _envs(service: list[str]) -> dict[str, str]:
    env: dict[str, str] = {}
    for ln in service:
        if ln.startswith("Environment="):
            for part in ln[len("Environment="):].split():
                if "=" in part:
                    k, v = part.strip('"').split("=", 1)
                    env[k] = v
    return env


def audit_pair(facts: dict[str, Any]) -> dict[str, Any]:
    """Score one caller-declared (system unit, user unit) snapshot into 10 trits."""
    sys_u = sections(facts.get("system_unit"))
    usr_u = sections(facts.get("user_unit"))
    sys_t = 1 if sys_u else (0 if not facts.get("system_unit") else -1)
    usr_t = 1 if usr_u else (0 if not facts.get("user_unit") else -1)
    s_svc = (sys_u or {}).get("Service", [])
    u_svc = (usr_u or {}).get("Service", [])

    core_s = (1 if all(c in s_svc for c in CORE_LINES) else -1) if sys_u else 0
    core_u = (1 if all(c in u_svc for c in CORE_LINES) else -1) if usr_u else 0
    core_missing_user = [c for c in CORE_LINES if usr_u and c not in u_svc]

    want = parity_lines(s_svc) if sys_u else []
    u_left = list(u_svc)
    missing: list[str] = []
    for ln in want:
        if ln in u_left:
            u_left.remove(ln)
        else:
            missing.append(ln)
    u_keys = {_key(ln): ln for ln in u_svc}
    differs = sorted({u_keys[_key(m)] for m in missing
                      if _key(m) in u_keys and _key(m) not in STACKING_KEYS})
    weakened = sorted(ln for ln in u_svc if ln in WEAKENING)
    if sys_u and usr_u:
        parity_t = 1 if not missing else -1
        weaker_t = 1 if not differs and not weakened else -1
    else:
        parity_t = 0
        weaker_t = 0 if not usr_u else (1 if not weakened else -1)

    s_env, u_env = _envs(s_svc), _envs(u_svc)
    if sys_u and usr_u:
        bind_t = 1 if s_env.get("JUNIOR_BIND") == BITNETD == u_env.get("JUNIOR_BIND") else -1
        off_t = 1 if s_env.get("JUNIOR_OFFLINE") == "1" == u_env.get("JUNIOR_OFFLINE") else -1
        s_inst = sys_u.get("Install", [])
        u_inst = usr_u.get("Install", [])
        tgt_t = 1 if ("WantedBy=multi-user.target" in s_inst
                      and "WantedBy=default.target" in u_inst) else -1
    else:
        bind_t = off_t = tgt_t = 0

    leaks: list[str] = []
    blob = (facts.get("system_unit") or "") + "\n" + (facts.get("user_unit") or "")
    if "0.0.0.0" in blob:
        leaks.append("wildcard_bind")
    if "docker.sock" in blob:
        leaks.append("docker_socket")
    if any(_key(ln) in SYSTEM_ONLY_KEYS for ln in u_svc):
        leaks.append("user_unit_sets_identity")
    guard_t = -1 if leaks else 1

    trits = [sys_t, usr_t, core_s, core_u, parity_t, weaker_t, bind_t, off_t, tgt_t, guard_t]
    open_keys = [k for k, t in zip(TRIT_KEYS, trits) if t == 0]
    wrong = [k for k, t in zip(TRIT_KEYS, trits) if t == -1]
    return {
        "item": ROADMAP_ITEM,
        "label": facts.get("label", "bitnetd"),
        "parity_lines": len(want),
        "missing": missing,
        "missing_count": len(missing),
        "core_missing_user": core_missing_user,
        "differs": differs,
        "weakened": weakened,
        "leaks": leaks,
        "open": open_keys,
        "wrong": wrong,
        "trits": trits,
        "conforms": not open_keys and not wrong,
    }


def audit_text(audit: dict[str, Any]) -> str:
    return json.dumps(audit, sort_keys=True, separators=(",", ":"))


def append_pair_receipt(ledger: list[dict[str, Any]], prev: str,
                        facts: dict[str, Any]) -> dict[str, Any]:
    """Audit one unit-pair snapshot and append a receipt with side-commit and rate_commit."""
    audit = audit_pair(facts)
    trits = list(audit["trits"])
    body = audit_text(audit)
    pk = pack(trits)
    link = {
        "prev": prev,
        "trits": trits,
        "text": body,
        "conforms": audit["conforms"],
        "missing_count": audit["missing_count"],
        "commit": side_commit(prev, pk, body),
        "rate_commit": rate_lock_commit(prev, pk),
        "rate": RATE,
    }
    ledger.append(link)
    return link


def backfill_check(ledger: list[dict[str, Any]], prev: str = GENESIS) -> dict[str, Any]:
    """Live-beta backfill gate. gaps: broken links; open_parity: receipts whose user unit
    still lacks system hardening lines; regressions: a label's missing_count grew;
    leaks: wildcard bind, docker.sock, or User=/Group= in the user unit; closed: labels
    whose latest valid receipt conforms; still_open: labels whose latest does not."""
    gaps: list[int] = []
    open_parity: list[int] = []
    regressions: list[int] = []
    leaks: list[int] = []
    last_missing: dict[str, int] = {}
    latest: dict[str, bool] = {}
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
            or body.get("missing_count") != link.get("missing_count")
        ):
            gaps.append(i)
            cur = link.get("commit", cur)
            continue
        label = body.get("label", "bitnetd")
        mc = int(body.get("missing_count", 0))
        if mc:
            open_parity.append(i)
        if label in last_missing and mc > last_missing[label]:
            regressions.append(i)
        last_missing[label] = mc
        if body.get("leaks"):
            leaks.append(i)
        latest[label] = bool(body.get("conforms"))
        cur = link.get("commit", cur)
    closed = sorted(k for k, v in latest.items() if v)
    still_open = sorted(k for k, v in latest.items() if not v)
    ok = bool(latest) and not gaps and not leaks and not regressions and not still_open
    return {"ok": ok, "gaps": gaps, "open_parity": open_parity, "regressions": regressions,
            "leaks": leaks, "closed": closed, "still_open": still_open,
            "remaining": dict(sorted(last_missing.items())), "tip": cur, "n": len(ledger)}


# Fixtures: declared example unit texts shaped like the overlay's two units.
_SYSTEM = """[Unit]
Description=Junior BitNet local inference (loopback)
After=network-online.target

[Service]
Type=simple
User=nobody
Group=nogroup
ExecStart=/usr/local/bin/junior-bitnetd
Restart=on-failure
Environment=JUNIOR_OFFLINE=1
Environment=JUNIOR_BIND=127.0.0.1:8765
NoNewPrivileges=yes
ProtectSystem=strict
ProtectHome=yes
PrivateTmp=yes
PrivateDevices=yes
ProtectKernelTunables=yes
ProtectKernelModules=yes
ProtectControlGroups=yes
RestrictSUIDSGID=yes
RestrictRealtime=yes
LockPersonality=yes
MemoryDenyWriteExecute=yes
RestrictAddressFamilies=AF_UNIX AF_INET AF_INET6
RestrictNamespaces=yes
SystemCallArchitectures=native
SystemCallFilter=@system-service
SystemCallFilter=~@privileged @keyring @resources @mount @reboot @swap @raw-io @module @debug
CapabilityBoundingSet=
AmbientCapabilities=
MemoryMax=2G
TasksMax=256

[Install]
WantedBy=multi-user.target
"""

_USER_OPEN = """[Unit]
Description=Junior BitNet local inference (user, loopback)
After=default.target

[Service]
Type=simple
ExecStart=/usr/local/bin/junior-bitnetd
Restart=on-failure
Environment=JUNIOR_OFFLINE=1
Environment=JUNIOR_BIND=127.0.0.1:8765
NoNewPrivileges=yes
ProtectSystem=strict
PrivateTmp=yes
MemoryDenyWriteExecute=yes
RestrictAddressFamilies=AF_UNIX AF_INET AF_INET6
RestrictNamespaces=yes
CapabilityBoundingSet=
AmbientCapabilities=
MemoryMax=2G
TasksMax=256

[Install]
WantedBy=default.target
"""

_PARITY_11 = (
    "ProtectHome=yes", "PrivateDevices=yes", "ProtectKernelTunables=yes",
    "ProtectKernelModules=yes", "ProtectControlGroups=yes", "RestrictSUIDSGID=yes",
    "RestrictRealtime=yes", "LockPersonality=yes", "SystemCallArchitectures=native",
    "SystemCallFilter=@system-service",
    "SystemCallFilter=~@privileged @keyring @resources @mount @reboot @swap @raw-io "
    "@module @debug",
)


def _user_closed() -> str:
    return _USER_OPEN.replace("TasksMax=256\n", "TasksMax=256\n" + "\n".join(_PARITY_11) + "\n")


def _pair(user: str, label: str = "bitnetd") -> dict[str, Any]:
    return {"label": label, "system_unit": _SYSTEM, "user_unit": user}


def self_check() -> dict[str, Any]:
    """Flags, bind, ports, pack vector 4a44, known close, 11-line gap, closure, tamper."""
    assert BIND == "127.0.0.1" and BITNETD.startswith(BIND + ":")
    assert PORTS == ("Home", "OSai", "FieldCore", "Flagstaff", "JuniorLLM")
    assert not (MINT or SOCKET or LAYER_ONE or FETCH or UE5_LAUNCH or MODEL_PULL)
    assert RELEASED == 0 and RATE == 0.05

    vec = pack([1, 0, -1, -1, 1, 0, 1])
    assert vec.hex() == "4a44", vec.hex()
    known = side_commit(GENESIS, vec, "home")
    assert known == "dd07dea74a142604", known

    o = audit_pair(_pair(_USER_OPEN))
    assert o["missing_count"] == 11 and tuple(o["missing"]) == _PARITY_11, o["missing"]
    assert o["trits"] == [1, 1, 1, 1, -1, 1, 1, 1, 1, 1] and not o["conforms"], o
    assert o["parity_lines"] == 21 and o["core_missing_user"] == [] and o["differs"] == []

    c = audit_pair(_pair(_user_closed()))
    assert c["conforms"] and c["trits"] == [1] * 10 and c["missing"] == [], c

    half = _user_closed().replace("LockPersonality=yes\n", "").replace("ProtectHome=yes\n", "")
    h = audit_pair(_pair(half))
    assert h["missing"] == ["ProtectHome=yes", "LockPersonality=yes"]

    weak = audit_pair(_pair(_user_closed().replace("ProtectHome=yes", "ProtectHome=read-only")))
    assert weak["differs"] == ["ProtectHome=read-only"] and weak["trits"][5] == -1
    nnp = audit_pair(_pair(_user_closed().replace("NoNewPrivileges=yes", "NoNewPrivileges=no")))
    assert nnp["weakened"] == ["NoNewPrivileges=no"] and nnp["trits"][3] == -1
    ident = audit_pair(_pair(_user_closed().replace("Type=simple", "Type=simple\nUser=nobody")))
    assert ident["leaks"] == ["user_unit_sets_identity"] and ident["trits"][9] == -1
    wide = audit_pair(_pair(_user_closed().replace("127.0.0.1:8765", "0.0.0.0:8765")))
    assert "wildcard_bind" in wide["leaks"] and wide["trits"][6] == -1
    online = audit_pair(_pair(_user_closed().replace("JUNIOR_OFFLINE=1", "JUNIOR_OFFLINE=0")))
    assert online["trits"][7] == -1
    tgt = audit_pair(_pair(_user_closed().replace("WantedBy=default.target",
                                                  "WantedBy=multi-user.target")))
    assert tgt["trits"][8] == -1
    nouser = audit_pair({"system_unit": _SYSTEM})
    assert nouser["trits"][1] == 0 and "parity" in nouser["open"] and not nouser["conforms"]
    junk = audit_pair({"system_unit": _SYSTEM, "user_unit": "not a unit"})
    assert junk["trits"][1] == -1

    ledger: list[dict[str, Any]] = []
    r0 = append_pair_receipt(ledger, GENESIS, _pair(_USER_OPEN))
    b0 = backfill_check(ledger)
    assert not b0["ok"] and b0["open_parity"] == [0] and b0["still_open"] == ["bitnetd"]
    assert b0["remaining"] == {"bitnetd": 11}
    r1 = append_pair_receipt(ledger, r0["commit"], _pair(half))
    r2 = append_pair_receipt(ledger, r1["commit"], _pair(_user_closed()))
    bf = backfill_check(ledger)
    assert bf["ok"] and bf["gaps"] == [] and bf["n"] == 3 and bf["tip"] == r2["commit"], bf
    assert bf["open_parity"] == [0, 1] and bf["closed"] == ["bitnetd"] and bf["regressions"] == []

    rg = list(ledger)
    append_pair_receipt(rg, r2["commit"], _pair(half))
    brg = backfill_check(rg)
    assert brg["regressions"] == [3] and brg["still_open"] == ["bitnetd"] and not brg["ok"]
    lk = list(ledger)
    append_pair_receipt(lk, r2["commit"], _pair(_user_closed().replace("Type=simple",
                                                                       "Type=simple\nGroup=x")))
    assert backfill_check(lk)["leaks"] == [3]

    t = [dict(x) for x in ledger]
    t[0] = dict(t[0], text=t[0]["text"].replace('"missing_count":11', '"missing_count":0'))
    assert 0 in backfill_check(t)["gaps"]
    m = [dict(x) for x in ledger]
    m[1] = dict(m[1], missing_count=0)
    assert 1 in backfill_check(m)["gaps"]
    r = [dict(x) for x in ledger]
    r[2] = dict(r[2], rate_commit=hashlib.sha256(b"x").hexdigest())
    rb = backfill_check(r)
    assert 2 in rb["gaps"] and not rb["ok"]
    assert 1 in backfill_check([ledger[0], ledger[2]])["gaps"]
    assert not backfill_check([])["ok"]

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
        "open_gap_lines": o["missing_count"],
        "tip": bf["tip"],
        "flags": {"mint": MINT, "socket": SOCKET, "layer_one": LAYER_ONE, "fetch": FETCH,
                  "ue5_launch": UE5_LAUNCH, "model_pull": MODEL_PULL, "released": RELEASED},
    }


def main(argv: list[str]) -> int:
    if "--selftest" in argv:
        print(json.dumps(self_check(), sort_keys=True))
        return 0
    pairs: list[dict[str, Any]] = [_pair(_USER_OPEN)]
    if "--facts" in argv:
        i = argv.index("--facts")
        if i + 1 >= len(argv):
            print("usage: --facts PAIR.json (one object or a list)", file=sys.stderr)
            return 2
        with open(argv[i + 1], "rb") as fh:
            data = json.loads(fh.read(MAX_READ).decode("utf-8", "replace"))
        pairs = data if isinstance(data, list) else [data]
    ledger: list[dict[str, Any]] = []
    prev = GENESIS
    for p in pairs:
        prev = append_pair_receipt(ledger, prev, p)["commit"]
    bf = backfill_check(ledger)
    print(json.dumps({"receipts": ledger, "backfill": bf}, sort_keys=True))
    return 0 if bf["ok"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
