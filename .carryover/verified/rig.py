"""Shared rig for the Phase 4 redo verification.

Differences from the voided carryover run, all deliberate:

  * The harness is SOURCED, not reconstructed — `zsh -c '. harness/env.sh && exec ...'`.
    That is what pins openai/gpt-5.6-sol and compaction.auto=false.
  * XDG_DATA_HOME is NOT set. Global.Path.data derives from it (core/src/global.ts:11) and
    auth.json lives there (opencode/src/auth/index.ts:10); openai is on oauth, so
    redirecting it strands the credentials. Isolation is the DB only, via an absolute
    OPENCODE_DB, which database.ts:43-46 returns directly.
  * OPENCODE_DISABLE_DEFAULT_PLUGINS is NOT set (those are the provider auth plugins).
"""

import json
import os
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

SP = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SP)
from term import Term  # noqa: E402

# Everything derives from __file__. Previously every verify_*.py hardcoded an absolute
# scratchpad path belonging to the session that wrote it; those directories are gone, so the
# suite could not be re-run from a fresh clone — which for a project whose only mechanism for
# proving anything is this rig is a defect in the evidence, not just an inconvenience.
HEALBOT = os.path.dirname(os.path.dirname(SP))
REPO = f"{HEALBOT}/opencode"
ENVSH = f"{HEALBOT}/harness/env.sh"
WORK = os.environ.get("HEALBOT_RIG_WORK", f"{SP}/hb")
PROJECT = f"{WORK}/project"

# The fork run from source. The installed `opencode` binary does NOT contain healbot.tsx, so
# every rig here has to go through the checkout or it is testing a different program.
OC = f"bun run --cwd {REPO}/packages/opencode --conditions=browser src/index.ts"


def db(name):
    """Absolute, per-rig DB path. OPENCODE_DB is the ONLY isolation this suite applies —
    `database.ts:43-46` returns an absolute value directly, bypassing the data dir. Do NOT
    reach for XDG_DATA_HOME: `global.ts:11` derives Global.Path.data from it and auth.json
    lives there, so redirecting it strands the OpenAI oauth credentials and the model pin
    silently stops resolving. That mistake is what voided the first verification run."""
    os.makedirs(WORK, exist_ok=True)
    return f"{WORK}/{name}.db"


def fixtures():
    """Create the project fixtures the rigs prompt against. Idempotent.

    `worker0..2.txt` carry assertable payloads so a tool-using turn can be proven to have
    really read a file; `ledger0..2.txt` are large enough (~130 KB each) that reading them
    moves context occupancy far enough to cross a lowered HEALBOT_RETIRE_AT.
    """
    os.makedirs(PROJECT, exist_ok=True)
    for i in range(3):
        path = f"{PROJECT}/worker{i}.txt"
        if not os.path.exists(path):
            with open(path, "w") as fh:
                fh.write(f"payload-{i}\n")
    for i in range(3):
        path = f"{PROJECT}/ledger{i}.txt"
        # Regenerate if short: a truncated ledger silently stops moving occupancy, and the
        # retirement rigs would then fail for a reason that looks like a code defect.
        if os.path.exists(path) and os.path.getsize(path) >= 130_000:
            continue
        with open(path, "w") as fh:
            row = 0
            while fh.tell() < 130_000:
                fh.write(f"{i:02d}-{row:06d}  ACCT-{(row * 7919) % 100000:05d}  {(row * 31) % 997:04d}.{row % 100:02d}  OK\n")
                row += 1
    return PROJECT


def git_baseline():
    """Make PROJECT its own git repo with the fixtures committed. Call AFTER creating fixtures
    and BEFORE the session runs.

    Not optional for anything that asserts on changed files. `GET /session/{id}/diff` serves
    `summary.diffs`, which `SessionSummary.summarize` (`summary.ts:102-127`) computes with git
    — so a file git cannot see produces no diff, silently and with no error anywhere.

    This directory lives inside the healbot repo and is gitignored there (`.gitignore`:
    `.carryover/verified/hb/`), which means without an inner repo of its own EVERY file a
    session creates here is invisible to the diff machinery. TESTED, the expensive way: a
    350K-token run reported an empty file list and no "## Files already changed" section, and
    the cause was the ignore rule rather than anything in the code under test.

    A nested repo is the fix rather than moving the directory: it keeps the rig self-contained
    and makes the baseline explicit, so a session's creations are diffs against a known tree.
    """
    import subprocess

    def git(*args, check=True):
        return subprocess.run(["git", "-C", PROJECT, *args], capture_output=True, text=True, check=check)

    if not os.path.isdir(f"{PROJECT}/.git"):
        git("init", "-q")
        git("config", "user.email", "rig@healbot.local")
        git("config", "user.name", "healbot rig")
    git("add", "-A")
    # Nothing to commit is fine and normal on a re-run.
    git("commit", "-q", "-m", "rig baseline", check=False)
    return git("rev-parse", "--short", "HEAD", check=False).stdout.strip()


