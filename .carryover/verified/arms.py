"""Arm factory: synthesized, frozen runtime configs — base ± exactly one delta.

WHY SYNTHESIS. ab.py's two arms are ENVIRONMENTS (source env.sh, or inherit the user's real
~/.config), and environments move: the 2026-07-31 stock arm changed twice in one day (a
symlink flip displaced ~/.claude/CLAUDE.md; four — then five — skills landed in
~/.agents/skills), so "stock" drifted mid-study and the frozen-arm repair became a
precondition for ever launching again. A synthesized arm inverts the dependency: the study
OWNS the config bytes. `freeze()` writes every config file plus the delta into the run
directory at launch with per-file sha256; `materialize()` rebuilds a live XDG_CONFIG_HOME
from that snapshot, verifying every byte, and refuses on any mismatch. Nothing the machine
does between launch and analysis can move an arm.

THE DELTA CHANNEL, VERIFIED AT SOURCE. A skills A/B needs arm B = arm A + one skill with
external skills OFF in both. opencode scans `{skill,skills}/**/SKILL.md` inside every
config directory UNCONDITIONALLY (skill/index.ts:205-208 at the 1.18.5 pin) — the
OPENCODE_DISABLE_EXTERNAL_SKILLS flag gates only the ~/.claude + ~/.agents + project-upward
scans (index.ts:186-203). So the synthesized dir carries the delta at
`opencode/skill/<name>/SKILL.md` and both arms keep the external scan disabled: one
channel, one file, zero contamination from the machine's 20+ external skills.

THE FILENAME-BAN COLLISION, resolved by construction. Run dirs are TRACKED
(hb/ab-runs/, .gitignore's un-ignore block) and this repo bans the SKILL.md filename
in-tree (gate.py `BANNED`) because a body containing !`cmd` shell-executes on slash-invoke
with no permission check (harness/env.sh:48-53, session/prompt.ts:1397-1408 at the pin).
So the SNAPSHOT stores the delta body under a safe name (`files/_delta_skill.md`) and only
`materialize()` writes a literal SKILL.md — into `hb/arms/`, which `.gitignore:48` ignores
(only explicit negations escape `hb/*`). The same hole motivates `define()`'s content
guard: a delta body containing the bang-backtick pattern is refused outright.

WHAT IS AND IS NOT FROZEN. Frozen: every regular file in `harness/config` except
node_modules and the seeded `.gitignore` (config.ts:297-303 seeds it at boot). NOT frozen:
`node_modules` bytes — `package-lock.json` IS frozen and pins them; materialize clonefiles
node_modules from the base and refuses if the base lockfile no longer matches the frozen
one, so dependency drift surfaces as a refusal instead of a silent arm change.

Never XDG_DATA_HOME: auth.json lives there and OpenAI is on oauth (rig.py's docstring,
the voided-run lesson). Isolation stays OPENCODE_DB-only, exactly like ab.serve_arm.

    import arms
    a = arms.define("base")
    b = arms.define("plus-tdd", skill_name="tdd", skill_body=open(...).read())
    manifest = arms.freeze([a, b], runpath)          # at launch, before any spend
    live = arms.materialize(runpath, "plus-tdd")     # byte-verified live config dir
    proc = arms.serve(runpath, "plus-tdd", port, db, log=...)
"""

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys

SP = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SP)
from rig import PROJECT, Api, fixtures, wait_for  # noqa: E402

HEALBOT = os.path.dirname(os.path.dirname(SP))
BASE = f"{HEALBOT}/harness/config"
LIVE = f"{SP}/hb/arms"  # ignored by .gitignore's hb/* rule — disposable, rebuildable
OC = f"bun run --cwd {HEALBOT}/opencode/packages/opencode --conditions=browser src/index.ts"

# The bang-backtick shell hole (harness/env.sh:48-53). A delta body carrying it would give
# the arm a slash command that executes shell with no permission gate — refuse at define().
SHELL_HOLE = re.compile(r"!`[^`]*`")

