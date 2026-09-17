from network_monitor.database.database import Database


def test_database_initializes(tmp_path):
    db = Database(f"sqlite:///{tmp_path}/network.db")
    with db.connect() as conn:
        names = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"devices", "observations", "presence_sessions", "traffic_samples"} <= names
