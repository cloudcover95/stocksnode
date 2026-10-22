"""16:45 daily audit receipt ledger: per-day section receipts + side-commit + rate lock.

Roadmap item: JuniorHome docs/ROADMAP.md, Automations (current) ON:
"16:45 daily audit" (writes docs/AUTOMATION_AUDIT.md), as named for pair B by
Quant Chief on 2026-10-22 14:14 MT (no team file yet; live beta steps 1-6
already covered). The matching handshake/port check belongs to Handshake &
Ports in a different file.

This is a new capability. It never imports, runs, wraps, tests, rewrites, or
re-derives any team file (including JuniorHome web3node/advance_daily_audit*.py,
scripts/advance_daily_audit_probe.py, ports/daily_audit_handshake.py, or my own
earlier ledgers). Those emit one fixed trit pack for the item; none of them
read what the audit actually wrote day by day.

The gap it fills, from caller-supplied AUTOMATION_AUDIT.md text (the audit's
own markdown, passed in as a string):
  1. Splits the doc into "# Automation audit YYYY-MM-DD ..." day sections.
  2. Per-day field receipts, one trit each (+1 holds, 0 not reported, -1 breaks):
     time (header says 16:45), tip (header carries an 8+ hex tip), audit_row
     (daily audit listed at daily 16:45), overnight (01:00 slot listed),
     slot19 (19:00 slot listed), weekly (Mon 17:00 weekly audit listed),
     paused_absent (no 07:00 / 13:00 row and no Friday weekly row: paused slots
     are not recreated), paused_note ("07:00 and 13:00 not scheduled" stated),
     no_actions (no CI yaml / GitHub Actions turned on), tz (America/Denver or
     MDT stated).
  3. One day receipt folding those trits, closing over the day's field chain tip;
     day receipts chain across days.
  4. backfill_check: chain + rate lock replay, failed fields per day, missing
     calendar days between first and last section, duplicate days, repeated
     tips across days, field regressions (+1 -> -1).
Offline: no subprocess, no file reads, no network, no sockets, no model pull,
no GGUF download, no UE5 launch. released 0, layer_one false.

Stdlib only. Close: sha256(prev || pack || text)[:16] with i2s 2-bit pack
(0->0, 1->1, -1->2), MSB first, zero-padded (pack vector 4a44). Rate lock
commits rate 0.05 beside the pack as sha256(prev || pack || b"0.05") full
hexdigest (JuniorHome docs/JUNIORS_RATE.md).

Ports touched: Home, OSai, FieldCore, Flagstaff, JuniorLLM. Bind 127.0.0.1.

Run: python3 daily_audit_1645_receipt_ledger.py --selftest
     python3 daily_audit_1645_receipt_ledger.py --run < AUTOMATION_AUDIT.md
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import json
import re
import sys

RATE = 0.05
RATE_BYTES = b"0.05"
GENESIS = "0" * 16
ROADMAP_ITEM = "JuniorHome docs/ROADMAP.md Automations ON: 16:45 daily audit"

MINT = False
SOCKET = False
LAYER_ONE = False
FETCH = False
UE5_LAUNCH = False
MODEL_PULL = False
SUBPROCESS = False
RELEASED = 0
BIND = "127.0.0.1"
PORTS = ("Home", "OSai", "FieldCore", "Flagstaff", "JuniorLLM")
COMPATIBLE_ENGINES = ("web3node", "stocksnode", "JuniorLLM", "BitNet-mlx")
CLOSE = "sha256(prev || pack || text)[:16]"

FIELDS = ("time", "tip", "audit_row", "overnight", "slot19", "weekly",
          "paused_absent", "paused_note", "no_actions", "tz")

_ENC = {0: 0, 1: 1, -1: 2}
_VEC_TRITS = (1, 0, -1, -1, 1, 0, 1)
_VEC_PACK = "4a44"
_VEC_COMMIT = "e038848e2422d22a"  # side_commit(GENESIS, pack(_VEC_TRITS), "stocks")

_HDR = re.compile(r"^# Automation audit (\d{4}-\d{2}-\d{2})(.*)$", re.M)
_TIP = re.compile(r"\btip ([0-9a-f]{8,40})\b")


def pack(trits) -> bytes:
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


def side_commit(prev: str, pk: bytes, text: str) -> str:
    return hashlib.sha256(prev.encode() + pk + text.encode()).hexdigest()[:16]


def rate_commit(prev: str, pk: bytes) -> str:
    return hashlib.sha256(prev.encode() + pk + RATE_BYTES).hexdigest()


def rate_lock(level: float, x: float) -> float:
    return level + RATE * (x - level)


def split_days(doc: str) -> list[tuple[str, str, str]]:
    """-> [(date, header_rest, body)] in document order."""
    hs = list(_HDR.finditer(doc))
    out = []
    for i, m in enumerate(hs):
        end = hs[i + 1].start() if i + 1 < len(hs) else len(doc)
        out.append((m.group(1), m.group(2), doc[m.end():end]))
    return out


def _rows(body: str) -> list[str]:
    return [ln.lower() for ln in body.splitlines()
            if ln.strip().startswith("|") and not set(ln.strip()) <= set("|-: ")]


def day_fields(date: str, rest: str, body: str) -> dict:
    rows = _rows(body)
    low = body.lower()
    rest_l = rest.lower()
    f = {}
    f["time"] = 1 if "16:45" in rest else 0
    f["tip"] = 1 if _TIP.search(rest_l) else 0
    f["audit_row"] = 1 if any("daily audit" in r and "16:45" in r for r in rows) else (
        -1 if any("daily audit" in r for r in rows) else 0)
    f["overnight"] = 1 if any("01:00" in r for r in rows) else 0
    f["slot19"] = 1 if any("19:00" in r for r in rows) else 0
    f["weekly"] = 1 if any("weekly audit" in r and "mon 17:00" in r for r in rows) else 0
    bad = any(("07:00" in r or "13:00" in r or ("fri" in r and "weekly" in r))
              and "not scheduled" not in r and "paused" not in r for r in rows)
    f["paused_absent"] = -1 if bad else (1 if rows else 0)
    f["paused_note"] = 1 if ("07:00 and 13:00" in low and "not scheduled" in low) else 0
    on_ci = any(re.search(r"(actions|ci yaml|workflow)[^\n]*\b(enabled|turned on|added)\b", ln)
                and not re.search(r"\b(no|not|never|off|manual-only)\b", ln)
                for ln in low.splitlines())
    f["no_actions"] = -1 if on_ci else 1
    f["tz"] = 1 if ("america/denver" in low or "mdt" in rest_l) else 0
    return f


def build_ledger(doc: str, prev: str = GENESIS) -> dict:
    days = []
    lock = 0.0
    for date, rest, body in split_days(doc):
        fl = day_fields(date, rest, body)
        fprev = prev
        for name in FIELDS:
            fprev = side_commit(fprev, pack([fl[name]]), f"{date}|{name}")
        trits = [fl[n] for n in FIELDS]
        pk = pack(trits)
        tipm = _TIP.search(rest.lower())
        text = f"audit1645|{date}|{tipm.group(1) if tipm else '-'}|{fprev}"
        c = side_commit(prev, pk, text)
        lock = rate_lock(lock, sum(trits) / len(trits))
        days.append({"date": date, "fields": fl, "field_tip": fprev, "text": text,
                     "prev": prev, "commit": c, "rate_commit": rate_commit(prev, pk),
                     "lock": lock, "tip": tipm.group(1) if tipm else None})
        prev = c
    return {"item": ROADMAP_ITEM, "rate": RATE, "bind": BIND, "days": days, "tip": prev}


def backfill_check(ledger: dict, prev: str = GENESIS) -> dict:
    ok = True
    lock = 0.0
    failed, regressions = {}, []
    last = {}
    for i, d in enumerate(ledger["days"]):
        trits = [d["fields"][n] for n in FIELDS]
        pk = pack(trits)
        fp = prev
        for name in FIELDS:
            fp = side_commit(fp, pack([d["fields"][name]]), f"{d['date']}|{name}")
        if (d["prev"] != prev or fp != d["field_tip"]
                or side_commit(prev, pk, d["text"]) != d["commit"]
                or rate_commit(prev, pk) != d["rate_commit"]
                or not d["text"].endswith(fp)):
            ok = False
            return {"ok": False, "at": i, "reason": "chain"}
        lock = rate_lock(lock, sum(trits) / len(trits))
        if abs(lock - d["lock"]) > 1e-12:
            return {"ok": False, "at": i, "reason": "rate_lock"}
        bad = [n for n in FIELDS if d["fields"][n] == -1]
        if bad:
            failed[d["date"]] = bad
        for n in FIELDS:
            if last.get(n) == 1 and d["fields"][n] == -1:
                regressions.append(f"{d['date']}:{n}")
        last = d["fields"]
        prev = d["commit"]
    dates = [d["date"] for d in ledger["days"]]
    dup = sorted({x for x in dates if dates.count(x) > 1})
    missing = []
    if dates:
        ds = sorted({_dt.date.fromisoformat(x) for x in dates})
        cur = ds[0]
        have = set(ds)
        while cur <= ds[-1]:
            if cur not in have:
                missing.append(cur.isoformat())
            cur += _dt.timedelta(days=1)
    tips = [d["tip"] for d in ledger["days"] if d["tip"]]
    rep = sorted({t for t in tips if tips.count(t) > 1})
    clean = ok and not failed and not regressions and not dup and not rep
    return {"ok": ok, "clean": clean, "n": len(dates), "tip": prev, "failed": failed,
            "missing_days": missing, "duplicate_days": dup, "repeated_tips": rep,
            "regressions": regressions, "rate": RATE}


_SAMPLE = """# Automation audit 2026-10-11

