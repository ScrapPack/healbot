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
    $venv harness/pool.py provision            # ensure N slots exist AND accepted (default 2);
                                               # re-verifies and repairs existing slots too
    $venv harness/pool.py provision --count 4
    $venv harness/pool.py acquire --owner me --purpose "ab arm B"   # prints slot path
    $venv harness/pool.py release <slot> [--if-owner me] [--keep|--discard-work]
    $venv harness/pool.py reset <slot> [--discard-work]   # repair an unleased soiled slot
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


def work_state(slot):
    """Work in a slot exists in two forms and every guard needs BOTH: uncommitted changes
    (visible to git status) and commits on the detached HEAD (status-clean, orphaned by a
    reset, reachable only via reflog). The first shipped version guarded only the first —
    the push review caught release; the committed-canary test then showed acquire and
    status shared the blind spot."""
    dirty, detail = slot_dirty(slot)
    sha = (read_json(record_path(slot)) or {}).get("sha")
    head = run(["git", "rev-parse", "HEAD"], cwd=slot)["out"].strip()
    committed = bool(sha) and head != sha
    return dirty, detail, committed, head, sha


def restore(slot, sha):
    """Reset TRACKED state to the provisioned sha; `clean -fd` without -x so the gitignored
    payload survives — the exact inversion of treehouse's return-reset, deliberately."""
    r1 = run(["git", "reset", "--hard", *([sha] if sha else [])], cwd=slot)
    r2 = run(["git", "clean", "-fd"], cwd=slot)
    ok = r1["code"] == 0 and r2["code"] == 0
    if not ok:
        print(f"{slot_name(slot)}: reset failed — inspect by hand:\n"
              f"  {r1['out'].strip()[:150]}\n  {r2['out'].strip()[:150]}", flush=True)
    return ok


def list_slots():
    if not os.path.isdir(SLOTS):
        return []
    return sorted(f"{SLOTS}/{d}" for d in os.listdir(SLOTS)
                  if os.path.isdir(f"{SLOTS}/{d}") and d.startswith("slot-"))


# ==========================================================================================
def accept(slot, sha, t0):
    """Run the slot's acceptance with the slot's own venv and (re)write its record. The slot
    proves itself against its own tree; one that cannot is recorded, kept for inspection,
    and never leased."""
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
    return acceptance["verdict"]


def copy_payload(slot):
    for rel in PAYLOAD:
        src, dst = f"{HEALBOT}/{rel}", f"{slot}/{rel}"
        if os.path.exists(dst):
            continue
        if not os.path.exists(src):
            print(f"   ERROR payload source missing: {src}", flush=True)
            return False
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        r = run(["cp", "-c", "-R", src, dst], timeout=600)
        print(f"   payload {rel}: {'ok' if r['code'] == 0 else 'FAILED'} ({r['secs']}s)", flush=True)
        if r["code"] != 0:
            return False
    return True


def provision(count):
    """Ensure `count` slots exist AND hold a recorded acceptance PASS. Existing slots are
    re-verified, not skipped — a half-built slot (worktree added, payload copy died) or one
    recorded blocked/error is repaired and re-accepted on every run, so "0 provisioned" can
    never mean "and none of them work". Leased slots are left alone: repair mutates a tree
    somebody may be using."""
    os.makedirs(SLOTS, exist_ok=True)
    os.makedirs(LEASES, exist_ok=True)
    os.makedirs(RECORDS, exist_ok=True)
    run(["git", "worktree", "prune"], cwd=HEALBOT)

    print(f"== pool provision ==  {len(list_slots())} slot(s) exist, target {count}", flush=True)
    made, repaired, failed, leased = 0, 0, 0, 0
    for i in range(1, count + 1):
        slot = f"{SLOTS}/slot-{i}"
        t0 = time.time()
        if os.path.isdir(slot):
            rec = read_json(record_path(slot)) or {}
            if rec.get("acceptance", {}).get("verdict") == "pass" and \
                    all(os.path.exists(f"{slot}/{rel}") for rel in PAYLOAD):
                continue
            if read_json(lease_path(slot)):
                print(f"-- slot-{i}: needs repair but is LEASED — skipped, release it first", flush=True)
                leased += 1
                continue
            print(f"-- slot-{i}: exists but unaccepted — repairing", flush=True)
            sha = rec.get("sha") or run(["git", "rev-parse", "HEAD"], cwd=slot)["out"].strip()
            if copy_payload(slot) and accept(slot, sha, t0) == "pass":
                repaired += 1
            else:
                failed += 1
            continue
        sha = run(["git", "rev-parse", "HEAD"], cwd=HEALBOT)["out"].strip()
        print(f"-- slot-{i}: worktree at {sha[:12]}", flush=True)
        r = run(["git", "worktree", "add", "--detach", slot], cwd=HEALBOT)
        if r["code"] != 0:
            print(f"   ERROR worktree add: {r['out'].strip()[:200]}", flush=True)
            failed += 1
            continue
        made += 1
        if not (copy_payload(slot) and accept(slot, sha, t0) == "pass"):
            failed += 1
    print(f"== done ==  {made} provisioned, {repaired} repaired, {failed} failed acceptance, "
          f"{leased} leased-skipped (records in {RECORDS})", flush=True)
    return 3 if failed else (2 if leased else 0)


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
        dirty, _, committed, _, _ = work_state(slot)
        if dirty or committed:
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
def release(slot, if_owner=None, keep=False, discard_work=False):
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
    code = guard_then_restore(slot, discard_work, context="release again")
    if code != 0:
        return code  # lease NOT dropped on refusal or reset failure
    os.unlink(lease_path(slot))
    print(f"{slot_name(slot)}: restored, payload kept, lease dropped", flush=True)
    return 0


