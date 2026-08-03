"""Minimal pty + terminal-emulator driver, so assertions run against the RENDERED screen
rather than a raw ANSI byte soup that a redrawing TUI makes meaningless."""

import fcntl
import os
import pty
import re
import select
import signal
import struct
import termios
import time

import pyte


class Screen(pyte.Screen):
    """pyte.Screen, minus the one handler that makes it unable to host tmux.

    tmux probes its terminal at startup with PRIVATE device queries. `pyte.Screen`'s
    `report_device_status` takes `(self, mode)` and the stream dispatches the private form
    with `private=True`, so `stream.feed()` raises `TypeError` mid-render. MEASURED
    2026-08-03: it kills a driver on the FIRST pump, before a single assertion runs.

    Exactly one handler, not two: `report_device_attributes` already takes `**kwargs` and has
    no-opped on `private` since pyte 0.7.0, so the private DA tmux also sends was never the
    problem. (Read it in the venv; no line citation, because the venv is derived and
    gitignored, so a pointer into it resolves for no reader and for no probe.) A first draft
    of this class overrode both and
    said so in prose, which is a wrong belief about the dependency held in the file every
    rig renders through — the push review caught it.

    Nothing in the suite had hit any of this because every rig here drives the opencode
    TUI, which sends no private queries. The repair stays narrow because this class is what
    the whole rig renders through. Answering the query is not wanted either: a reply is
    written into the child's stdin and lands in whatever is reading it (MEASURED: a stray
    `6c` typed into the captain's shell), so it goes unanswered, which is what a terminal
    without the capability does.
    """

    def report_device_status(self, *args, **kwargs):
        if kwargs.pop("private", False):
            return
        super().report_device_status(*args, **kwargs)


class Term:
    def __init__(self, argv, env=None, cwd=None, cols=150, rows=45):
        self.cols, self.rows = cols, rows
        self.screen = Screen(cols, rows)
        self.stream = pyte.ByteStream(self.screen)
        self.alive = True
        environ = dict(os.environ)
        if env:
            environ.update(env)
        environ.setdefault("TERM", "xterm-256color")
        environ["COLUMNS"], environ["LINES"] = str(cols), str(rows)

        self.pid, self.fd = pty.fork()
        if self.pid == 0:  # child
            if cwd:
                os.chdir(cwd)
            os.execvpe(argv[0], argv, environ)
        fcntl.ioctl(self.fd, termios.TIOCSWINSZ, struct.pack("HHHH", rows, cols, 0, 0))

    def pump(self, seconds):
        """Read for `seconds`, feeding the emulator. Never raises on child exit."""
        end = time.time() + seconds
        while time.time() < end:
            try:
                r, _, _ = select.select([self.fd], [], [], 0.05)
            except (OSError, ValueError):
                self.alive = False
                return
            if not r:
                continue
            try:
                data = os.read(self.fd, 65536)
            except OSError:
                self.alive = False
                return
            if not data:
                self.alive = False
                return
            self.stream.feed(data)

    def send(self, data, settle=0.6):
        os.write(self.fd, data.encode() if isinstance(data, str) else data)
        self.pump(settle)

    def key(self, name, settle=0.6):
        keys = {
            "enter": "\r",
            "escape": "\x1b",
            "tab": "\t",
            "up": "\x1b[A",
            "down": "\x1b[B",
            "right": "\x1b[C",
            "left": "\x1b[D",
        }
        self.send(keys.get(name, name), settle)

    def text(self):
        return "\n".join(line.rstrip() for line in self.screen.display)

    def show(self, title=""):
        bar = f"----- {title} " + "-" * max(0, 60 - len(title))
        print(bar)
        for line in self.screen.display:
            if line.strip():
                print(line.rstrip())
        print("-" * 66)

    def find(self, needle):
        """CASE-INSENSITIVE substring. Convenient and, for that reason, dangerous — three of
        the four assertion failures across this project were substring collisions found with
        this method. Notably `find("RETIRE")` also matches the header's `1 to retire`, and
        `find("Healbot")` also matches any path containing the project directory name. Prefer
        `exact()` for cell labels and `search()` for anything structural."""
        return needle.lower() in self.text().lower()

    def exact(self, needle):
        """Case-SENSITIVE substring. Cell labels are uppercase (`RETIRE`, `PERMISSION`,
        `ERROR`) and header phrasing is lowercase (`1 to retire`, `2 blocked`); case is the
        only thing that tells them apart."""
        return needle in self.text()

    def search(self, pattern):
        """Case-sensitive regex over the rendered screen. Use when a predicate needs shape,
        not just presence — e.g. `Healbot\\s+\\d+\\s+sessions?` is on the grid and nowhere
        else, whereas the bare word `healbot` is also in the run's own directory path."""
        return re.search(pattern, self.text()) is not None

    def close(self):
        try:
            os.kill(self.pid, signal.SIGTERM)
            time.sleep(0.4)
            os.kill(self.pid, signal.SIGKILL)
        except (ProcessLookupError, OSError):
            pass
        try:
            os.close(self.fd)
        except OSError:
            pass
