"""Pooled worktree slots — provision once, lease many times, reuse forever.

WHY A POOL AND NOT AD-HOC WORKTREES. An ad-hoc `git worktree add` here is measured-broken:
a worktree carries tracked files only, and this repo's expensive state is deliberately
untracked — the `opencode/` checkout (2.8G, 145,627 files, of which node_modules is 2.3G),
and the rig venv (17M). A bare worktree cannot resolve one file:line citation into the
checkout, boot one server, or run one probe. The repair is not to re-derive that state per
worktree (a fresh reconstitution is a clone + patch + `bun install` — minutes and network),
it is to provision a slot ONCE and lease it many times.

WHAT A SLOT IS. A full, self-similar healbot tree: a detached worktree of this repo (151
tracked files, including the hb/ measurement corpus since the 2026-07-31 hb/ split — the
corpus travels with the worktree for free) plus the two untracked payloads, cloned from the
main tree with APFS clonefile (`cp -c`): near-zero marginal disk until divergence, and
TESTED 2026-07-31 on this volume — the 2.8G checkout clones in ~28s with the nested
opencode .git intact and files byte-identical; the venv clones in 0.14s and its python
resolves sys.prefix to the CLONE, so no path surgery is needed. Self-similarity is the
load-bearing property: rig.py:31-35 derives every path from __file__, so the rig inside a
slot addresses the slot's own checkout, venv and DBs with no env overrides and no rig
changes; corpus writes in a slot STAY in the slot (disposable by design — merge back
deliberately or not at all).

THE TREEHOUSE VERDICT, so nobody re-litigates it. kunchenguid/treehouse (Go, MIT) is the
pattern source: pooled reusable worktrees, durable leases that survive process death,
conditional release for retry-safe automation, status/prune. Its lease DESIGN is borrowed
below; the tool itself is not adoptable here, for the same shape of reason gated-harness's
worktree was not (gate.py module docstring): treehouse treats untracked files as dirty and
resets worktrees on return — but a healbot slot's entire value IS its untracked payload.
Under treehouse's hygiene model our slots are permanently dirty and every return destroys
the provisioning. Borrowed vocabulary, rejected isolation model, zero third-party code run.

ACCEPTANCE, because a slot that never proved itself is not leasable. Provisioning ends by
running, INSIDE the slot with the slot's own venv: (1) the slot's gate.py — Tier 1 reads
the slot's checkout, docs and rigs, so a missing or drifted payload goes red here — and
(2) probe_control_wiring.py, the cheapest booting probe (~3s), which starts a real server
from the slot's checkout via bun, proving node_modules/bun/venv end to end. `acquire`
refuses slots without a recorded acceptance PASS.

KNOWN LIMIT — do not run BOOTING probes in two slots concurrently. Every booting probe
pins a fixed port (4141-4747 range); two slots running probe_fleet at once collide. Tier-1
and static probes are concurrency-safe (pure reads). Lifting this means parameterizing
probe ports, which is rig surgery with its own discipline — out of scope here, recorded.

    venv=.carryover/verified/venv/bin/python
    $venv harness/pool.py provision            # ensure N slots exist and accepted (default 2)
    $venv harness/pool.py provision --count 4
    $venv harness/pool.py acquire --owner me --purpose "ab arm B"   # prints slot path
    $venv harness/pool.py release <slot> [--if-owner me] [--keep|--force-dirty]
    $venv harness/pool.py status
    $venv harness/pool.py destroy <slot> --really

Exit codes match the gate's lattice: 0 ok · 2 refused (a check said no) · 3 error (could
not run). Pool root: ~/Desktop/healbot-pool, override HEALBOT_POOL. Leases and slot
records live in the pool root, never inside a worktree, so a slot's git status stays about
the WORK.
"""

import json
import os
import subprocess
import sys
import time
import uuid

HEALBOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
POOL = os.environ.get("HEALBOT_POOL", os.path.expanduser("~/Desktop/healbot-pool"))
SLOTS = f"{POOL}/slots"
LEASES = f"{POOL}/leases"
RECORDS = f"{POOL}/records"
# The untracked payloads a worktree cannot carry. Relative to the tree root on both ends.
PAYLOAD = ["opencode", ".carryover/verified/venv"]
VENV_PY = ".carryover/verified/venv/bin/python"
DEFAULT_COUNT = 2


def run(cmd, cwd=None, timeout=900):
    t0 = time.time()
    try:
        p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)
        return {"code": p.returncode, "out": p.stdout + p.stderr, "secs": round(time.time() - t0, 1)}
    except FileNotFoundError as exc:
        return {"code": None, "out": f"executable not found: {exc}", "secs": round(time.time() - t0, 1)}
    except subprocess.TimeoutExpired:
        return {"code": None, "out": f"TIMEOUT after {timeout}s", "secs": round(time.time() - t0, 1)}


def slot_name(path):
    return os.path.basename(os.path.normpath(path))


def lease_path(slot):
    return f"{LEASES}/{slot_name(slot)}.json"


def record_path(slot):
    return f"{RECORDS}/{slot_name(slot)}.json"


