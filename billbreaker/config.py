"""Settings read from the environment (and a local .env file when present)."""

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")


def _flag(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    gemini_api_key: str
    gemini_model: str
    gemini_fallback_model: str
    openstates_api_key: str
    database_path: Path
    turso_url: str
    turso_token: str
    cloud_sync: bool
    abuse_admin_token: str
    abuse_alert_webhook_url: str
    abuse_alert_threshold: int
    abuse_alert_cooldown_s: int


def _default_db() -> str:
    # Serverless hosts only allow writes under /tmp; Turso is the durable option there.
    return "/tmp/billbreaker.db" if os.getenv("VERCEL") else str(ROOT / "data" / "billbreaker.db")


def load_settings() -> Settings:
    return Settings(
        gemini_api_key=os.getenv("GEMINI_API_KEY", ""),
        gemini_model=os.getenv("GEMINI_MODEL", "gemini-flash-latest"),
        gemini_fallback_model=os.getenv("GEMINI_FALLBACK_MODEL", "gemini-3.5-flash-lite"),
        openstates_api_key=os.getenv("OPENSTATES_API_KEY", ""),
        database_path=Path(os.getenv("DATABASE_PATH", "") or _default_db()),
        turso_url=os.getenv("TURSO_DATABASE_URL", ""),
        turso_token=os.getenv("TURSO_AUTH_TOKEN", ""),
        cloud_sync=_flag("CLOUD_SYNC"),
        abuse_admin_token=os.getenv("ABUSE_ADMIN_TOKEN", ""),
        abuse_alert_webhook_url=os.getenv("ABUSE_ALERT_WEBHOOK_URL", ""),
        abuse_alert_threshold=max(1, int(os.getenv("ABUSE_ALERT_THRESHOLD", "5") or 5)),
        abuse_alert_cooldown_s=max(60, int(os.getenv("ABUSE_ALERT_COOLDOWN_S", "3600") or 3600)),
    )


settings = load_settings()
