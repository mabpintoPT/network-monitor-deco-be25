from datetime import datetime, timezone

from network_monitor.collectors.deco.collector import DecoCollector


class FakeClient:
    def get_clients(self):
        return [type("C", (), {
            "name": "Test", "mac": "AA", "ip": "192.168.1.2", "online": True,
            "device_type": "pc", "connection_type": "wifi", "download_speed": 10,
            "upload_speed": 20, "remain_time": None, "enable_priority": False,
            "enable_internet": True,
        })()]


def test_deco_collector():
    result = DecoCollector(FakeClient()).collect()
    assert len(result) == 1
    assert result[0].mac == "AA"
    assert result[0].online is True
    assert result[0].observed_at.tzinfo == timezone.utc
