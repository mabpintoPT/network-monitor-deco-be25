from datetime import datetime, timezone
from tempfile import TemporaryDirectory

from network_monitor.database.database import Database
from network_monitor.database.repository import NetworkRepository
from network_monitor.domain.models import DeviceSnapshot


def test_presence_session_lifecycle():
    with TemporaryDirectory() as directory:
        db = Database(f"sqlite:///{directory}/test.db")
        repo = NetworkRepository(db)
        mac = "AA-BB-CC-DD-EE-FF"
        t1 = datetime(2026, 9, 16, 8, 0, tzinfo=timezone.utc)
        t2 = datetime(2026, 9, 16, 8, 1, tzinfo=timezone.utc)
        t3 = datetime(2026, 9, 16, 8, 2, tzinfo=timezone.utc)
        base = dict(name="PC", mac=mac, ip="192.168.1.10", device_type="pc", connection_type="wifi")
        repo.record_snapshot(DeviceSnapshot(observed_at=t1, online=True, **base))
        repo.record_snapshot(DeviceSnapshot(observed_at=t2, online=True, **base))
        repo.record_snapshot(DeviceSnapshot(observed_at=t3, online=False, **base))
        sessions = repo.sessions(mac)
        assert len(sessions) == 1
        assert sessions[0]["started_at"] == t1.isoformat()
        assert sessions[0]["ended_at"] == t3.isoformat()
        assert sessions[0]["device_name"] == "PC"


def test_collection_marks_missing_device_offline_and_closes_session():
    with TemporaryDirectory() as directory:
        db = Database(f"sqlite:///{directory}/test.db")
        repo = NetworkRepository(db)
        t1 = datetime(2026, 9, 16, 8, 0, tzinfo=timezone.utc)
        t2 = datetime(2026, 9, 16, 8, 1, tzinfo=timezone.utc)
        pc = dict(name="PC", mac="AA-BB-CC-DD-EE-FF", ip="192.168.1.10", device_type="pc", connection_type="wifi")
        phone = dict(name="S22", mac="11-22-33-44-55-66", ip="192.168.1.20", device_type="phone", connection_type="wifi")

        repo.record_collection([
            DeviceSnapshot(observed_at=t1, online=True, **pc),
            DeviceSnapshot(observed_at=t1, online=True, **phone),
        ])
        repo.record_collection([
            DeviceSnapshot(observed_at=t2, online=True, **pc),
        ])

        devices = {row["mac"]: row for row in repo.current_devices()}
        assert devices[phone["mac"]]["online"] == 0
        assert devices[pc["mac"]]["online"] == 1

        sessions = repo.sessions(mac=phone["mac"])
        assert len(sessions) == 1
        assert sessions[0]["device_name"] == "S22"
        assert sessions[0]["ended_at"] == t2.isoformat()