# Excluded from the snapshot: derived or runtime-seeded. package-lock.json is NOT here —
# it is the pin that stands in for node_modules.
EXCLUDE = ("node_modules",)
SEEDED = (".gitignore",)


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _file_sha(path):
    with open(path, "rb") as fh:
        return _sha(fh.read())


def _base_files():
    """Every regular file in the base config, relative paths, sorted — deterministic walk."""
    out = []
    for root, dirs, files in os.walk(BASE):
        dirs[:] = sorted(d for d in dirs if d not in EXCLUDE)
        for f in sorted(files):
            if f in SEEDED:
                continue
            out.append(os.path.relpath(os.path.join(root, f), BASE))
    return out


def define(name, skill_name=None, skill_body=None):
    """An arm definition: the base config, plus at most ONE delta skill. The single-delta
    constraint is the method (vary one thing); wanting two deltas means wanting two arms."""
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", name):
        raise ValueError(f"arm name {name!r} is not stable lowercase kebab-case")
    if (skill_name is None) != (skill_body is None):
        raise ValueError("a delta needs both skill_name and skill_body, or neither")
    if skill_name is not None:
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", skill_name):
            raise ValueError(f"skill name {skill_name!r} is not stable lowercase kebab-case")
        if not skill_body.strip():
            raise ValueError("delta skill body is empty")
        if SHELL_HOLE.search(skill_body):
            raise ValueError(
                "delta skill body contains the !`cmd` shell-substitution pattern — a skill "
                "body shell-executes on slash-invoke with no permission check "
                "(harness/env.sh:48-53); refusing to build an arm around it")
    return {"name": name, "skill_name": skill_name, "skill_body": skill_body}


def freeze(armdefs, runpath):
    """Snapshot every arm's config bytes into the run directory. Call AT LAUNCH, before any
    spend — the run dir becomes the arm authority the way it is already the corpus authority
    (the paid-run-protocol skill's freeze-at-launch rule; an environment edit after paid rows
    exist orphans the spend, measured twice on 2026-07-31)."""
    names = [a["name"] for a in armdefs]
    if len(set(names)) != len(names):
        raise ValueError(f"arm names are not unique: {names}")
    rels = _base_files()
    if not rels:
        raise RuntimeError(f"base config at {BASE} has no files — wrong tree?")
    manifests = {}
    for arm in armdefs:
        armdir = f"{runpath}/arms/{arm['name']}"
        filesdir = f"{armdir}/files"
        os.makedirs(filesdir, exist_ok=True)
        files = {}
        for rel in rels:
            src = f"{BASE}/{rel}"
            dst = f"{filesdir}/{rel}"
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copyfile(src, dst)
            files[rel] = _file_sha(dst)
        manifest = {
            "name": arm["name"],
            "base": os.path.relpath(BASE, HEALBOT),
            "files": files,
            "lockfile_sha256": files.get("opencode/package-lock.json"),
            "delta": None,
        }
        if arm["skill_name"]:
            body = arm["skill_body"].encode()
            # Safe name in the tracked snapshot; the real SKILL.md exists only in LIVE.
            with open(f"{armdir}/_delta_skill.md", "wb") as fh:
                fh.write(body)
            manifest["delta"] = {
                "skill_name": arm["skill_name"],
                "materialize_at": f"opencode/skill/{arm['skill_name']}/SKILL.md",
                "body_sha256": _sha(body),
            }
        with open(f"{armdir}/manifest.json", "w", encoding="utf-8") as fh:
            json.dump(manifest, fh, indent=2, sort_keys=True)
        manifests[arm["name"]] = manifest
    return manifests


def read_manifest(runpath, name):
    with open(f"{runpath}/arms/{name}/manifest.json", encoding="utf-8") as fh:
        return json.load(fh)


