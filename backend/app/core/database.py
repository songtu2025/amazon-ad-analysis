from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import PROJECT_ROOT, get_settings


class Base(DeclarativeBase):
    pass


def _sqlite_path_from_url(database_url: str) -> Path | None:
    prefix = "sqlite:///"
    if not database_url.startswith(prefix):
        return None
    raw_path = database_url.removeprefix(prefix)
    path = Path(raw_path)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return path


settings = get_settings()
database_url = settings.database_url
sqlite_path = _sqlite_path_from_url(database_url)
if sqlite_path is not None:
    sqlite_path.parent.mkdir(parents=True, exist_ok=True)
    database_url = f"sqlite:///{sqlite_path.as_posix()}"

engine = create_engine(
    database_url,
    connect_args={"check_same_thread": False} if database_url.startswith("sqlite") else {},
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def _ensure_sqlite_schema() -> None:
    if not database_url.startswith("sqlite"):
        return
    with engine.begin() as connection:
        metric_columns = {
            row[1]
            for row in connection.execute(text("PRAGMA table_info(sp_keyword_metrics)")).fetchall()
        }
        if metric_columns and "product_id" not in metric_columns:
            connection.execute(text("ALTER TABLE sp_keyword_metrics ADD COLUMN product_id INTEGER"))
        connection.execute(
            text("CREATE INDEX IF NOT EXISTS ix_sp_keyword_metrics_product_id ON sp_keyword_metrics (product_id)")
        )
        product_columns = {
            row[1]
            for row in connection.execute(text("PRAGMA table_info(products)")).fetchall()
        }
        if product_columns and "inventory_quantity" not in product_columns:
            connection.execute(text("ALTER TABLE products ADD COLUMN inventory_quantity INTEGER"))
        decision_columns = {
            row[1]
            for row in connection.execute(text("PRAGMA table_info(manual_decisions)")).fetchall()
        }
        if decision_columns and "observe_period" not in decision_columns:
            connection.execute(text("ALTER TABLE manual_decisions ADD COLUMN observe_period VARCHAR(16)"))
        suggestion_columns = {
            row[1]
            for row in connection.execute(text("PRAGMA table_info(ai_suggestions)")).fetchall()
        }
        if suggestion_columns and "recommended_manual_decision" not in suggestion_columns:
            connection.execute(text("ALTER TABLE ai_suggestions ADD COLUMN recommended_manual_decision VARCHAR(32)"))


def init_db() -> None:
    from app.models import ad_metrics, anomaly, decision, market, product, review, suggestion, sync  # noqa: F401

    Base.metadata.create_all(bind=engine)
    _ensure_sqlite_schema()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
