import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from .config import get_cors_origins
from .routes.documents import UPLOAD_ROOT
from .routes.documents import router as documents_router
from .services.document_cleanup import (
    CLEANUP_INTERVAL_SECONDS,
    DOCUMENT_RETENTION_SECONDS,
    cleanup_stale_documents,
)

from fastapi.middleware.cors import CORSMiddleware

logger = logging.getLogger(__name__)


async def _periodic_cleanup_loop() -> None:
    while True:
        await asyncio.sleep(CLEANUP_INTERVAL_SECONDS)

        try:
            cleanup_stale_documents(
                UPLOAD_ROOT, DOCUMENT_RETENTION_SECONDS
            )
        except Exception:
            # A cleanup failure must never take the sweep loop (or the
            # server) down with it -- log and try again next interval.
            logger.exception("periodic document cleanup failed")


@asynccontextmanager
async def lifespan(app: FastAPI):
    cleanup_stale_documents(UPLOAD_ROOT, DOCUMENT_RETENTION_SECONDS)

    cleanup_task = asyncio.create_task(_periodic_cleanup_loop())

    try:
        yield
    finally:
        cleanup_task.cancel()

        try:
            await cleanup_task
        except asyncio.CancelledError:
            pass


app = FastAPI(
    title="PrivacyLens API",
    description="Sensitive data detection and document redaction API",
    version="0.3.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(documents_router)


@app.get("/")
def root():
    return {
        "name": "PrivacyLens API",
        "version": "0.3.0",
    }


@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "service": "privacylens-api",
    }
