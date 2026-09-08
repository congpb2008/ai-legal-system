"""SQLite connections with one connection per worker thread.

The facade keeps transactions on their originating thread and closes all handles
at shutdown. WAL and a busy timeout allow the HTTP and ingestion workers to share
one local database. Do not place this database on a network filesystem.
"""
from __future__ import annotations

import sqlite3
import threading
from pathlib import Path


def _configure(conn):
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys=ON')
    conn.execute('PRAGMA busy_timeout=5000')
    return conn


def in_memory():
    return _configure(sqlite3.connect(':memory:', check_same_thread=False))


class ThreadLocalConnection:
    def __init__(self, path):
        self.path = str(Path(path).resolve())
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._local = threading.local()
        self._handles = []
        self._lock = threading.Lock()
        self._closed = False
        self._connection().execute('PRAGMA journal_mode=WAL')

    def _connection(self):
        if self._closed:
            raise sqlite3.ProgrammingError('Database is closed')
        if not hasattr(self._local, 'conn'):
            conn = _configure(sqlite3.connect(self.path, timeout=5, check_same_thread=False))
            with self._lock:
                self._handles.append(conn)
            self._local.conn = conn
        return self._local.conn

    def __getattr__(self, name):
        return getattr(self._connection(), name)

    def __enter__(self):
        self._connection().__enter__()
        return self

    def __exit__(self, *args):
        return self._connection().__exit__(*args)

    def close(self):
        with self._lock:
            self._closed = True
            for conn in self._handles:
                conn.close()
            self._handles.clear()


def connect_thread_local(path):
    return ThreadLocalConnection(path)