def boot(port, db, cols=170, rows=48, settle=25):
    """TUI from source, harness sourced, DB isolated. The TUI hosts its own server on `port`
    — `--port` is 'port to listen on' (`cli/network.ts:9`), so this mode cannot meet a block
    that predates it. For that, use `serve()` + `attach()`."""
    fixtures()
    inner = f". {ENVSH} && exec {OC} {PROJECT} --port {port}"
    t = Term(
        ["/bin/zsh", "-c", inner],
        env={"OPENCODE_DB": db, "OPENCODE_CLIENT": os.environ.get("OPENCODE_CLIENT", "cli")},
        cwd=PROJECT,
        cols=cols,
        rows=rows,
    )
    t.pump(settle)
    return t


def serve(port, db, timeout=90, log=None, env_extra=None):
    """A long-lived headless server, separate from any TUI — PLAN.md:335's architecture.

    Returns the Popen. This is what makes the cold-start reconcile reachable: pending
    permission and question requests live in an in-memory Map inside the SERVER
    (`permission/index.ts:24,50`), so as long as the server outlives the client, a block can
    predate the client and `healbot.tsx`'s `reconcile()` has something to recover.

    `log` redirects the server's merged stdout/stderr to a file the caller can read WHILE the
    server runs. The default `subprocess.PIPE` cannot be read incrementally without either a
    reader thread or risking a deadlock when the pipe buffer fills, and since Phase 6 the server
    is where automatic retirement actually happens — the plugin at
    `harness/config/opencode/plugin/healbot.ts` reports arming and every retirement there. A
    headless test that cannot read the server's log cannot see the thing it is testing.

    That path was `plugin/auto-retire.ts` until 7b7ce9f and this docstring still said so, wrapped
    across two lines so a grep for the old name did not find it. The file does not exist under
    that name any more; anything still citing it is stale.

    `env_extra` sets variables for the SERVER process specifically. That distinction became
    load-bearing in Phase 6: the retirement thresholds are read by the server plugin, not by the
    client, so a rig that only exports them into its own environment before `attach()` is
    configuring the wrong process.
    """
    import subprocess

    fixtures()
    inner = f". {ENVSH} && exec {OC} serve --port {port} --hostname 127.0.0.1"
    env = dict(os.environ)
    env["OPENCODE_DB"] = db
    env.setdefault("OPENCODE_CLIENT", "cli")
    env.update(env_extra or {})
    sink = open(log, "w", encoding="utf-8") if log else subprocess.PIPE
    proc = subprocess.Popen(
        ["/bin/zsh", "-c", inner],
        cwd=PROJECT,
        env=env,
        stdout=sink,
        stderr=subprocess.STDOUT,
        text=True,
    )
    api = Api(port)
    # Probe an API route, not `/app` — `/app` serves the web UI's HTML, so `Api` blows up
    # decoding it as JSON and the probe never goes true. `is not None` rather than truthiness
    # because a fresh server correctly answers `[]`, which is falsy.
    ready = wait_for(
        lambda: api("GET", "/session?scope=project", timeout=3) is not None, timeout, f"server on :{port}"
    )
    if not ready:
        proc.kill()
        raise RuntimeError(f"server did not come up on :{port}")
    return proc


