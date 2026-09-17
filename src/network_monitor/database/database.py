from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from collections.abc import Iterator


SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS devices (
    mac TEXT PRIMARY KEY,
    first_seen TEXT NOT NULL,
    last_seen TEXT NOT NULL,
    name TEXT NOT NULL DEFAULT '',
    ip TEXT NOT NULL DEFAULT '',
    online INTEGER NOT NULL DEFAULT 0,
    device_type TEXT,
    connection_type TEXT,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS observations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    observed_at TEXT NOT NULL,
    mac TEXT NOT NULL,
    name TEXT NOT NULL DEFAULT '',
    ip TEXT NOT NULL DEFAULT '',
    online INTEGER NOT NULL,
    device_type TEXT,
    connection_type TEXT,
    download_speed INTEGER,
    upload_speed INTEGER,
    remain_time INTEGER,
    enable_priority INTEGER,
    enable_internet INTEGER,
    FOREIGN KEY(mac) REFERENCES devices(mac)
);

CREATE INDEX IF NOT EXISTS idx_observations_mac_time
ON observations(mac, observed_at);

CREATE INDEX IF NOT EXISTS idx_observations_time
ON observations(observed_at);

CREATE TABLE IF NOT EXISTS presence_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    mac TEXT NOT NULL,
    started_at TEXT NOT NULL,
    ended_at TEXT,
    last_seen TEXT NOT NULL,
    FOREIGN KEY(mac) REFERENCES devices(mac)
);

CREATE INDEX IF NOT EXISTS idx_sessions_mac_start
ON presence_sessions(mac, started_at);

CREATE TABLE IF NOT EXISTS traffic_samples (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    observed_at TEXT NOT NULL,
    mac TEXT NOT NULL,
    download_bytes INTEGER,
    upload_bytes INTEGER,
    total_bytes INTEGER,
    source TEXT NOT NULL DEFAULT 'unknown',
    FOREIGN KEY(mac) REFERENCES devices(mac)
);

CREATE INDEX IF NOT EXISTS idx_traffic_mac_time
ON traffic_samples(mac, observed_at);
"""


class Database:
    def __init__(self, database_url: str) -> None:
        if not database_url.startswith("sqlite:///"):
            raise ValueError("A V1 suporta SQLite através de DATABASE_URL=sqlite:///...")
        self.path = Path(database_url.removeprefix("sqlite:///"))
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        """Abre uma ligação SQLite e garante que é fechada ao sair do contexto."""
        conn = sqlite3.connect(self.path, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def initialize(self) -> None:
        with self.connect() as conn:
            conn.executescript(SCHEMA)