def materialize(runpath, name):
    """Rebuild the live XDG_CONFIG_HOME for one arm from its frozen snapshot, verifying
    every byte against the manifest. Any mismatch REFUSES — a snapshot that cannot
    reproduce its arm is a finding, not something to repair silently. The live dir is
    disposable; this function is how it always comes back."""
    manifest = read_manifest(runpath, name)
    armdir = f"{runpath}/arms/{name}"
    live = f"{LIVE}/{os.path.basename(os.path.normpath(runpath))}/{name}"
    if os.path.isdir(live):
        shutil.rmtree(live)
    for rel, want in sorted(manifest["files"].items()):
        src = f"{armdir}/files/{rel}"
        got = _file_sha(src)
        if got != want:
            raise RuntimeError(f"arm {name!r}: snapshot file {rel} sha {got[:12]} != "
                               f"manifest {want[:12]} — the frozen record was tampered or "
                               f"corrupted; refusing to materialize")
        dst = f"{live}/{rel}"
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copyfile(src, dst)
    if manifest["delta"]:
        with open(f"{armdir}/_delta_skill.md", "rb") as fh:
            body = fh.read()
        if _sha(body) != manifest["delta"]["body_sha256"]:
            raise RuntimeError(f"arm {name!r}: delta skill body sha mismatch — refusing")
        dst = f"{live}/{manifest['delta']['materialize_at']}"
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        with open(dst, "wb") as fh:
            fh.write(body)
    # node_modules: NOT frozen; the lockfile is. Clone from base only while the base still
    # matches the frozen lockfile — otherwise the deps this arm would load are not the deps
    # the study froze, and that is a refusal, not a warning.
    base_lock = f"{BASE}/opencode/package-lock.json"
    nm_src = f"{BASE}/opencode/node_modules"
    if manifest.get("lockfile_sha256") and os.path.isdir(nm_src):
        if _file_sha(base_lock) != manifest["lockfile_sha256"]:
            raise RuntimeError(
                f"arm {name!r}: the base config's package-lock.json no longer matches the "
                f"frozen lockfile — node_modules would not be the frozen dependency tree. "
                f"Reconstitute the base or re-freeze a NEW run; never edit this one")
        subprocess.run(["cp", "-c", "-R", nm_src, f"{live}/opencode/node_modules"], check=True)
    return live


def serve(runpath, name, port, db, log=None, timeout=120):
    """Boot a headless server under a materialized arm. ab.serve_arm's shape exactly — the
    same leak-stripping, the same OPENCODE_DB-only isolation, the same readiness probe —
    but the environment is CONSTRUCTED from the snapshot rather than inherited from a shell:
    XDG_CONFIG_HOME points at the materialized dir and both external-skill switches are
    pinned true, so the only skill any arm can see is the one its manifest declares."""
    fixtures()
    live = materialize(runpath, name)
    env = dict(os.environ)
    for leak in ("XDG_CONFIG_HOME", "OPENCODE_DISABLE_EXTERNAL_SKILLS", "OPENCODE_DISABLE_CLAUDE_CODE"):
        env.pop(leak, None)
    env["XDG_CONFIG_HOME"] = live
    env["OPENCODE_DISABLE_EXTERNAL_SKILLS"] = "true"
    env["OPENCODE_DISABLE_CLAUDE_CODE"] = "true"
    env["OPENCODE_DB"] = db
    env.setdefault("OPENCODE_CLIENT", "cli")
    assert "XDG_DATA_HOME" not in env or env["XDG_DATA_HOME"] == os.environ.get("XDG_DATA_HOME"), \
        "this function must never introduce XDG_DATA_HOME (auth.json lives there)"
    sink = open(log, "w", encoding="utf-8") if log else subprocess.PIPE
    proc = subprocess.Popen(
        ["/bin/zsh", "-c", f"exec {OC} serve --port {port} --hostname 127.0.0.1"],
        cwd=PROJECT, env=env, stdout=sink, stderr=subprocess.STDOUT, text=True,
    )
    api = Api(port)
    if not wait_for(lambda: api("GET", "/session?scope=project", timeout=3) is not None,
                    timeout, f"arm {name} on :{port}"):
        proc.kill()
        raise RuntimeError(f"synthesized arm {name!r} did not come up on :{port}")
    return proc
