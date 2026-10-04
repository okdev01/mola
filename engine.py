"""Local tasks, sessions and monotonic countdown. No network or analytics."""
from contextlib import contextmanager
from datetime import date
from pathlib import Path
import sqlite3
import time
from uuid import uuid4


class Store:
    def __init__(self, path):
        self.path = str(path)
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with self.db() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS tasks (id TEXT PRIMARY KEY,title TEXT NOT NULL,
                    done INTEGER NOT NULL DEFAULT 0,created REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS sessions (id TEXT PRIMARY KEY,day TEXT NOT NULL,
                    seconds INTEGER NOT NULL,task_title TEXT NOT NULL);
            """)

    @contextmanager
    def db(self):
        db = sqlite3.connect(self.path, timeout=5)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def add(self, title):
        title = title.strip()
        if not title or len(title) > 200:
            raise ValueError("Görev 1–200 karakter olmalı")
        identifier = uuid4().hex
        with self.db() as db:
            db.execute("INSERT INTO tasks VALUES (?,?,0,?)", (identifier, title, time.time()))
        return identifier

    def toggle(self, identifier):
        with self.db() as db:
            db.execute("UPDATE tasks SET done=1-done WHERE id=?", (identifier,))

    def remove(self, identifier):
        with self.db() as db:
            db.execute("DELETE FROM tasks WHERE id=?", (identifier,))

    def tasks(self):
        with self.db() as db:
            return [dict(r) for r in db.execute("SELECT * FROM tasks ORDER BY done,created")]

    def complete(self, identifier, seconds, task_title="", day=None):
        if type(seconds) is not int or seconds < 1:
            raise ValueError("Geçersiz oturum süresi")
        with self.db() as db:
            db.execute("INSERT OR IGNORE INTO sessions VALUES (?,?,?,?)",
                       (identifier, day or date.today().isoformat(), seconds, task_title))

    def today(self, day=None):
        with self.db() as db:
            row = db.execute("SELECT count(*),coalesce(sum(seconds),0) FROM sessions WHERE day=?",
                             (day or date.today().isoformat(),)).fetchone()
            return row[0], row[1]

    def backup(self, destination):
        if Path(destination).resolve() == Path(self.path).resolve():
            raise ValueError("Yedek dosyası farklı bir konumda olmalı")
        if Path(destination).exists():
            raise FileExistsError("Yedek adı kullanılıyor; yeni bir ad seçin")
        with self.db() as source:
            target = sqlite3.connect(str(destination))
            try:
                source.backup(target)
            finally:
                target.close()


class Countdown:
    def __init__(self, seconds=1500, clock=time.monotonic):
        self.clock = clock
        self.reset(seconds)

    def reset(self, seconds):
        if type(seconds) is not int or seconds < 1:
            raise ValueError("Süre pozitif bir tam sayı olmalı")
        self.total = seconds
        self.remaining = float(seconds)
        self.deadline = None
        self.identifier = uuid4().hex
        self.reported = False

    @property
    def running(self):
        return self.deadline is not None

    def start(self):
        if not self.running and self.remaining > 0:
            self.deadline = self.clock() + self.remaining

    def pause(self):
        self.tick()
        self.deadline = None

    def tick(self):
        if self.deadline is not None:
            self.remaining = max(0.0, self.deadline - self.clock())
            if self.remaining == 0:
                self.deadline = None
        return self.remaining
