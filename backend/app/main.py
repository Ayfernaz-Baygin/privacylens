from fastapi import FastAPI

from .routes.documents import router as documents_router

from fastapi.middleware.cors import CORSMiddleware


app = FastAPI(
    title="PrivacyLens API",
    description="Sensitive data detection and document redaction API",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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