def attach(port, db, cols=170, rows=48, settle=25):
    """The control terminal as a CLIENT of an existing server.

    `opencode attach <url>` is a real, registered command (`cli/cmd/attach.ts:7-16`,
    `index.ts:84`), and its non---mini branch calls the same `run()` from `cli/tui/layer`
    with the same `createLegacyTuiPluginHost()` as `cli/cmd/tui.ts:271-296` — so it is the
    full TUI and the Healbot builtin loads on it. HARNESS.md used to record this as
    impossible, on the true premise that `--port` only ever listens.

    OPENCODE_DB is still passed for parity, but it is the SERVER's DB that holds the
    sessions; the client reaches them over HTTP.
    """
    inner = f". {ENVSH} && exec {OC} attach http://127.0.0.1:{port} --dir {PROJECT}"
    t = Term(
        ["/bin/zsh", "-c", inner],
        env={"OPENCODE_DB": db, "OPENCODE_CLIENT": os.environ.get("OPENCODE_CLIENT", "cli")},
        cwd=PROJECT,
        cols=cols,
        rows=rows,
    )
    t.pump(settle)
    return t


class Api:
    """HTTP client for the rig, scoped to the same project the TUI is scoped to.

    The `x-opencode-directory` header is NOT optional, and leaving it off is a trap that costs
    a whole test run. `workspace-routing.ts:87` resolves the instance as
    `?directory || x-opencode-directory || process.cwd()`, and the real SDK always sends the
    header (`sdk/js/src/client.ts:49`, url-encoded). Without it the rig talks to whatever
    directory the SERVER's cwd happens to be — and under `serve()` that is
    `packages/opencode`, because `bun run --cwd` sets it there, not the project.

    Symptom when this is wrong: every API call succeeds, `GET /session` returns the sessions
    you created, and the grid shows `0 sessions`, because the two are looking at different
    instances. TESTED — that is exactly how the first cold-start run failed.
    """

    def __init__(self, port, directory=None):
        self.base = f"http://127.0.0.1:{port}"
        self.directory = directory or PROJECT

    def __call__(self, method, path, body=None, timeout=900):
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(
            self.base + path,
            data=data,
            method=method,
            headers={
                "Content-Type": "application/json",
                "x-opencode-directory": urllib.parse.quote(self.directory, safe=""),
            },
        )
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read().decode()
        return json.loads(raw) if raw else None


# The sentinel `summary()` emits and `gate/tier2.py` parses. A probe's stdout is prose meant
# for a human, so the one line a machine reads is marked as such rather than pattern-matched
# out of the prose — the tier must not start depending on the wording of a sentence.
SKIP_LINE = "##ENV-SKIP## "


class Env:
    """A named requirement about the MACHINE, so a check that cannot be MEASURED here says
    which fact was missing instead of reporting a red that means "wrong machine".

    THE PROBLEM THIS SOLVES, measured 2026-08-01 by running `gate/tier2.py` from a pool
    worktree slot: four probes went red, and not one of the reds was a defect. The CLAUDE.md
    symlink is materialized by `env.claude.sh` at source time and `git worktree add` does not
    run it; the installed-skill twin compares against `~/.agents/skills/`, which belongs to
    whichever checkout last installed it; the transcript corpus is whatever
    `CLAUDE_CONFIG_DIR` points at. A slot run therefore reported BLOCKED for reasons a slot
    cannot fix and must not try to (a crewmate writing outside its worktree is the thing the
    crew constraints exist to stop). Misleading, not wrong — and a suite people learn to read
    around is a suite that has stopped working.

    BOTH FAILURE MODES ARE REAL, and this class is shaped by the second one. A silent red
    that means "wrong machine" trains the reader to ignore reds. A silent SKIP that means "we
    stopped measuring" is worse: it reports green for a claim nobody checked, which is
    `docs/CLONE.md`'s defect wearing a new hat. So a skip here is never quiet — it prints
    NOT MEASURED HERE with the requirement's name, it is counted against a declared budget
    (`Results(skip_max=)`), a run where EVERY row skipped is red, and `summary()` emits a
    machine-readable line `gate/tier2.py` lifts into the run record. What was not measured,
    and why, is evidence the record carries; it is not an absence.

    A requirement must be STRICTLY WEAKER than the check it guards, or the check can no
    longer go red and the guard has replaced the measurement. `probe_backend`'s is the worked
    example: the requirement is "some corpus directory carries a doubled dash", the check is
    "the `--claude-worktrees-` directories are there and match the rule" — so a corpus that
    has dotted paths but not those ones still goes red, which is the finding.

    `probe` is called at most once and its answer cached: a requirement is a fact about the
    machine, and one re-measured per check could answer differently twice in one run. A probe
    that raises counts as unsatisfied and carries the exception into the printed note —
    "could not establish the environment" is a skip, not a pass.
    """

    def __init__(self, name, why, probe):
        self.name = name
        self.why = why
        self._probe = probe
        self._cached = None

    def satisfied(self):
        """`(ok, note)`. `note` is empty unless establishing the fact itself failed."""
        if self._cached is None:
            try:
                self._cached = (bool(self._probe()), "")
            except Exception as exc:
                self._cached = (False, f"could not establish: {type(exc).__name__}: {exc}")
        return self._cached