| Slot | Task | State |
|---|---|---|
| 01:00 | overnight | active |
| 19:00 | slot 19:00 | active |
| 16:45 | daily audit | active |

07:00 and 13:00 are not scheduled.

# Automation audit 2026-10-12 16:45 MDT (tip 27f8b7a1)

| Name | Schedule (MDT) | Notes |
|---|---|---|
| JuniorCloud overnight build | daily 01:00 | guard |
| JuniorCloud daily audit | daily 16:45 | this run |
| JuniorCloud slot 19:00 | daily 19:00 | guard |
| JuniorCloud weekly audit | Mon 17:00 | WEEKLY_AUDIT.md |

07:00 and 13:00 not scheduled. America/Denver.
| GitHub Actions | no new workflows added; CI manual-only |

# Automation audit 2026-10-14 16:45 MDT (tip 0cd0a810)

| Name | Schedule (MDT) | Notes |
|---|---|---|
| JuniorCloud overnight build | daily 01:00 | guard |
| JuniorCloud daily audit | daily 16:45 | this run |
| JuniorCloud slot 19:00 | daily 19:00 | guard |
| JuniorCloud weekly audit | Mon 17:00 | WEEKLY_AUDIT.md |

07:00 and 13:00 not scheduled. America/Denver.
"""


def self_check() -> dict:
    assert BIND == "127.0.0.1" and RELEASED == 0
    assert PORTS == ("Home", "OSai", "FieldCore", "Flagstaff", "JuniorLLM")
    assert not (MINT or SOCKET or LAYER_ONE or FETCH or UE5_LAUNCH or MODEL_PULL or SUBPROCESS)
    assert abs(RATE - 0.05) < 1e-12 and abs(rate_lock(0.0, 1.0) - 0.05) < 1e-12
    p = pack(_VEC_TRITS)
    assert p.hex() == _VEC_PACK and side_commit(GENESIS, p, "stocks") == _VEC_COMMIT
    assert rate_commit(GENESIS, p) == hashlib.sha256(GENESIS.encode() + p + b"0.05").hexdigest()
    led = build_ledger(_SAMPLE)
    assert [d["date"] for d in led["days"]] == ["2026-10-11", "2026-10-12", "2026-10-14"]
    assert led["days"][1]["fields"] == {n: 1 for n in FIELDS}
    assert led["days"][0]["fields"]["time"] == 0 and led["days"][0]["fields"]["tip"] == 0
    bc = backfill_check(led)
    assert bc["ok"] and bc["clean"] and bc["missing_days"] == ["2026-10-13"]
    # paused slot recreated -> -1 and a regression from the prior +1 day
    bad_doc = _SAMPLE + """
