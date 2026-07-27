"""Does the retirement guard exist when NOTHING is rendering? — FREE, no model turn.

Phase 5 shipped automatic retirement as a `createEffect` inside the Healbot route component. It
worked (13/13) under the one condition nobody wrote down: that a human had the grid open. A fleet
started by `harness/fleet.sh` and left running with the control terminal closed — the topology the
whole fleet architecture exists to provide — retired nothing.

Phase 6 moved the trigger to a SERVER plugin. This probe asserts the half of that which can be
proven for free: that in a server with **no TUI process anywhere**, the guard loads, arms, and
reports the thresholds it will actually enforce.

WHAT THIS PROBE DOES NOT PROVE, stated plainly so the green does not get read as more than it is:
it does not prove the `event` hook fires, and it does not prove a session is ever retired. Both
need real assistant tokens, which need real model turns. `verify_headless_retire.py` pays for that.
This probe is the cheap half — and it is the half that catches the likely regressions: an
unregistered plugin, a rename, a non-function export tripping `getLegacyPlugins`, or a threshold
that never reaches the server process.

ASSERTION DISCIPLINE. "The log contains a line" is a positive-only predicate and this suite's
characteristic failure is passing. So the same predicate is run against a server started with
`HEALBOT_AUTO_RETIRE=0`, where it MUST be absent. Without that negative control, a probe that
grepped a file it never wrote would look identical to this one.
"""

import os
import re
import sys
import time

SP = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SP)
import rig  # noqa: E402

PORT_ON = 4141
PORT_OFF = 4142
SOFT = "37000"
HARD = "41000"

ARMED = r"\[healbot/auto-retire\] headless retirement armed"

r = rig.Results()
servers = []


def log_of(port):
    return f"{rig.WORK}/arm-{port}.log"


def read_log(port):
    path = log_of(port)
    if not os.path.exists(path):
        return ""
    with open(path, encoding="utf-8", errors="replace") as fh:
        return fh.read()


try:
    rig.fixtures()

    # -----------------------------------------------------------------------------------------
    # Preconditions. A log left over from a previous run would make the arming assertion pass
    # without a server ever starting.
    # -----------------------------------------------------------------------------------------
    for port in (PORT_ON, PORT_OFF):
        if os.path.exists(log_of(port)):
            os.remove(log_of(port))
    r.check(
        "precondition: no stale server log on disk",
        not read_log(PORT_ON) and not read_log(PORT_OFF),
        "otherwise the grep below could pass without a server",
    )

    # -----------------------------------------------------------------------------------------
    # THE ARMED CASE. `rig.serve` spawns `opencode serve` under `subprocess.Popen` with no pty
    # and no terminal — there is no TUI in this test at all, which is the entire point.
    #
    # Thresholds go through `env_extra`, i.e. into the SERVER's environment. That distinction is
    # the one a rig gets wrong: before Phase 6 the thresholds were read by the client, so
    # exporting them in Python before `boot()` was enough. Now the server enforces them, and a
    # rig that configures only its own environment configures the wrong process.
    # -----------------------------------------------------------------------------------------
    servers.append(
        rig.serve(
            PORT_ON,
            rig.db("armon"),
            log=log_of(PORT_ON),
            env_extra={"HEALBOT_RETIRE_AT": SOFT, "HEALBOT_RETIRE_HARD": HARD},
        )
    )
    # The plugin instance is created lazily, per directory, on the first request that names it —
    # which `rig.serve`'s own readiness probe already made. Settle briefly so the line is flushed.
    time.sleep(2)
    on = read_log(PORT_ON)

    r.check("a headless server came up with no TUI", bool(on), f"{len(on)} bytes of log")
    r.check(
        "THE GUARD ARMS WITH NOTHING RENDERING — the Phase 5 gap, closed",
        bool(re.search(ARMED, on)),
        "no client, no terminal, no grid — and the retirement trigger is live",
    )
    r.check(
        "it reports the SOFT gate it was actually given",
        f"soft {int(SOFT):,}" in on,
        f"expected 'soft {int(SOFT):,}'",
    )
    r.check(
        "it reports the HARD gate it was actually given",
        f"hard {int(HARD):,}" in on,
        f"expected 'hard {int(HARD):,}' — proves env reaches the SERVER, not just the rig",
    )
    r.check(
        "it armed for the PROJECT directory, not the server's cwd",
        rig.PROJECT in on,
        "workspace-routing.ts:87 falls back to process.cwd(); under `serve` that is "
        "packages/opencode, and a guard armed there would watch an empty instance",
    )
    # The default must NOT leak through when an override is present — otherwise this probe would
    # pass on a plugin that ignored its environment entirely.
    r.check(
        "the shipped 256,000 default is NOT what armed here",
        "soft 256,000" not in on,
        "an override that is silently ignored would read as armed",
    )

    # -----------------------------------------------------------------------------------------
    # THE NEGATIVE CONTROL. Same rig, same probe, `HEALBOT_AUTO_RETIRE=0`. The kill switch exists
    # because this thing spawns and archives without asking, so it has to work — and it doubles
    # as proof that the assertion above is capable of being false.
    # -----------------------------------------------------------------------------------------
    servers.append(
        rig.serve(
            PORT_OFF,
            rig.db("armoff"),
            log=log_of(PORT_OFF),
            env_extra={"HEALBOT_RETIRE_AT": SOFT, "HEALBOT_AUTO_RETIRE": "0"},
        )
    )
    time.sleep(2)
    off = read_log(PORT_OFF)

    r.check("the kill-switch server also came up", bool(off), f"{len(off)} bytes of log")
    r.check(
        "NEGATIVE CONTROL: HEALBOT_AUTO_RETIRE=0 does NOT arm",
        not re.search(ARMED, off),
        "the same grep that passed above fails here — so it discriminates",
    )
    r.check(
        "…and the server is otherwise healthy",
        rig.Api(PORT_OFF)("GET", "/session?scope=project", timeout=10) is not None,
        "the kill switch disables the guard, not the server",
    )

    # -----------------------------------------------------------------------------------------
    # Nothing was retired. Neither server ran a model turn, so a retirement line here would mean
    # the guard fired on something it invented.
    # -----------------------------------------------------------------------------------------
    r.check(
        "no session was retired by either server",
        "handed off" not in on and "handed off" not in off,
        "arming is not firing",
    )

finally:
    for proc in servers:
        try:
            proc.kill()
        except Exception:
            pass
    ok = r.summary()
    sys.exit(0 if ok else 1)