def _git_out(*args):
    import subprocess

    p = subprocess.run(["git", "-C", HEALBOT, *args], capture_output=True, text=True)
    return p.stdout.strip() if p.returncode == 0 else ""


def is_main_checkout():
    """Is this rig running from the repository's PRIMARY worktree?

    git's own answer rather than a path heuristic: in a linked worktree `--git-dir` is
    `<main>/.git/worktrees/<name>` while `--git-common-dir` is `<main>/.git`; in the primary
    checkout the two name the same directory. VERIFIED 2026-08-01 in both — this slot
    reported `.../healbot/.git/worktrees/slot-2` vs `.../healbot/.git`, the main checkout
    reported `.git` for both. Relative answers are resolved against HEALBOT, which is why the
    join is there; `os.path.join` already keeps an absolute second argument.

    No git, or a `git` that errors, yields "" for both and answers False. That is deliberate:
    a rig that cannot establish which checkout it is in should declare the skip, not assume
    the privileged answer.
    """
    gd, common = _git_out("rev-parse", "--git-dir"), _git_out("rev-parse", "--git-common-dir")
    if not gd or not common:
        return False
    return os.path.realpath(os.path.join(HEALBOT, gd)) == os.path.realpath(os.path.join(HEALBOT, common))


MAIN_CHECKOUT = Env(
    "main-checkout",
    "the rig is running from the repository's primary worktree, not a pool slot — the claim "
    "reads state keyed to the main checkout (an installed copy, an absolute session path) "
    "that a slot cannot own and must not write",
    is_main_checkout,
)