def guard_then_restore(slot, discard_work, context):
    """The shared back half of release and reset: refuse while the slot holds work in
    either form, unless --discard-work; then restore. 0 restored · 2 refused · 3 failed."""
    dirty, detail, committed, head, sha = work_state(slot)
    if (dirty or committed) and not discard_work:
        what = " and ".join(w for w, on in
                            [("uncommitted changes", dirty),
                             (f"commits on the detached HEAD ({head[:12]} != provisioned {sha[:12] if sha else '?'})",
                              committed)] if on)
        print(f"{slot_name(slot)}: the slot holds {what} — push or copy the work out "
              f"(e.g. `git -C {slot} push origin HEAD:refs/heads/<branch>`), then {context}; "
              f"or --discard-work to destroy it", flush=True)
        if dirty:
            print("\n".join(f"    {ln}" for ln in detail.splitlines()[:10]), flush=True)
        return 2
    if not restore(slot, sha):
        return 3
    print(f"{slot_name(slot)}: reset to {sha[:12] if sha else 'HEAD'}", flush=True)
    return 0


def reset_cmd(slot, discard_work=False):
    """Repair an UNLEASED slot that holds abandoned work (acquire skips those forever
    otherwise, and release cannot reach them — it requires a lease)."""
    slot = f"{SLOTS}/{slot_name(slot)}"
    if read_json(lease_path(slot)):
        print(f"{slot_name(slot)}: LEASED — use release, which drops the lease too", flush=True)
        return 2
    if not os.path.isdir(slot):
        print(f"{slot_name(slot)}: no such slot", flush=True)
        return 3
    return guard_then_restore(slot, discard_work, context="reset again")


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
        dirty, _, committed, _, _ = work_state(slot)
        state = "dirty" if dirty else ("committed-work" if committed else "clean")
        bits = [f"accepted={acc}", f"sha={rec.get('sha', '?')[:12]}", state]
        if lease:
            age_note = ""
            pid = lease.get("pid")
            if pid:
                try:
                    os.kill(pid, 0)
                except ProcessLookupError:
                    age_note = " — holder pid DEAD; release explicitly if abandoned"
                    # Durable lease: never auto-reaped. The note is the escalation.
                except PermissionError:
                    pass  # EPERM = the process EXISTS under another user — alive, not dead
            bits.append(f"LEASED {lease['owner']} ({lease['purpose']}) since {lease['acquired_at']}{age_note}")
        else:
            bits.append("free")
        if acc != "pass" or ((dirty or committed) and not lease):
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
USAGE = "Commands: provision [--count N] | acquire --owner O --purpose P | " \
        "release <slot> [--if-owner O] [--keep|--discard-work] | " \
        "reset <slot> [--discard-work] | status | destroy <slot> --really"


def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__.split("\n\n")[0] + "\n\n" + USAGE)
        return 0
    cmd, rest = args[0], args[1:]

    def flag(name, default=None):
        # Malformed input exits 3 through the lattice, never as a traceback.
        if name not in rest:
            return default
        i = rest.index(name)
        if i + 1 >= len(rest) or rest[i + 1].startswith("--"):
            raise SystemExit(print(f"{name} needs a value\n{USAGE}") or 3)
        return rest[i + 1]

    def positional():
        value_flags = {"--if-owner", "--count"}  # flags that consume the next token
        skip = False
        for a in rest:
            if skip:
                skip = False
                continue
            if a.startswith("--"):
                skip = a in value_flags
                continue
            return a
        raise SystemExit(print(f"{cmd} needs a slot name\n{USAGE}") or 3)

    if cmd == "provision":
        try:
            return provision(int(flag("--count", str(DEFAULT_COUNT))))
        except ValueError:
            print(f"--count needs an integer\n{USAGE}")
            return 3
    if cmd == "acquire":
        return acquire(flag("--owner"), flag("--purpose"))
    if cmd == "release":
        return release(positional(), if_owner=flag("--if-owner"),
                       keep="--keep" in rest, discard_work="--discard-work" in rest)
    if cmd == "reset":
        return reset_cmd(positional(), discard_work="--discard-work" in rest)
    if cmd == "status":
        return status()
    if cmd == "destroy":
        return destroy(positional(), really="--really" in rest)
    print(f"unknown command: {cmd}\n{USAGE}")
    return 3


if __name__ == "__main__":
    sys.exit(main())
