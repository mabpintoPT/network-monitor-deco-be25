from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from typing import Any

from network_monitor.database.database import Database
from network_monitor.domain.models import DeviceSnapshot


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


def parse_dt(value: str) -> datetime:
    return datetime.fromisoformat(value)


class NetworkRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    def record_snapshot(self, snapshot: DeviceSnapshot) -> None:
        """Regista uma observação individual sem inferir clientes ausentes."""
        self._record_snapshots([snapshot], mark_missing=False)

    def record_collection(self, snapshots: list[DeviceSnapshot], observed_at: datetime | None = None) -> None:
        """Regista uma recolha completa da Deco.

        A API ``client_list`` devolve apenas os clientes atualmente presentes.
        Por isso, um dispositivo conhecido que não apareça numa resposta
        válida deve ser marcado como offline e a sua sessão aberta deve ser
        encerrada. Uma falha da API não chega a este método e, portanto, não
        provoca falsos offline.
        """
        self._record_snapshots(snapshots, mark_missing=True, observed_at=observed_at)

    def _record_snapshots(
        self,
        snapshots: list[DeviceSnapshot],
        *,
        mark_missing: bool,
        observed_at: datetime | None = None,
    ) -> None:
        if not snapshots and not mark_missing:
            return

        timestamp = iso(observed_at or (snapshots[0].observed_at if snapshots else datetime.now(timezone.utc)))
        current_macs = {snapshot.mac for snapshot in snapshots}

        with self.db.connect() as conn:
            # Primeiro atualizamos/insertamos todos os dispositivos presentes.
            for snapshot in snapshots:
                timestamp = iso(snapshot.observed_at)
                existing = conn.execute(
                    "SELECT mac, online FROM devices WHERE mac = ?", (snapshot.mac,)
                ).fetchone()

                previous_online = None if existing is None else int(existing["online"])

                if existing is None:
                    conn.execute(
                        """INSERT INTO devices
                        (mac, first_seen, last_seen, name, ip, online, device_type, connection_type, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (
                            snapshot.mac,
                            timestamp,
                            timestamp,
                            snapshot.name,
                            snapshot.ip,
                            int(snapshot.online),
                            snapshot.device_type,
                            snapshot.connection_type,
                            timestamp,
                        ),
                    )
                else:
                    conn.execute(
                        """UPDATE devices SET last_seen=?, name=?, ip=?, online=?,
                        device_type=?, connection_type=?, updated_at=? WHERE mac=?""",
                        (
                            timestamp,
                            snapshot.name,
                            snapshot.ip,
                            int(snapshot.online),
                            snapshot.device_type,
                            snapshot.connection_type,
                            timestamp,
                            snapshot.mac,
                        ),
                    )

                conn.execute(
                    """INSERT INTO observations
                    (observed_at, mac, name, ip, online, device_type, connection_type,
                     download_speed, upload_speed, remain_time, enable_priority, enable_internet)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        timestamp,
                        snapshot.mac,
                        snapshot.name,
                        snapshot.ip,
                        int(snapshot.online),
                        snapshot.device_type,
                        snapshot.connection_type,
                        snapshot.download_speed,
                        snapshot.upload_speed,
                        snapshot.remain_time,
                        None if snapshot.enable_priority is None else int(snapshot.enable_priority),
                        None if snapshot.enable_internet is None else int(snapshot.enable_internet),
                    ),
                )

                if snapshot.online and (previous_online is None or previous_online == 0):
                    conn.execute(
                        """INSERT INTO presence_sessions (mac, started_at, ended_at, last_seen)
                        VALUES (?, ?, NULL, ?)""",
                        (snapshot.mac, timestamp, timestamp),
                    )
                elif snapshot.online:
                    conn.execute(
                        """UPDATE presence_sessions SET last_seen=?
                        WHERE id=(SELECT id FROM presence_sessions WHERE mac=? AND ended_at IS NULL
                        ORDER BY started_at DESC LIMIT 1)""",
                        (timestamp, snapshot.mac),
                    )
                else:
                    conn.execute(
                        """UPDATE presence_sessions SET ended_at=?, last_seen=?
                        WHERE id=(SELECT id FROM presence_sessions WHERE mac=? AND ended_at IS NULL
                        ORDER BY started_at DESC LIMIT 1)""",
                        (timestamp, timestamp, snapshot.mac),
                    )

            if mark_missing:
                # A lista de clientes da Deco é uma fotografia completa. Tudo o
                # que era conhecido mas não apareceu nesta resposta está offline.
                # Não criamos uma observação artificial: ``last_seen`` continua a
                # significar a última vez em que o dispositivo foi observado online.
                known = conn.execute("SELECT mac FROM devices WHERE online=1").fetchall()
                for row in known:
                    mac = row["mac"]
                    if mac in current_macs:
                        continue
                    conn.execute(
                        "UPDATE devices SET online=0, updated_at=? WHERE mac=?",
                        (timestamp, mac),
                    )
                    conn.execute(
                        """UPDATE presence_sessions SET ended_at=?,
                        last_seen=last_seen
                        WHERE id=(SELECT id FROM presence_sessions WHERE mac=? AND ended_at IS NULL
                        ORDER BY started_at DESC LIMIT 1)""",
                        (timestamp, mac),
                    )

    def current_devices(self) -> list[dict[str, Any]]:
        with self.db.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM devices ORDER BY online DESC, name COLLATE NOCASE"
            ).fetchall()
        return [dict(row) for row in rows]

    def sessions(self, mac: str | None = None, limit: int = 200) -> list[dict[str, Any]]:
        sql = """SELECT presence_sessions.*, devices.name AS device_name, devices.ip AS device_ip
                FROM presence_sessions
                JOIN devices ON devices.mac = presence_sessions.mac"""
        params: list[Any] = []
        if mac:
            sql += " WHERE presence_sessions.mac=?"
            params.append(mac)
        sql += " ORDER BY started_at DESC LIMIT ?"
        params.append(limit)
        with self.db.connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [dict(row) for row in rows]

    def observations(self, mac: str, since: datetime | None = None, limit: int = 5000) -> list[dict[str, Any]]:
        sql = "SELECT * FROM observations WHERE mac=?"
        params: list[Any] = [mac]
        if since:
            sql += " AND observed_at>=?"
            params.append(iso(since))
        sql += " ORDER BY observed_at DESC LIMIT ?"
        params.append(limit)
        with self.db.connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [dict(row) for row in rows]


    def record_traffic_samples(self, samples: list) -> None:
        if not samples:
            return
        with self.db.connect() as conn:
            for sample in samples:
                conn.execute(
                    """INSERT INTO traffic_samples
                    (observed_at, mac, download_bytes, upload_bytes, total_bytes, source)
                    VALUES (?, ?, ?, ?, ?, ?)""",
                    (
                        iso(sample.observed_at),
                        sample.mac,
                        sample.download_bytes,
                        sample.upload_bytes,
                        sample.total_bytes,
                        sample.source,
                    ),
                )

    def traffic_samples(self, mac: str, limit: int = 5000) -> list[dict[str, Any]]:
        with self.db.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM (SELECT * FROM traffic_samples WHERE mac=? ORDER BY observed_at DESC LIMIT ?) ORDER BY observed_at ASC",
                (mac, limit),
            ).fetchall()
        return [dict(row) for row in rows]

    def device_history(self, mac: str, limit: int = 200) -> list[dict[str, Any]]:
        """Combina cada sessão de presença com o tráfego acumulado durante essa sessão."""
        sessions = self.sessions(mac=mac, limit=limit)
        samples = self.traffic_samples(mac, limit=20000)
        now = datetime.now(timezone.utc)

        result: list[dict[str, Any]] = []
        for session in sessions:
            start = parse_dt(session["started_at"])
            end = parse_dt(session["ended_at"]) if session["ended_at"] else now
            relevant = [
                sample for sample in samples
                if start <= parse_dt(sample["observed_at"]) <= end
            ]

            download = 0
            upload = 0
            previous_download = None
            previous_upload = None
            first_sample_at = None
            last_sample_at = None

            for sample in relevant:
                current_download = sample["download_bytes"]
                current_upload = sample["upload_bytes"]
                sample_at = sample["observed_at"]
                first_sample_at = first_sample_at or sample_at
                last_sample_at = sample_at

                if previous_download is not None and current_download is not None and current_download >= previous_download:
                    download += current_download - previous_download
                if previous_upload is not None and current_upload is not None and current_upload >= previous_upload:
                    upload += current_upload - previous_upload

                if current_download is not None:
                    previous_download = current_download
                if current_upload is not None:
                    previous_upload = current_upload

            result.append({
                **session,
                "traffic": {
                    "download_bytes": download,
                    "upload_bytes": upload,
                    "total_bytes": download + upload,
                    "sample_count": len(relevant),
                    "first_sample_at": first_sample_at,
                    "last_sample_at": last_sample_at,
                },
            })

        return result

    def stats(self) -> dict[str, Any]:
        with self.db.connect() as conn:
            devices = conn.execute("SELECT COUNT(*) FROM devices").fetchone()[0]
            online = conn.execute("SELECT COUNT(*) FROM devices WHERE online=1").fetchone()[0]
            observations = conn.execute("SELECT COUNT(*) FROM observations").fetchone()[0]
            sessions = conn.execute("SELECT COUNT(*) FROM presence_sessions").fetchone()[0]
        return {
            "devices": devices,
            "online": online,
            "offline": devices - online,
            "observations": observations,
            "sessions": sessions,
        }
