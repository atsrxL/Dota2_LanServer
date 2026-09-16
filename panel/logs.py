"""Bounded logs with redaction before anything is persisted."""
from __future__ import annotations
import threading
from pathlib import Path
from .common import ANSI, now

class SafeLog:
    def __init__(self, path: Path, secrets=(), max_bytes: int = 4 * 1024 * 1024):
        self.path, self.max_bytes = path, max_bytes
        self.lock = threading.RLock()
        self.secrets: set[str] = set(s for s in secrets if s)
        self.buffer = ""
        path.parent.mkdir(parents=True, exist_ok=True)

    def add_secret(self, secret: str) -> None:
        if secret:
            with self.lock:
                self.secrets.add(secret)

    def clean(self, text: str) -> str:
        text = ANSI.sub("", text)
        for s in sorted(self.secrets, key=len, reverse=True):
            text = text.replace(s, "[REDACTED]")
        return "".join(c for c in text if c in "\n\t" or ord(c) >= 32)

    def _append(self, text: str) -> None:
        if self.path.exists() and self.path.stat().st_size > self.max_bytes:
            older = self.path.with_suffix(self.path.suffix + ".1")
            self.path.replace(older)
        with self.path.open("a", encoding="utf-8") as f:
            f.write(self.clean(text))

    def write(self, data: str) -> None:
        # pexpect logfile_read only. Do NOT attach this to logfile/logfile_send.
        with self.lock:
            self.buffer += data.replace("\r", "\n")
            while "\n" in self.buffer:
                line, self.buffer = self.buffer.split("\n", 1)
                if line:
                    self._append(line + "\n")
            if len(self.buffer) > 65536:
                # Drop pathological no-newline output; do not split possible secrets.
                self.buffer = ""
                self._append("[过长输出行已丢弃]\n")

    def event(self, message: str) -> None:
        with self.lock:
            self._append(f"[{now()}] {message}\n")

    def flush(self) -> None:
        # pexpect flushes each chunk; leave partial lines buffered for safe redaction.
        pass

    def finish(self) -> None:
        with self.lock:
            if self.buffer:
                self._append(self.buffer + "\n")
            self.buffer = ""