def read_json(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def slot_dirty(slot):
    """Tracked changes OR untracked non-ignored files. The payload is gitignored, so a
    freshly provisioned slot is CLEAN by this test — that inversion of treehouse's
    untracked-is-dirty rule is the whole reason this file exists."""
    r = run(["git", "status", "--porcelain"], cwd=slot)
    return bool(r["out"].strip()), r["out"].strip()


def list_slots():
    if not os.path.isdir(SLOTS):
        return []
    return sorted(f"{SLOTS}/{d}" for d in os.listdir(SLOTS)
                  if os.path.isdir(f"{SLOTS}/{d}") and d.startswith("slot-"))


# ==========================================================================================
def provision(count):
    os.makedirs(SLOTS, exist_ok=True)
    os.makedirs(LEASES, exist_ok=True)
    os.makedirs(RECORDS, exist_ok=True)
    run(["git", "worktree", "prune"], cwd=HEALBOT)

    have = list_slots()
    print(f"== pool provision ==  {len(have)} slot(s) exist, target {count}", flush=True)
    made, failed = 0, 0
    for i in range(1, count + 1):
        slot = f"{SLOTS}/slot-{i}"
        if slot in have:
            continue
        t0 = time.time()
        sha = run(["git", "rev-parse", "HEAD"], cwd=HEALBOT)["out"].strip()
        print(f"-- slot-{i}: worktree at {sha[:12]}", flush=True)
        r = run(["git", "worktree", "add", "--detach", slot], cwd=HEALBOT)
        if r["code"] != 0:
            print(f"   ERROR worktree add: {r['out'].strip()[:200]}", flush=True)
            failed += 1
            continue
        ok = True
        for rel in PAYLOAD:
            src, dst = f"{HEALBOT}/{rel}", f"{slot}/{rel}"
            if not os.path.exists(src):
                print(f"   ERROR payload source missing: {src}", flush=True)
                ok = False
                break
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            r = run(["cp", "-c", "-R", src, dst], timeout=600)
            print(f"   payload {rel}: {'ok' if r['code'] == 0 else 'FAILED'} ({r['secs']}s)", flush=True)
            if r["code"] != 0:
                ok = False
                break

        acceptance = {"verdict": "error", "gate": None, "boot": None}
        if ok:
            # The slot proves itself with its own venv against its own tree. A slot whose
            # gate cannot pass is recorded, kept for inspection, and never leased.
            g = run([f"{slot}/{VENV_PY}", f"{slot}/gate/gate.py", "--quiet"], cwd=slot, timeout=300)
            b = run([f"{slot}/{VENV_PY}", "probe_control_wiring.py"],
                    cwd=f"{slot}/.carryover/verified", timeout=300)
            acceptance = {
                "gate": g["code"], "boot": b["code"],
                "gate_tail": g["out"].strip().splitlines()[-1:] or [""],
                "boot_tail": b["out"].strip().splitlines()[-1:] or [""],
                "verdict": "pass" if g["code"] == 0 and b["code"] == 0 else
                           ("error" if g["code"] is None or b["code"] is None else "blocked"),
            }
            print(f"   acceptance: gate exit {g['code']}, boot exit {b['code']}"
                  f" -> {acceptance['verdict'].upper()}", flush=True)

        rec = {"slot": slot_name(slot), "sha": sha, "provisioned_at": time.strftime("%Y-%m-%d %H:%M:%S"),
               "secs": round(time.time() - t0, 1), "payload": PAYLOAD, "acceptance": acceptance}
        with open(record_path(slot), "w", encoding="utf-8") as fh:
            json.dump(rec, fh, indent=2)
        made += 1
        if acceptance["verdict"] != "pass":
            failed += 1
    print(f"== done ==  {made} provisioned, {failed} failed acceptance "
          f"(records in {os.path.relpath(RECORDS, os.path.expanduser('~'))})", flush=True)
    return 3 if failed else 0


# ==========================================================================================
def acquire(owner, purpose):
    if not owner or not purpose:
        print("acquire needs --owner and --purpose (the lease is the audit trail)", flush=True)
        return 3
    for slot in list_slots():
        rec = read_json(record_path(slot))
        if not rec or rec.get("acceptance", {}).get("verdict") != "pass":
            continue  # never lease a slot that has not proven itself
        if os.path.exists(lease_path(slot)):
            continue
        dirty, detail = slot_dirty(slot)
        if dirty:
            continue  # abandoned state is a human's decision, not auto-clean fodder
        lease = {"slot": slot_name(slot), "path": slot, "owner": owner, "purpose": purpose,
                 "lease_id": uuid.uuid4().hex, "pid": os.getpid(),
                 "acquired_at": time.strftime("%Y-%m-%d %H:%M:%S")}
        try:
            fd = os.open(lease_path(slot), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            continue  # raced another acquire; next slot
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(lease, fh, indent=2)
        print(slot, flush=True)  # the path IS the interface — scriptable
        print(f"  leased to {owner} ({purpose}), lease_id {lease['lease_id'][:12]}",
              file=sys.stderr, flush=True)
        return 0
    print("no leasable slot: all leased, dirty, or unaccepted — see `pool.py status`;"
          " `provision --count N` grows the pool", file=sys.stderr, flush=True)
    return 2


# ==========================================================================================
def release(slot, if_owner=None, keep=False, force_dirty=False):
    slot = f"{SLOTS}/{slot_name(slot)}"
    lease = read_json(lease_path(slot))
    if lease is None:
        print(f"{slot_name(slot)}: not leased", flush=True)
        return 2
    if if_owner and lease.get("owner") != if_owner:
        print(f"{slot_name(slot)}: leased by {lease.get('owner')}, not {if_owner} — refusing",
              flush=True)
        return 2
    if keep:
        os.unlink(lease_path(slot))
        print(f"{slot_name(slot)}: lease dropped, state KEPT — slot will not lease again "
              f"until clean (status will show it dirty)", flush=True)
        return 0
    dirty, detail = slot_dirty(slot)
    if dirty and not force_dirty:
        print(f"{slot_name(slot)}: worktree has uncommitted work — push or copy it out, "
              f"then release again; or --force-dirty to destroy it, or --keep to walk away:",
              flush=True)
        print("\n".join(f"    {ln}" for ln in detail.splitlines()[:10]), flush=True)
        return 2
    rec = read_json(record_path(slot)) or {}
    sha = rec.get("sha")
    # Reset TRACKED state to the provisioned sha; `clean -fd` without -x so the gitignored
    # payload survives — the exact inversion of treehouse's return-reset, deliberately.
    r1 = run(["git", "reset", "--hard", *( [sha] if sha else [] )], cwd=slot)
    r2 = run(["git", "clean", "-fd"], cwd=slot)
    if r1["code"] != 0 or r2["code"] != 0:
        print(f"{slot_name(slot)}: reset failed — lease NOT dropped, inspect by hand:\n"
              f"  {r1['out'].strip()[:150]}\n  {r2['out'].strip()[:150]}", flush=True)
        return 3
    os.unlink(lease_path(slot))
    print(f"{slot_name(slot)}: reset to {sha[:12] if sha else 'HEAD'}, payload kept, lease dropped",
          flush=True)
    return 0


# ==========================================================================================
def status():
    slots = list_slots()
    print(f"== pool ==  {POOL}  ({len(slots)} slot(s))", flush=True)
    code = 0
    for slot in slots:
        name = slot_name(slot)
        rec = read_json(record_path(slot)) or {}
        acc = rec.get("acceptance", {}).get("verdict", "none")
        lease = read_json(lease_path(slot))
        dirty, _ = slot_dirty(slot)
        bits = [f"accepted={acc}", f"sha={rec.get('sha', '?')[:12]}", "dirty" if dirty else "clean"]
        if lease:
            age_note = ""
            pid = lease.get("pid")
            if pid:
                try:
                    os.kill(pid, 0)
                except (ProcessLookupError, PermissionError):
                    age_note = " — holder pid DEAD; release explicitly if abandoned"
                    # Durable lease: never auto-reaped. The note is the escalation.
            bits.append(f"LEASED {lease['owner']} ({lease['purpose']}) since {lease['acquired_at']}{age_note}")
        else:
            bits.append("free")
        if acc != "pass" or (dirty and not lease):
            code = 2  # something needs a human; status is also a check
        print(f"  {name:<10} {' | '.join(bits)}", flush=True)
    return code


# ==========================================================================================
def destroy(slot, really=False):
    slot = f"{SLOTS}/{slot_name(slot)}"
    if not really:
        print("destroy is permanent (worktree + 2.8G payload). Repeat with --really.", flush=True)
        return 2
    if read_json(lease_path(slot)):
        print(f"{slot_name(slot)}: LEASED — release first", flush=True)
        return 2
    r = run(["git", "worktree", "remove", "--force", slot], cwd=HEALBOT, timeout=600)
    if r["code"] != 0:
        print(f"worktree remove failed: {r['out'].strip()[:200]}", flush=True)
        return 3
    for p in (record_path(slot), lease_path(slot)):
        if os.path.exists(p):
            os.unlink(p)
    print(f"{slot_name(slot)}: destroyed", flush=True)
    return 0


# ==========================================================================================
def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__.split("\n\n")[0] + "\n\nCommands: provision | acquire | release | status | destroy")
        return 0
    cmd, rest = args[0], args[1:]

    def flag(name, default=None):
        return rest[rest.index(name) + 1] if name in rest else default

    if cmd == "provision":
        return provision(int(flag("--count", DEFAULT_COUNT)))
    if cmd == "acquire":
        return acquire(flag("--owner"), flag("--purpose"))
    if cmd == "release":
        return release(rest[0], if_owner=flag("--if-owner"),
                       keep="--keep" in rest, force_dirty="--force-dirty" in rest)
    if cmd == "status":
        return status()
    if cmd == "destroy":
        return destroy(rest[0], really="--really" in rest)
    print(f"unknown command: {cmd}")
    return 3


if __name__ == "__main__":
    sys.exit(main())
