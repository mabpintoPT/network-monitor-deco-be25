from datetime import datetime, timezone
from tempfile import TemporaryDirectory

from network_monitor.database.database import Database
from network_monitor.database.repository import NetworkRepository
from network_monitor.domain.models import DeviceSnapshot, TrafficSnapshot


def test_traffic_is_calculated_as_delta_inside_presence_session():
    with TemporaryDirectory() as directory:
        db = Database(f"sqlite:///{directory}/test.db")
        repo = NetworkRepository(db)
        mac = "AA-BB-CC-DD-EE-FF"
        base = dict(name="S22", mac=mac, ip="192.168.1.20", device_type="phone", connection_type="wifi")
        t1 = datetime(2026, 9, 16, 8, 0, tzinfo=timezone.utc)
        t2 = datetime(2026, 9, 16, 8, 1, tzinfo=timezone.utc)
        t3 = datetime(2026, 9, 16, 8, 2, tzinfo=timezone.utc)

        repo.record_collection([DeviceSnapshot(observed_at=t1, online=True, **base)])
        repo.record_traffic_samples([TrafficSnapshot(t1, mac, 1_000_000, 100_000)])
        repo.record_traffic_samples([TrafficSnapshot(t2, mac, 3_000_000, 250_000)])
        repo.record_collection([], observed_at=t3)

        history = repo.device_history(mac)
        assert len(history) == 1
        assert history[0]["traffic"]["download_bytes"] == 2_000_000
        assert history[0]["traffic"]["upload_bytes"] == 150_000
        assert history[0]["traffic"]["total_bytes"] == 2_150_000
