"""juniorctl-on-PATH + Debian/Alpine base receipt ledger: side-commit + rate lock.

ROADMAP item: JuniorLLM docs/BETA_TO_OS.md "JuniorOS overlay", the juniorctl on
PATH and Debian/Alpine parts (Quant Chief pair B slot, 2026-10-18 05:09 MT).
os-release.junior and hardened bitnetd.service shipped earlier as separate
receipts; this file covers only the uncovered gap: a per-host receipt chain that
proves juniorctl actually resolves from the pinned PATH on a Debian or Alpine
base, plus a backfill gate that says which base still lacks a conforming receipt.
Pair B receipt and ledger piece; the matching handshake/port check belongs to
Handshake & Ports. New capability: it never imports, wraps, tests, rewrites, or
re-derives any team file (not rails/linux/install-overlay.sh, path_pin.py,
juniorctl.py, or any earlier stocksnode/web3node ledger).
Advances live-beta receipt chains / backfill_check at rate 0.05.

What it records: one receipt per host snapshot, built only from facts the caller
declares (base os-release text, package manager, login shell, the login PATH
before the profile.d pin, the executables present on that PATH with mode and
shebang, the declared package list, and JUNIOR_BIND). It replays the POSIX
profile.d pin (prepend /usr/local/bin once) twice in memory, then does a
first-match lookup of "juniorctl" over the pinned PATH. 10 trits:
base (ID/ID_LIKE names debian or alpine), pkg (apt on debian, apk on alpine),
shell (login shell sources /etc/profile.d), pinned (/usr/local/bin on PATH),
pin_once (exactly one /usr/local/bin after two pins), resolves (first hit is
/usr/local/bin/juniorctl, not shadowed), mode (owner/other exec, not
world-writable), shebang (python3 interpreter), python3 (declared in packages),
guard (no 0.0.0.0, loopback JUNIOR_BIND, no empty or relative PATH entry).
Offline: no subprocess, no os.environ reads, no filesystem walk, no network,
no sockets, no model pull, no UE5.

Stdlib only. Close: sha256(prev || pack || text)[:16] with i2s 2-bit pack
(0->0, 1->1, -1->2), MSB first, zero-padded (pack vector 4a44). Rate lock
commits rate 0.05 beside the pack as sha256(prev || pack || b"0.05") full
hexdigest (JuniorHome docs/JUNIORS_RATE.md).

Ports touched: Home, OSai, FieldCore, Flagstaff, JuniorLLM. Bind 127.0.0.1.

Run: python3 juniorctl_path_base_receipt_ledger.py --selftest
     python3 juniorctl_path_base_receipt_ledger.py --facts host.json
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
ROADMAP_ITEM = ("JuniorLLM docs/BETA_TO_OS.md JuniorOS overlay - "
                "juniorctl on PATH + Debian/Alpine part")
MAX_READ = 8192

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

PIN_DIR = "/usr/local/bin"
TOOL = "juniorctl"
BASES = ("debian", "alpine")
PKG_FOR_BASE = {"debian": "apt", "alpine": "apk"}
PROFILE_SHELLS = ("sh", "dash", "ash", "bash", "busybox", "ksh", "mksh")
GOOD_SHEBANGS = ("#!/usr/bin/env python3", "#!/usr/bin/python3")
LOOPBACK_HOSTS = ("127.0.0.1", "localhost", "::1")
TRIT_KEYS = ("base", "pkg", "shell", "pinned", "pin_once", "resolves",
             "mode", "shebang", "python3", "guard")
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


def base_of(os_release: str | None) -> tuple[str | None, int]:
    """Return (base, trit) from base /etc/os-release text: debian/alpine via ID or ID_LIKE."""
    if not os_release:
        return None, 0
    fields: dict[str, str] = {}
    for raw in os_release.splitlines():
        m = _LINE_RE.match(raw.strip())
        if m:
            v = m.group(2)
            if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
                v = v[1:-1]
            fields[m.group(1)] = v
    ids = [fields.get("ID", "")] + fields.get("ID_LIKE", "").split()
    for b in BASES:
        if b in ids:
            return b, 1
    return (fields.get("ID") or None), -1


def apply_pin(path: str) -> str:
    """In-memory replay of the POSIX profile.d pin: prepend PIN_DIR unless already present."""
    if (":" + PIN_DIR + ":") in (":" + path + ":"):
        return path
    return PIN_DIR + ":" + path if path else PIN_DIR


def resolve(path: str, executables: dict[str, Any]) -> str | None:
    """First-match lookup of TOOL over PATH entries, using declared executables only."""
    for d in path.split(":"):
        cand = (d.rstrip("/") or "") + "/" + TOOL
        if cand in executables:
            return cand
    return None


def _mode_trit(mode: Any) -> int:
    if mode is None:
        return 0
    try:
        m = int(str(mode), 8)
    except ValueError:
        return -1
    if m & 0o002 or not (m & 0o100) or not (m & 0o001):
        return -1
    return 1


def audit_host(facts: dict[str, Any]) -> dict[str, Any]:
    """Score one caller-declared host snapshot into 10 trits."""
    base, base_t = base_of(facts.get("os_release"))
    pkg = facts.get("pkg_manager")
    if pkg is None or base_t != 1:
        pkg_t = 0 if pkg is None else -1
    else:
        pkg_t = 1 if pkg == PKG_FOR_BASE[base] else -1
    shell = facts.get("login_shell")
    shell_t = 0 if not shell else (1 if shell.rsplit("/", 1)[-1] in PROFILE_SHELLS else -1)

    login_path = facts.get("login_path", "")
    once = apply_pin(login_path)
    twice = apply_pin(once)
    entries = twice.split(":")
    pinned_t = 1 if PIN_DIR in entries else -1
    pin_once_t = 1 if (once == twice and entries.count(PIN_DIR) == 1) else -1

    execs: dict[str, Any] = facts.get("executables") or {}
    hit = resolve(twice, execs)
    want = PIN_DIR + "/" + TOOL
    if not execs:
        resolves_t = 0
    else:
        resolves_t = 1 if hit == want else -1
    shadowed_by = hit if (hit and hit != want) else None
    info = execs.get(want) or {}
    mode_t = _mode_trit(info.get("mode")) if info else (0 if not execs else -1)
    sb = info.get("shebang")
    shebang_t = 0 if sb is None else (1 if sb.strip() in GOOD_SHEBANGS else -1)
    pkgs = facts.get("packages")
    py_t = 0 if pkgs is None else (1 if "python3" in pkgs else -1)

    leaks: list[str] = []
    blob = json.dumps(facts, sort_keys=True)
    if "0.0.0.0" in blob:
        leaks.append("wildcard_bind")
    jb = facts.get("junior_bind", BITNETD)
    host = jb.rsplit(":", 1)[0].strip("[]")
    if host not in LOOPBACK_HOSTS:
        leaks.append("non_loopback_junior_bind")
    for e in entries:
        if e == "" or e == ".":
            leaks.append("cwd_in_path")
            break
    for e in entries:
        if e and e != "." and not e.startswith("/"):
            leaks.append("relative_path_entry")
            break
    guard_t = -1 if leaks else 1

    trits = [base_t, pkg_t, shell_t, pinned_t, pin_once_t, resolves_t,
             mode_t, shebang_t, py_t, guard_t]
    missing = [k for k, t in zip(TRIT_KEYS, trits) if t == 0]
    wrong = [k for k, t in zip(TRIT_KEYS, trits) if t == -1]
    return {
        "item": ROADMAP_ITEM,
        "host": facts.get("host", "unnamed"),
        "base": base,
        "pinned_path": twice,
        "resolved": hit,
        "shadowed_by": shadowed_by,
        "leaks": leaks,
        "missing": missing,
        "wrong": wrong,
        "trits": trits,
        "conforms": not missing and not wrong,
    }


def audit_text(audit: dict[str, Any]) -> str:
    return json.dumps(audit, sort_keys=True, separators=(",", ":"))


def append_host_receipt(ledger: list[dict[str, Any]], prev: str,
                        facts: dict[str, Any]) -> dict[str, Any]:
    """Audit one host snapshot and append a receipt with side-commit and rate_commit."""
    audit = audit_host(facts)
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
    """Live-beta backfill gate. gaps: broken links; unresolved: juniorctl not first on
    pinned PATH; shadowed: another juniorctl wins; leaks: wildcard/non-loopback bind or
    cwd/relative PATH entries; bases_missing: debian/alpine with no conforming receipt."""
    gaps: list[int] = []
    unresolved: list[int] = []
    shadowed: list[int] = []
    leaks: list[int] = []
    covered: set[str] = set()
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
        if body.get("trits", [0] * 10)[5] != 1:
            unresolved.append(i)
        if body.get("shadowed_by"):
            shadowed.append(i)
        if body.get("leaks"):
            leaks.append(i)
        if body.get("conforms") and body.get("base") in BASES and i not in gaps:
            covered.add(body["base"])
        cur = link.get("commit", cur)
    bases_missing = [b for b in BASES if b not in covered]
    return {"ok": not gaps and not leaks and not bases_missing, "gaps": gaps,
            "unresolved": unresolved, "shadowed": shadowed, "leaks": leaks,
            "bases_missing": bases_missing, "tip": cur, "n": len(ledger)}


def _host(base: str) -> dict[str, Any]:
    deb = base == "debian"
    return {
        "host": f"{base}-overlay",
        "os_release": 'ID=debian\nNAME="Debian GNU/Linux"\n' if deb
        else 'ID=alpine\nNAME="Alpine Linux"\n',
        "pkg_manager": "apt" if deb else "apk",
        "login_shell": "/bin/sh",
        "login_path": "/usr/bin:/bin" if deb else "/usr/sbin:/usr/bin:/sbin:/bin",
        "executables": {"/usr/local/bin/juniorctl": {"mode": "0755",
                                                     "shebang": "#!/usr/bin/env python3"}},
        "packages": ["python3", "python3-venv", "systemd", "ca-certificates", "git"] if deb
        else ["python3", "ca-certificates", "git"],
        "junior_bind": BITNETD,
    }


def self_check() -> dict[str, Any]:
    """Flags, bind, ports, pack vector 4a44, known close, host audits, tamper/gap/base coverage."""
    assert BIND == "127.0.0.1" and BITNETD.startswith(BIND + ":")
    assert PORTS == ("Home", "OSai", "FieldCore", "Flagstaff", "JuniorLLM")
    assert not (MINT or SOCKET or LAYER_ONE or FETCH or UE5_LAUNCH or MODEL_PULL)
    assert RELEASED == 0 and RATE == 0.05

    vec = pack([1, 0, -1, -1, 1, 0, 1])
    assert vec.hex() == "4a44", vec.hex()
    known = side_commit(GENESIS, vec, "home")
    assert known == "dd07dea74a142604", known

    assert apply_pin("/usr/bin") == "/usr/local/bin:/usr/bin"
    assert apply_pin("/usr/local/bin:/usr/bin") == "/usr/local/bin:/usr/bin"
    assert apply_pin("") == "/usr/local/bin"

    d = audit_host(_host("debian"))
    a = audit_host(_host("alpine"))
    assert d["conforms"] and d["trits"] == [1] * 10 and d["base"] == "debian", d
    assert a["conforms"] and a["trits"] == [1] * 10 and a["base"] == "alpine", a

    ub = dict(_host("debian"), os_release="ID=ubuntu\n")
    u = audit_host(ub)
    assert u["trits"][0] == -1 and u["trits"][1] == -1 and not u["conforms"]
    like = audit_host(dict(_host("debian"), os_release='ID=raspbian\nID_LIKE="debian"\n'))
    assert like["base"] == "debian" and like["trits"][0] == 1
    wrongpkg = audit_host(dict(_host("alpine"), pkg_manager="apt"))
    assert wrongpkg["trits"][1] == -1
    fish = audit_host(dict(_host("debian"), login_shell="/usr/bin/fish"))
    assert fish["trits"][2] == -1

    sh = _host("debian")
    sh["login_path"] = "/home/j/.local/bin:/usr/bin"
    sh["executables"] = dict(sh["executables"], **{"/home/j/.local/bin/juniorctl": {"mode": "0755"}})
    s = audit_host(sh)
    assert s["resolved"] == "/usr/local/bin/juniorctl" and s["trits"][5] == 1
    sh2 = dict(sh, login_path="/home/j/.local/bin:/usr/local/bin:/usr/bin")
    s2 = audit_host(sh2)
    assert s2["shadowed_by"] == "/home/j/.local/bin/juniorctl" and s2["trits"][5] == -1

    dup = audit_host(dict(_host("debian"), login_path="/usr/local/bin:/usr/bin:/usr/local/bin"))
    assert dup["trits"][4] == -1
    gone = audit_host(dict(_host("debian"), executables={"/usr/bin/python3": {}}))
    assert gone["resolved"] is None and gone["trits"][5] == -1 and gone["trits"][6] == -1
    ww = _host("alpine")
    ww["executables"] = {"/usr/local/bin/juniorctl": {"mode": "0777", "shebang": "#!/bin/bash"}}
    w = audit_host(ww)
    assert w["trits"][6] == -1 and w["trits"][7] == -1
    nopy = audit_host(dict(_host("alpine"), packages=["git"]))
    assert nopy["trits"][8] == -1
    cwd = audit_host(dict(_host("debian"), login_path="/usr/bin::/bin"))
    assert "cwd_in_path" in cwd["leaks"] and cwd["trits"][9] == -1
    rel = audit_host(dict(_host("debian"), login_path="bin:/usr/bin"))
    assert "relative_path_entry" in rel["leaks"]
    wide = audit_host(dict(_host("debian"), junior_bind="0.0.0.0:8765"))
    assert wide["leaks"] == ["wildcard_bind", "non_loopback_junior_bind"]
    bare = audit_host({"login_path": "/usr/bin"})
    assert "base" in bare["missing"] and "resolves" in bare["missing"] and not bare["conforms"]

    ledger: list[dict[str, Any]] = []
    r0 = append_host_receipt(ledger, GENESIS, _host("debian"))
    half = backfill_check(ledger)
    assert half["bases_missing"] == ["alpine"] and not half["ok"]
    r1 = append_host_receipt(ledger, r0["commit"], _host("alpine"))
    r2 = append_host_receipt(ledger, r1["commit"], sh2)
    bf = backfill_check(ledger)
    assert bf["ok"] and bf["gaps"] == [] and bf["n"] == 3 and bf["tip"] == r2["commit"], bf
    assert bf["shadowed"] == [2] and bf["unresolved"] == [2] and bf["bases_missing"] == []

    lk = list(ledger)
    append_host_receipt(lk, r2["commit"], dict(_host("alpine"), login_path="/usr/bin::/bin"))
    bl = backfill_check(lk)
    assert bl["leaks"] == [3] and not bl["ok"] and bl["gaps"] == []

    t = [dict(x) for x in ledger]
    t[1] = dict(t[1], text=t[1]["text"].replace('"conforms":true', '"conforms":false'))
    tb = backfill_check(t)
    assert 1 in tb["gaps"] and "alpine" in tb["bases_missing"]
    r = [dict(x) for x in ledger]
    r[0] = dict(r[0], rate_commit=hashlib.sha256(b"x").hexdigest())
    assert 0 in backfill_check(r)["gaps"]
    assert 1 in backfill_check([ledger[0], ledger[2]])["gaps"]

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


def main(argv: list[str]) -> int:
    if "--selftest" in argv:
        print(json.dumps(self_check(), sort_keys=True))
        return 0
    hosts: list[dict[str, Any]] = [_host("debian"), _host("alpine")]
    if "--facts" in argv:
        i = argv.index("--facts")
        if i + 1 >= len(argv):
            print("usage: --facts HOSTS.json (one object or a list)", file=sys.stderr)
            return 2
        with open(argv[i + 1], "rb") as fh:
            data = json.loads(fh.read(MAX_READ).decode("utf-8", "replace"))
        hosts = data if isinstance(data, list) else [data]
    ledger: list[dict[str, Any]] = []
    prev = GENESIS
    for h in hosts:
        prev = append_host_receipt(ledger, prev, h)["commit"]
    bf = backfill_check(ledger)
    print(json.dumps({"receipts": ledger, "backfill": bf}, sort_keys=True))
    return 0 if bf["ok"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
