"""JuniorOS overlay "No OSWorld score. No kernel blob." staged-tree receipt ledger.

ROADMAP item: JuniorLLM docs/BETA_TO_OS.md "JuniorOS overlay", closing clause
"No OSWorld score. No kernel blob." (Quant Chief pair B slot, 2026-10-19 02:09 MT,
remaining overlay gaps only; Quant Verifier: the thinnest overlay limit).
os-release.junior (stocksnode f49707c only guards its own keys), bitnetd.service,
juniorctl on PATH, Debian/Alpine and the user-unit parity part already landed and
are not re-derived. Handshake & Ports' JuniorLLM
ports/overlay_no_kernel_blob_osworld_handshake.py reads the installer scripts;
this file is the other half: a receipt chain over what a staged overlay tree
(DEST) actually holds, so every snapshot of the whole tree gets a side-committed
receipt attesting no kernel blob and no OSWorld score claim, and backfill_check
only goes green once the latest receipt per label is clean with no regression.
New capability: it never imports, wraps, tests, rewrites, or re-derives any team
file (not rails/linux/install-overlay.sh, debian/stage_overlay.sh, the handshake
above, or any earlier stocksnode/web3node ledger).
Advances live-beta receipt chains / backfill_check at rate 0.05.

What it records, from an inventory the caller declares ({"path", "size",
"head_hex" or "text", optional "link"}) or from --dest DIR (read-only walk, at
most 4096 head bytes per file and 65536 bytes per text file, symlinks not
followed). 10 trits:
  manifest      inventory parsed and non-empty
  contained     every path relative, no "..", no absolute symlink escape
  kernel_path   no /boot, vmlinuz/vmlinux/bzImage/zImage/uImage/Image,
                System.map, boot config-*, *.dtb/*.dtbo, EFI stubs, lib/firmware
  kernel_magic  no head bytes of a kernel image: x86 "HdrS"@0x202, arm64
                "ARM\\x64"@0x38, uImage 27051956, ARM zImage 016f2818@0x24,
                FDT d00dfeed (0 = some binary had no head declared)
  modules       no *.ko[.xz|.zst|.gz], no lib/modules, no ELF ET_REL object
  initramfs     no initrd*/initramfs* and no cpio newc 070701/070702 head
  osworld       every OSWorld mention is a negation with no number, and no
                OSWORLD* key in any key=value text
  gguf          no *.gguf and no "GGUF" magic staged in the overlay (I2_S 2B4T
                only if the operator's GGUF is already on disk, never shipped)
  oversize      no non-text file >= 4 MiB (kernel-sized opaque blob)
  guard         no 0.0.0.0, no docker.sock in any staged text
Offline: no subprocess, no os.environ reads, no network, no sockets, no model
pull, no UE5.

Stdlib only. Close: sha256(prev || pack || text)[:16] with i2s 2-bit pack
(0->0, 1->1, -1->2), MSB first, zero-padded (pack vector 4a44). Rate lock
commits rate 0.05 beside the pack as sha256(prev || pack || b"0.05") full
hexdigest (JuniorHome docs/JUNIORS_RATE.md).

Ports touched: Home, OSai, FieldCore, Flagstaff, JuniorLLM. Bind 127.0.0.1.

Run: python3 overlay_no_kernel_osworld_receipt_ledger.py --selftest
     python3 overlay_no_kernel_osworld_receipt_ledger.py --facts tree.json
       (tree.json: {"label", "files": [...]} or a list of them)
     python3 overlay_no_kernel_osworld_receipt_ledger.py --dest /opt/junioros
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from typing import Any

RATE = 0.05
RATE_BYTES = b"0.05"
GENESIS = "0" * 16
ROADMAP_ITEM = ("JuniorLLM docs/BETA_TO_OS.md JuniorOS overlay - No OSWorld score. "
                "No kernel blob. (staged-tree receipt)")
MAX_READ = 65536
HEAD_READ = 4096
OVERSIZE = 4 * 1024 * 1024

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

TRIT_KEYS = ("manifest", "contained", "kernel_path", "kernel_magic", "modules",
             "initramfs", "osworld", "gguf", "oversize", "guard")
_TRIT_TO_BITS = {0: 0, 1: 1, -1: 2}

_KERNEL_NAME = re.compile(
    r"^(vmlinuz|vmlinux|bzImage|zImage|uImage|Image|Image\.gz|kernel\d*\.img|System\.map)"
    r"([-._].*)?$")
_MODULE_NAME = re.compile(r"\.ko(\.(xz|zst|gz))?$")
_INITRD_NAME = re.compile(r"^(initrd|initramfs)([-._].*)?$")
_KERNEL_DIRS = ("boot/", "lib/firmware/", "usr/lib/firmware/", "efi/", "boot/efi/")
_MODULE_DIRS = ("lib/modules/", "usr/lib/modules/")
_OSW = re.compile(r"os[\s_-]?world", re.I)
_NEG = re.compile(r"\b(no|not|never|without|none)\b", re.I)
_NUM = re.compile(r"\d")


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


def _norm(path: str) -> str:
    p = path.replace("\\", "/")
    return p[2:] if p.startswith("./") else p


def _head(entry: dict[str, Any]) -> bytes | None:
    if entry.get("head_hex") is not None:
        try:
            return bytes.fromhex(str(entry["head_hex"]))[:HEAD_READ]
        except ValueError:
            return None
    if entry.get("text") is not None:
        return str(entry["text"]).encode("utf-8")[:HEAD_READ]
    return None


def _at(head: bytes, off: int, magic: bytes) -> bool:
    return len(head) >= off + len(magic) and head[off:off + len(magic)] == magic


def kernel_magic(head: bytes) -> str | None:
    """Name the kernel-image family a head matches, or None."""
    if _at(head, 0x202, b"HdrS"):
        return "x86_bzimage"
    if _at(head, 0x38, b"ARM\x64"):
        return "arm64_image"
    if _at(head, 0, bytes.fromhex("27051956")):
        return "uimage"
    if _at(head, 0x24, bytes.fromhex("18286f01")):
        return "arm_zimage"
    if _at(head, 0, bytes.fromhex("d00dfeed")):
        return "fdt_dtb"
    return None


def _is_text(entry: dict[str, Any], head: bytes | None) -> bool:
    if entry.get("text") is not None:
        return True
    if head is None or b"\x00" in head:
        return False
    try:
        head.decode("utf-8")
    except UnicodeDecodeError:
        return False
    return True


def osworld_claims(text: str) -> list[str]:
    """Sentences naming OSWorld that are not a bare negation, or carry any number."""
    out: list[str] = []
    for sent in re.split(r"[.\n;]", text):
        if not _OSW.search(sent):
            continue
        s = sent.strip()
        key = s.split("=", 1)[0].strip()
        if "=" in s and _OSW.search(key):
            out.append(s[:120])
        elif _NUM.search(s) or not _NEG.search(s):
            out.append(s[:120])
    return out


def audit_tree(facts: dict[str, Any]) -> dict[str, Any]:
    """Score one caller-declared staged overlay inventory into 10 trits."""
    files = facts.get("files")
    label = facts.get("label", "junioros")
    ok_manifest = isinstance(files, list) and bool(files) and all(
        isinstance(f, dict) and isinstance(f.get("path"), str) for f in files)
    find: dict[str, list[str]] = {k: [] for k in TRIT_KEYS}
    unknown_heads: list[str] = []
    if ok_manifest:
        for f in files:
            p = _norm(f["path"])
            base = p.rsplit("/", 1)[-1]
            link = f.get("link")
            if p.startswith("/") or ".." in p.split("/") or (
                    isinstance(link, str) and (link.startswith("/") or ".." in link.split("/"))):
                find["contained"].append(p)
            targets = [p] + ([_norm(link).lstrip("/")] if isinstance(link, str) else [])
            for t in targets:
                tb = t.rsplit("/", 1)[-1]
                if (t.startswith(_KERNEL_DIRS) or _KERNEL_NAME.match(tb)
                        or tb.endswith((".dtb", ".dtbo")) or tb.lower().endswith(".efi")
                        or (t.startswith("boot") and tb.startswith("config-"))):
                    find["kernel_path"].append(t)
                if t.startswith(_MODULE_DIRS) or _MODULE_NAME.search(tb):
                    find["modules"].append(t)
                if _INITRD_NAME.match(tb):
                    find["initramfs"].append(t)
                if tb.lower().endswith(".gguf"):
                    find["gguf"].append(t)
            if isinstance(link, str):
                continue
            head = _head(f)
            text_ok = _is_text(f, head)
            if head is None:
                unknown_heads.append(p)
            else:
                fam = kernel_magic(head)
                if fam:
                    find["kernel_magic"].append(p + ":" + fam)
                if _at(head, 0, b"\x7fELF") and len(head) >= 18 and head[16] == 1:
                    find["modules"].append(p + ":elf_rel")
                if _at(head, 0, b"070701") or _at(head, 0, b"070702"):
                    find["initramfs"].append(p + ":cpio_newc")
                if _at(head, 0, b"GGUF"):
                    find["gguf"].append(p + ":gguf_magic")
            size = int(f.get("size") or 0)
            if not text_ok and size >= OVERSIZE:
                find["oversize"].append(p)
            if f.get("text") is not None:
                txt = str(f["text"])
                for c in osworld_claims(txt):
                    find["osworld"].append(p + ": " + c)
                if "0.0.0.0" in txt:
                    find["guard"].append(p + ":wildcard_bind")
                if "docker.sock" in txt:
                    find["guard"].append(p + ":docker_socket")
    trits: list[int] = []
    for k in TRIT_KEYS:
        if k == "manifest":
            trits.append(1 if ok_manifest else (0 if files is None else -1))
        elif not ok_manifest:
            trits.append(0)
        elif find[k]:
            trits.append(-1)
        elif k == "kernel_magic" and unknown_heads:
            trits.append(0)
        else:
            trits.append(1)
    findings = {k: sorted(set(v)) for k, v in find.items() if v}
    count = sum(len(v) for v in findings.values())
    blob = any(k in findings for k in ("kernel_path", "kernel_magic", "modules",
                                       "initramfs", "oversize"))
    open_keys = [k for k, t in zip(TRIT_KEYS, trits) if t == 0]
    wrong = [k for k, t in zip(TRIT_KEYS, trits) if t == -1]
    return {
        "item": ROADMAP_ITEM,
        "label": label,
        "files": len(files) if isinstance(files, list) else 0,
        "findings": findings,
        "finding_count": count,
        "kernel_blob": blob,
        "osworld_claim": "osworld" in findings,
        "unknown_heads": sorted(unknown_heads),
        "open": open_keys,
        "wrong": wrong,
        "trits": trits,
        "conforms": not open_keys and not wrong,
    }


def audit_text(audit: dict[str, Any]) -> str:
    return json.dumps(audit, sort_keys=True, separators=(",", ":"))


def append_tree_receipt(ledger: list[dict[str, Any]], prev: str,
                        facts: dict[str, Any]) -> dict[str, Any]:
    """Audit one staged-tree snapshot and append a receipt with side-commit and rate_commit."""
    audit = audit_tree(facts)
    trits = list(audit["trits"])
    body = audit_text(audit)
    pk = pack(trits)
    link = {
        "prev": prev,
        "trits": trits,
        "text": body,
        "conforms": audit["conforms"],
        "finding_count": audit["finding_count"],
        "commit": side_commit(prev, pk, body),
        "rate_commit": rate_lock_commit(prev, pk),
        "rate": RATE,
    }
    ledger.append(link)
    return link


def backfill_check(ledger: list[dict[str, Any]], prev: str = GENESIS) -> dict[str, Any]:
    """Live-beta backfill gate. gaps: broken links; blobs: receipts that saw a kernel
    blob; claims: receipts that saw an OSWorld score claim; regressions: a label's
    finding_count grew; leaks: wildcard bind or docker.sock; closed / still_open:
    labels whose latest valid receipt conforms / does not."""
    gaps: list[int] = []
    blobs: list[int] = []
    claims: list[int] = []
    regressions: list[int] = []
    leaks: list[int] = []
    last: dict[str, int] = {}
    latest: dict[str, bool] = {}
    cur = prev
    for i, link in enumerate(ledger):
        try:
            pk = pack(link["trits"])
            body = json.loads(link["text"])
        except (KeyError, ValueError, TypeError):
            gaps.append(i)
            cur = link.get("commit", cur) if isinstance(link, dict) else cur
            continue
        if (
            link.get("prev") != cur
            or link.get("commit") != side_commit(cur, pk, link["text"])
            or link.get("rate_commit") != rate_lock_commit(cur, pk)
            or link.get("rate") != RATE
            or body.get("trits") != link["trits"]
            or body.get("conforms") != link.get("conforms")
            or body.get("finding_count") != link.get("finding_count")
        ):
            gaps.append(i)
            cur = link.get("commit", cur)
            continue
        label = body.get("label", "junioros")
        fc = int(body.get("finding_count", 0))
        if body.get("kernel_blob"):
            blobs.append(i)
        if body.get("osworld_claim"):
            claims.append(i)
        if "guard" in body.get("findings", {}):
            leaks.append(i)
        if label in last and fc > last[label]:
            regressions.append(i)
        last[label] = fc
        latest[label] = bool(body.get("conforms"))
        cur = link.get("commit", cur)
    closed = sorted(k for k, v in latest.items() if v)
    still_open = sorted(k for k, v in latest.items() if not v)
    ok = bool(latest) and not gaps and not regressions and not still_open
    return {"ok": ok, "gaps": gaps, "blobs": blobs, "claims": claims,
            "regressions": regressions, "leaks": leaks, "closed": closed,
            "still_open": still_open, "remaining": dict(sorted(last.items())),
            "tip": cur, "n": len(ledger)}


def inventory_dest(dest: str, label: str = "junioros") -> dict[str, Any]:
    """Read-only bounded walk of a staged overlay DEST into an inventory (no symlink follow)."""
    files: list[dict[str, Any]] = []
    for root, dirs, names in os.walk(dest, followlinks=False):
        dirs.sort()
        for name in sorted(names) + [d for d in dirs if os.path.islink(os.path.join(root, d))]:
            full = os.path.join(root, name)
            rel = os.path.relpath(full, dest).replace(os.sep, "/")
            if os.path.islink(full):
                files.append({"path": rel, "size": 0, "link": os.readlink(full)})
                continue
            size = os.path.getsize(full)
            with open(full, "rb") as fh:
                head = fh.read(HEAD_READ)
                entry: dict[str, Any] = {"path": rel, "size": size}
                text = None
                if b"\x00" not in head and size <= MAX_READ:
                    raw = head + fh.read(MAX_READ - len(head))
                    try:
                        text = raw.decode("utf-8")
                    except UnicodeDecodeError:
                        text = None
            if text is not None:
                entry["text"] = text
            else:
                entry["head_hex"] = head.hex()
            files.append(entry)
    return {"label": label, "files": files}


# Fixtures: declared example inventory shaped like install-overlay.sh's DEST tree.
_OS_RELEASE = ('NAME="JuniorOS overlay"\nID=junioros\nID_LIKE=debian\nVARIANT_ID=overlay\n'
               'JUNIOR_BITNETD=127.0.0.1:8765\nJUNIOR_OFFLINE=1\n')
_README = ("JuniorOS overlay OCI bundle. Loopback only.\n"
           "No OSWorld score. No kernel blob. Host kernel stays vendor.\n")
_KCONFIG = "# Fragment only. Merge against a vendor kernel. Do not ship vmlinuz.\nCONFIG_SECCOMP=y\n"


def _clean() -> list[dict[str, Any]]:
    return [
        {"path": "etc/os-release.junior", "size": len(_OS_RELEASE), "text": _OS_RELEASE},
        {"path": "usr/lib/os-release.junior", "size": len(_OS_RELEASE), "text": _OS_RELEASE},
        {"path": "etc/systemd/system/bitnetd.service", "size": 120,
         "text": "[Service]\nEnvironment=JUNIOR_BIND=127.0.0.1:8765\n"},
        {"path": "usr/lib/systemd/user/bitnetd.service", "size": 110,
         "text": "[Service]\nEnvironment=JUNIOR_BIND=127.0.0.1:8765\n"},
        {"path": "usr/local/bin/junior-bitnetd", "size": 40, "text": "#!/bin/sh\nexec true\n"},
        {"path": "usr/local/bin/juniorctl", "size": 40, "text": "#!/usr/bin/env python3\n"},
        {"path": "etc/profile.d/junioros.sh", "size": 60, "text": 'PATH="/usr/local/bin:$PATH"\n'},
        {"path": "usr/lib/junioros/oci/README.md", "size": len(_README), "text": _README},
        {"path": "usr/lib/junioros/oci/config.json", "size": 30, "text": '{"ociVersion":"1.0.2"}'},
        {"path": "usr/lib/junioros/kconfig.junior", "size": len(_KCONFIG), "text": _KCONFIG},
        {"path": "usr/lib/junioros/i2s.bin", "size": 64, "head_hex": "4a54523100" + "00" * 11},
    ]


def _tree(files: list[dict[str, Any]], label: str = "junioros") -> dict[str, Any]:
    return {"label": label, "files": files}


def _bz() -> str:
    h = bytearray(0x210)
    h[0:2] = b"MZ"
    h[0x202:0x206] = b"HdrS"
    return h.hex()


def self_check() -> dict[str, Any]:
    """Flags, bind, ports, pack vector 4a44, known close, every finding family, ledger, tamper."""
    assert BIND == "127.0.0.1" and BITNETD.startswith(BIND + ":")
    assert PORTS == ("Home", "OSai", "FieldCore", "Flagstaff", "JuniorLLM")
    assert not (MINT or SOCKET or LAYER_ONE or FETCH or UE5_LAUNCH or MODEL_PULL)
    assert RELEASED == 0 and RATE == 0.05

    vec = pack([1, 0, -1, -1, 1, 0, 1])
    assert vec.hex() == "4a44", vec.hex()
    known = side_commit(GENESIS, vec, "home")
    assert known == "dd07dea74a142604", known

    c = audit_tree(_tree(_clean()))
    assert c["conforms"] and c["trits"] == [1] * 10 and c["findings"] == {}, c

    def one(extra: dict[str, Any] | None = None, edit=None) -> dict[str, Any]:
        fs = _clean()
        if edit:
            fs = edit(fs)
        if extra:
            fs.append(extra)
        return audit_tree(_tree(fs))

    k = one({"path": "boot/vmlinuz-6.8-junior", "size": 9 << 20, "head_hex": _bz()})
    assert k["trits"][2] == -1 and k["trits"][3] == -1 and k["trits"][8] == -1, k
    assert k["kernel_blob"] and "boot/vmlinuz-6.8-junior:x86_bzimage" in k["findings"]["kernel_magic"]
    hid = one({"path": "usr/lib/junioros/payload.bin", "size": 100,
               "head_hex": "00" * 0x38 + "41524d64"})
    assert hid["findings"]["kernel_magic"] == ["usr/lib/junioros/payload.bin:arm64_image"]
    assert hid["trits"][2] == 1 and hid["trits"][3] == -1
    ub = one({"path": "usr/lib/junioros/u.bin", "size": 10, "head_hex": "27051956" + "00" * 8})
    assert ub["trits"][3] == -1
    dtb = one({"path": "usr/lib/junioros/board.dtb", "size": 10, "head_hex": "d00dfeed00"})
    assert dtb["trits"][2] == -1 and dtb["trits"][3] == -1
    ko = one({"path": "lib/modules/6.8/extra/trit.ko.zst", "size": 10, "head_hex": "28b52ffd"})
    assert ko["trits"][4] == -1 and ko["kernel_blob"]
    rel = one({"path": "usr/lib/junioros/trit.o", "size": 64,
               "head_hex": "7f454c46020101" + "00" * 9 + "0100"})
    assert rel["findings"]["modules"] == ["usr/lib/junioros/trit.o:elf_rel"]
    exe = one({"path": "usr/lib/junioros/i2sd", "size": 64,
               "head_hex": "7f454c46020101" + "00" * 9 + "0300"})
    assert exe["conforms"], exe
    ird = one({"path": "usr/lib/junioros/initrd.img-6.8", "size": 10, "head_hex": "1f8b"})
    assert ird["trits"][5] == -1
    cpio = one({"path": "usr/lib/junioros/root.cpio", "size": 10, "head_hex": b"070701".hex()})
    assert cpio["findings"]["initramfs"] == ["usr/lib/junioros/root.cpio:cpio_newc"]
    lk = one({"path": "usr/lib/junioros/kernel", "size": 0, "link": "/boot/vmlinuz"})
    assert lk["trits"][1] == -1 and lk["trits"][2] == -1
    esc = one({"path": "../etc/shadow", "size": 1, "text": "x"})
    assert esc["trits"][1] == -1
    gg = one({"path": "usr/lib/junioros/model.gguf", "size": 10, "head_hex": b"GGUF".hex()})
    assert gg["trits"][7] == -1 and len(gg["findings"]["gguf"]) == 2
    big = one({"path": "usr/lib/junioros/blob.bin", "size": 5 << 20, "head_hex": "00ff00ff"})
    assert big["trits"][8] == -1 and big["kernel_blob"]
    unk = one({"path": "usr/lib/junioros/opaque", "size": 10})
    assert unk["trits"][3] == 0 and "kernel_magic" in unk["open"] and not unk["conforms"]

    def readme(txt: str):
        def ed(fs):
            fs[7] = dict(fs[7], text=txt)
            return fs
        return ed
    sc = one(edit=readme("JuniorOS overlay scores 38.1% on OSWorld.\n"))
    assert sc["osworld_claim"] and sc["trits"][6] == -1, sc
    neg_num = one(edit=readme("No OSWorld score above 0 yet.\n"))
    assert neg_num["trits"][6] == -1
    bare = one(edit=readme("Benchmarked against OSWorld.\n"))
    assert bare["trits"][6] == -1
    neg = one(edit=readme("No OSWorld score. Not run on OS-World either.\n"))
    assert neg["conforms"], neg
    key = one(edit=lambda fs: fs[:0] + [dict(fs[0], text=_OS_RELEASE + "OSWORLD_SCORE=none\n")] + fs[1:])
    assert key["trits"][6] == -1
    wide = one(edit=lambda fs: fs[:2] + [dict(fs[2], text="JUNIOR_BIND=0.0.0.0:8765\n")] + fs[3:])
    assert wide["trits"][9] == -1
    assert audit_tree({"label": "x"})["trits"][0] == 0
    assert audit_tree({"files": []})["trits"][0] == -1
    assert osworld_claims("no osworld score") == []

    ledger: list[dict[str, Any]] = []
    r0 = append_tree_receipt(ledger, GENESIS, _tree(_clean() + [
        {"path": "boot/vmlinuz", "size": 9 << 20, "head_hex": _bz()}]))
    b0 = backfill_check(ledger)
    assert not b0["ok"] and b0["blobs"] == [0] and b0["still_open"] == ["junioros"], b0
    r1 = append_tree_receipt(ledger, r0["commit"], _tree(_clean(), "junioros"))
    r2 = append_tree_receipt(ledger, r1["commit"], _tree(_clean(), "debian-stage"))
    bf = backfill_check(ledger)
    assert bf["ok"] and bf["gaps"] == [] and bf["n"] == 3 and bf["tip"] == r2["commit"], bf
    assert bf["closed"] == ["debian-stage", "junioros"] and bf["remaining"]["junioros"] == 0

    rg = list(ledger)
    append_tree_receipt(rg, r2["commit"], one_tree := _tree(
        [dict(f) for f in _clean()[:7]] + [dict(_clean()[7], text="OSWorld: 41%\n")] + _clean()[8:]))
    brg = backfill_check(rg)
    assert brg["regressions"] == [3] and brg["claims"] == [3] and not brg["ok"], brg
    assert one_tree["label"] == "junioros"
    lk2 = list(ledger)
    append_tree_receipt(lk2, r2["commit"], _tree(
        _clean()[:2] + [dict(_clean()[2], text="JUNIOR_BIND=0.0.0.0:8765\n")] + _clean()[3:]))
    assert backfill_check(lk2)["leaks"] == [3]

    t = [dict(x) for x in ledger]
    t[0] = dict(t[0], text=t[0]["text"].replace('"kernel_blob":true', '"kernel_blob":false'))
    assert 0 in backfill_check(t)["gaps"]
    m = [dict(x) for x in ledger]
    m[0] = dict(m[0], finding_count=0)
    assert 0 in backfill_check(m)["gaps"]
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
        "tip": bf["tip"],
        "flags": {"mint": MINT, "socket": SOCKET, "layer_one": LAYER_ONE, "fetch": FETCH,
                  "ue5_launch": UE5_LAUNCH, "model_pull": MODEL_PULL, "released": RELEASED},
    }


def main(argv: list[str]) -> int:
    if "--selftest" in argv:
        print(json.dumps(self_check(), sort_keys=True))
        return 0
    trees: list[dict[str, Any]] = [_tree(_clean())]
    if "--facts" in argv or "--dest" in argv:
        flag = "--facts" if "--facts" in argv else "--dest"
        i = argv.index(flag)
        if i + 1 >= len(argv):
            print("usage: --facts TREE.json | --dest DIR", file=sys.stderr)
            return 2
        if flag == "--dest":
            trees = [inventory_dest(argv[i + 1])]
        else:
            with open(argv[i + 1], "rb") as fh:
                data = json.loads(fh.read(MAX_READ * 16).decode("utf-8", "replace"))
            trees = data if isinstance(data, list) else [data]
    ledger: list[dict[str, Any]] = []
    prev = GENESIS
    for t in trees:
        prev = append_tree_receipt(ledger, prev, t)["commit"]
    bf = backfill_check(ledger)
    print(json.dumps({"receipts": ledger, "backfill": bf}, sort_keys=True))
    return 0 if bf["ok"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