# Automation audit 2026-10-15 16:45 MDT (tip 0cd0a810)

| Name | Schedule (MDT) | Notes |
|---|---|---|
| slot 07:00 | daily 07:00 | active |
| JuniorCloud daily audit | daily 17:30 | moved |
| GitHub Actions | ci yaml added |
"""
    b = backfill_check(build_ledger(bad_doc))
    assert b["ok"] and not b["clean"]
    assert "paused_absent" in b["failed"]["2026-10-15"] and "audit_row" in b["failed"]["2026-10-15"]
    assert "no_actions" in b["failed"]["2026-10-15"]
    assert "2026-10-15:paused_absent" in b["regressions"] and b["repeated_tips"] == ["0cd0a810"]
    t = build_ledger(_SAMPLE)
    t["days"][1]["fields"]["tz"] = 0
    assert backfill_check(t) == {"ok": False, "at": 1, "reason": "chain"}
    t = build_ledger(_SAMPLE)
    t["days"][2]["lock"] += 0.01
    assert backfill_check(t) == {"ok": False, "at": 2, "reason": "rate_lock"}
    return {"ok": True, "item": ROADMAP_ITEM, "rate": RATE, "close": CLOSE, "bind": BIND,
            "ports": list(PORTS), "engines": list(COMPATIBLE_ENGINES), "pack": _VEC_PACK,
            "vec_commit": _VEC_COMMIT, "tip": led["tip"]}


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        print(json.dumps(self_check()))
    elif "--run" in sys.argv:
        led = build_ledger(sys.stdin.read())
        print(json.dumps({"ledger": led, "backfill_check": backfill_check(led)}, indent=1))
    else:
        print(__doc__)
