from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


def _bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    app_host: str = os.getenv("APP_HOST", "127.0.0.1")
    app_port: int = int(os.getenv("APP_PORT", "8000"))
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///data/network-monitor.db")
    collector_enabled: bool = _bool("COLLECTOR_ENABLED", True)
    collector_interval: int = int(os.getenv("COLLECTOR_INTERVAL", "30"))
    log_level: str = os.getenv("LOG_LEVEL", "INFO")

    deco_host: str = os.getenv("DECO_HOST", "192.168.68.1")
    deco_username: str = os.getenv("DECO_USERNAME", "admin")
    deco_password: str = os.getenv("DECO_PASSWORD", "")
    deco_timeout: float = float(os.getenv("DECO_TIMEOUT", "10"))
    deco_verify_tls: bool = _bool("DECO_VERIFY_TLS", False)


settings = Settings()
