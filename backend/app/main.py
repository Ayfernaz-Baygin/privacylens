from fastapi import FastAPI

from .routes.documents import router as documents_router


app = FastAPI(
    title="PrivacyLens API",
    description="Sensitive data detection and document redaction API",
    version="0.1.0",
)


app.include_router(documents_router)


@app.get("/")
def root():
    return {
        "name": "PrivacyLens API",
        "version": "0.1.0",
    }


@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "service": "privacylens-api",
    }