class Results:
    """Assertion ledger. `expect` is a FLOOR on how many assertions must run, and it is not
    bookkeeping — it is the only thing that can tell "everything passed" from "almost nothing ran".

    Without it `summary()` returns `not failed` over whatever happened to be appended, so a probe
    that died on its third line reports `2/2 passed` and exits 0. MEASURED in Phase 9 by cloning
    this repo and running the suite in it: `probe_on_grid` reported **2/2**, `probe_control_wiring`
    **7/7**, and `probe_headless_arm` printed `!! timed out waiting for server` and then **1/1** —
    all three exit 0, all three having proven nothing. The opencode checkout is gitignored, so
    `bun run --cwd` ENOENTs and no server ever starts; every screen predicate is then trivially
    false and every `not on_grid` assertion passes vacuously.

    Two distinct escape routes produce that, which is why the floor sits here rather than in a
    per-probe guard:

    - **A crash.** `sys.exit()` inside a `finally` DISCARDS the in-flight exception, so a probe
      that raises still exits on `summary()`'s verdict. `probe_request_channel.py:151-153` names
      this exactly and guards against it; nine other probes carried the identical `finally` and
      seven had no guard at all.
    - **A timeout.** `wait_for()` prints `!!` and returns None. Nothing raises, so the probe simply
      runs fewer assertions and the summary never notices.

    The floor is a MINIMUM, not an equality: adding an assertion must not turn a probe red, but
    losing one must. Set it to the count the probe is recorded as producing.

    `skip_max` is the second budget and it governs `Env` (above): the MOST declared
    environment skips a run of this rig may record. It defaults to 0, so every rig that names
    no requirement is unaffected and a rig that starts skipping must raise this number in the
    same change — the same discipline `probe_rig_contract`'s box exemption carries, for the
    same reason. An exemption that widens without anybody counting is how a guard stops
    guarding.

    A skipped row is still APPENDED, so it counts toward `expect`. That is correct and worth
    saying why: the floor answers "did the probe reach this line", and a skip proves it did.
    What the floor cannot then catch is the degenerate case where everything skipped, so
    `summary()` catches that one by name — rows but none of them measured is red, always,
    whatever `skip_max` says.
    """

    def __init__(self, expect=None, skip_max=0):
        self.rows = []
        self.expect = expect
        self.skip_max = skip_max

    def check(self, name, ok, detail="", needs=None):
        """`needs=<Env>` guards this row on a machine fact. When it holds the row runs
        normally; when it does not the row records a declared skip and `ok` is NEVER called.

        With `needs=`, `ok` must be a CALLABLE — Python evaluates arguments eagerly, so an
        expression predicate has already run, and already crashed if the missing environment
        is what it reads, before this guard can decide anything. The TypeError is deliberate
        and fatal: a guard that silently accepted the eager form would leave the caller
        believing a row was protected when the protection ran too late to matter.
        `probe_rig_contract` asserts the lambda statically, so the two agree.
        """
        if needs is not None:
            if not callable(ok):
                raise TypeError(
                    f"check({name!r}, needs={needs.name!r}) needs a CALLABLE predicate — pass a "
                    "lambda. An expression is evaluated before check() is entered, so the guard "
                    "cannot stop it reading an environment that is not there."
                )
            satisfied, note = needs.satisfied()
            if not satisfied:
                self.rows.append((name, None, detail, needs))
                print(f"  [SKIP] {name} — NOT MEASURED HERE: needs `{needs.name}` ({needs.why})"
                      + (f" [{note}]" if note else ""), flush=True)
                return None
            ok = ok()
        self.rows.append((name, bool(ok), detail, None))
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""), flush=True)
        return bool(ok)

    def skips(self):
        """The declared environment skips this run recorded, newest last."""
        return [{"needs": need.name, "check": name, "why": need.why}
                for name, ok, _, need in self.rows if need is not None]

    def summary(self):
        print("\n== summary ==", flush=True)
        for name, ok, detail, need in self.rows:
            mark = "SKIP" if need is not None else ("PASS" if ok else "FAIL")
            note = f" [needs {need.name}]" if need is not None else ""
            print(f"  {mark}  {name}{note}" + (f"   ({detail})" if detail else ""))

        measured = [(n, ok) for n, ok, _, need in self.rows if need is None]
        skipped = self.skips()
        failed = [n for n, ok in measured if not ok]
        short = self.expect is not None and len(self.rows) < self.expect
        over = len(skipped) > self.skip_max
        blank = bool(self.rows) and not measured

        # Two shapes, and the split is not cosmetic. The floor counts ROWS while the ratio
        # counts MEASURED rows, so a rig with skips printing the one-line form reads
        # "31/31 passed (expected at least 33)" — which is what a SHORT RUN looks like, on a
        # run that was not short. Rigs that name no requirement keep the original line
        # verbatim; the recorded scores in docs/SHIP.md and gate/runs/ are quotes of it.
        floor = f" (expected at least {self.expect})" if self.expect is not None else ""
        if skipped or self.skip_max:
            against = f" against a floor of {self.expect}" if self.expect is not None else ""
            print(f"\n  {len(self.rows)} rows{against}: {len(measured) - len(failed)}/{len(measured)} "
                  f"measured passed, {len(skipped)} NOT MEASURED HERE (budget {self.skip_max})", flush=True)
        else:
            print(f"\n  {len(self.rows) - len(failed)}/{len(self.rows)} passed{floor}", flush=True)

        if short:
            print(
                f"  !! SHORT RUN — only {len(self.rows)} of {self.expect} assertions ran. The ones that\n"
                f"     did are NOT evidence: a probe that stops early leaves every later claim\n"
                f"     unmeasured, and screen predicates pass vacuously against a dead terminal.",
                flush=True,
            )
        if over:
            print(
                f"  !! SKIP BUDGET EXCEEDED — {len(skipped)} declared skips against a budget of\n"
                f"     {self.skip_max}. Either an environment requirement stopped holding somewhere it\n"
                f"     should, or a new one was added without being counted. Both are findings.",
                flush=True,
            )
        if blank:
            print(
                f"  !! NOTHING WAS MEASURED — all {len(self.rows)} rows declared a skip. A rig with no\n"
                f"     measured row proves nothing at all, and reporting that as a pass is exactly the\n"
                f"     failure the skip machinery exists to avoid. Red regardless of the budget.",
                flush=True,
            )
        # The line gate/tier2.py parses. Emitted whenever this rig participates in the
        # mechanism at all — including at zero, because "0 of a budget of 3" is the positive
        # evidence that everything was measured, and absence of the line would be
        # indistinguishable from a parse that failed.
        if skipped or self.skip_max:
            print(SKIP_LINE + json.dumps({"count": len(skipped), "max": self.skip_max,
                                          "over": over, "blank": blank, "skips": skipped}), flush=True)
        return not failed and not short and not over and not blank


