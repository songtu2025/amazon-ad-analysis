from functools import lru_cache
from pathlib import Path
from dataclasses import dataclass
import os


PROJECT_ROOT = Path(__file__).resolve().parents[3]
ENV_PATH = PROJECT_ROOT / ".env"


def _load_dotenv(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def _read_bool(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    gerpgo_base_url: str
    gerpgo_app_id: str
    gerpgo_app_key: str
    gerpgo_access_token: str
    gerpgo_market_ids: str
    database_url: str
    sync_cooldown_seconds: int
    sync_scheduler_enabled: bool
    sync_scheduler_interval_minutes: int
    sync_scheduler_sources: str

    @property
    def market_ids(self) -> list[int]:
        values = []
        for value in self.gerpgo_market_ids.split(","):
            value = value.strip()
            if value:
                values.append(int(value))
        return values


@lru_cache
def get_settings() -> Settings:
    env_file_values = _load_dotenv(ENV_PATH)

    def read(name: str, default: str = "") -> str:
        return os.environ.get(name) or env_file_values.get(name) or default

    return Settings(
        gerpgo_base_url=read("GERPGO_BASE_URL", "https://open.gerpgo.com/api"),
        gerpgo_app_id=read("GERPGO_APP_ID"),
        gerpgo_app_key=read("GERPGO_APP_KEY"),
        gerpgo_access_token=read("GERPGO_ACCESS_TOKEN"),
        gerpgo_market_ids=read("GERPGO_MARKET_IDS"),
        database_url=read("DATABASE_URL", "sqlite:///./data/app.db"),
        sync_cooldown_seconds=int(read("SYNC_COOLDOWN_SECONDS", "120")),
        sync_scheduler_enabled=_read_bool(read("SYNC_SCHEDULER_ENABLED", "false")),
        sync_scheduler_interval_minutes=int(read("SYNC_SCHEDULER_INTERVAL_MINUTES", "360")),
        sync_scheduler_sources=read("SYNC_SCHEDULER_SOURCES", "sp_keywords"),
    )
