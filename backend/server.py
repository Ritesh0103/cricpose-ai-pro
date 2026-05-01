import logging
import os
from pathlib import Path

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

from fastapi import APIRouter, FastAPI  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402
from starlette.middleware.cors import CORSMiddleware  # noqa: E402

from app.core.config import STATIC_DIR  # noqa: E402
from app.core.db import ensure_indexes  # noqa: E402
from app.routes import analysis, auth, bowling_pipeline, compare, health, reports, users  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("cricpose")

app = FastAPI(title="CricPose AI Pro")

api_router = APIRouter(prefix="/api")
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(analysis.router)
api_router.include_router(bowling_pipeline.router)
api_router.include_router(compare.router)
api_router.include_router(reports.router)

app.include_router(api_router)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


def _cors_origins() -> list[str]:
    raw = os.environ.get("CORS_ORIGINS", "*")
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def _startup() -> None:
    try:
        await ensure_indexes()
        logger.info("Mongo indexes ensured")
    except Exception as exc:  # pragma: no cover
        logger.error("Index setup failed: %s", exc)