def wait_for(fn, timeout, label, interval=1.0):
    end = time.time() + timeout
    while time.time() < end:
        try:
            v = fn()
            if v:
                return v
        except Exception:
            pass
        time.sleep(interval)
    print(f"  !! timed out waiting for {label} after {timeout}s", flush=True)
    return None


# The grid's own header: the literal title, then the session count. `healbot.tsx` renders
# `Healbot` followed by two spaces and `N session(s)`; nothing else in the TUI does.
GRID_HEADER = r"Healbot\s+\d+\s+sessions?"


def on_grid(t):
    """Is the Healbot route the thing on screen?

    NOT `t.find("Healbot")`, which is what every "the route never changed" assertion in this
    suite used to be. `Term.find` lowercases both sides, and the rig's own project directory
    is `.../healbot/.carryover/verified/hb/project` — the session route renders a session's
    directory in its sidebar footer, so that predicate can be satisfied by the path alone. It
    was measured returning True on home, on the grid, on the session route, and on home again
    after quitting: zero discriminating power, on the assertion carrying the load-bearing
    claim that answering a block never navigated away.

    Any rig that asserts `on_grid` MUST also assert `not on_grid` somewhere it should be
    false. A positive-only predicate cannot be distinguished from a tautology.
    """
    return t.search(GRID_HEADER)


def marker_col(t):
    """Column of the '>' selection marker. Navigation is asserted on THIS, not on cell
    text — cell text is present regardless of which cell is selected."""
    for line in t.screen.display:
        idx = line.find("▸")
        if idx != -1:
            return idx
    return None


def fire(api, sid, text, tools=None, box=None, label=""):
    """POST /session/{id}/message blocks until the turn completes, so prompts go on a
    thread. `box` collects `(label, elapsed, result_or_exception)` — a THREE-tuple, and the
    third element is the one that matters. See `completed()` below; do not count `box`.

    A turn that threw and a turn that finished are appended in the SAME shape, so `len(box)`
    answers "how many turns ENDED", never "how many turns RAN". This docstring said
    `(elapsed, result_or_exception)` — the wrong arity, and the right warning — from the day it
    was written, and no rig in the suite ever read element [2]."""

    def run():
        started = time.time()
        try:
            body = {"parts": [{"type": "text", "text": text}]}
            if tools:
                body["tools"] = tools
            out = api("POST", f"/session/{sid}/message", body)
            if box is not None:
                box.append((label or sid, time.time() - started, out))
        except Exception as exc:
            if box is not None:
                box.append((label or sid, time.time() - started, exc))

    th = threading.Thread(target=run, daemon=True)
    th.start()
    return th


def completed(box, prefix=""):
    """The entries in a `fire()` box whose turn actually RAN — payload is not an exception.

    Use this for any ASSERTION about a turn having completed. `len(box)` is still correct for
    SEQUENCING — "wait until all three have ended, however they ended" — and the distinction is
    the whole point: `fire()` swallows every exception into the same 3-tuple, so a count cannot
    tell the two apart.

    Phase 12, TESTED: three `fire()` calls at a port with nothing listening filled a box with
    three `URLError`s in **9 milliseconds**, and that satisfied every completion predicate in
    the suite — `len(box) == 3`, `len(workers) == 3`, `any(b[0] == "blocker" for b in box)`.
    Four `r.check` rows were phrased as claims about turns completing and were really counting
    turns that ended; one of them (`verify_question.py`, the concurrency row) had no independent
    evidence anywhere else in its file. The hazard was named in `fire()`'s own docstring as
    "result_or_exception" and no rig had ever read that element.

    This is Phase 9's defect — an assertion that is True on exactly the runs that did not
    evaluate it — living in the PAID half, which is why a fresh clone could not reach it: a paid
    rig cannot run from a clone, so it never got the chance to report its false green.
    """
    return [b for b in box if b[0].startswith(prefix) and not isinstance(b[2], BaseException)]
