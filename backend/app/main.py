from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.anomalies import router as anomalies_router
from app.api.routes.dashboard import router as dashboard_router
from app.api.routes.decisions import router as decisions_router
from app.api.routes.products import router as products_router
from app.api.routes.reviews import router as reviews_router
from app.api.routes.suggestions import router as suggestions_router
from app.api.routes.sync import router as sync_router
from app.core.config import get_settings
from app.core.database import init_db
from app.services.scheduler_service import start_scheduler_if_enabled, stop_scheduler


app = FastAPI(title="Amazon SP Ads Health API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup() -> None:
    init_db()
    app.state.sync_scheduler = start_scheduler_if_enabled(get_settings())


@app.on_event("shutdown")
def on_shutdown() -> None:
    stop_scheduler(getattr(app.state, "sync_scheduler", None))


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(sync_router, prefix="/api/sync", tags=["sync"])
app.include_router(dashboard_router, prefix="/api/dashboard", tags=["dashboard"])
app.include_router(anomalies_router, prefix="/api/anomalies", tags=["anomalies"])
app.include_router(products_router, prefix="/api/products", tags=["products"])
app.include_router(suggestions_router, prefix="/api/suggestions", tags=["suggestions"])
app.include_router(decisions_router, prefix="/api/decisions", tags=["decisions"])
app.include_router(reviews_router, prefix="/api/reviews", tags=["reviews"])
