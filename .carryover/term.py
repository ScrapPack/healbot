"""Minimal pty + terminal-emulator driver, so assertions run against the RENDERED screen
rather than a raw ANSI byte soup that a redrawing TUI makes meaningless."""

import fcntl
import os
import pty
import select
import signal
import struct
import termios
import time

import pyte


class Term:
    def __init__(self, argv, env=None, cwd=None, cols=150, rows=45):
        self.cols, self.rows = cols, rows
        self.screen = pyte.Screen(cols, rows)
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
        return needle.lower() in self.text().lower()

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
