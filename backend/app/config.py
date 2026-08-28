import os
from pathlib import Path

# Single source of truth for env-configurable settings. Read via
# os.environ/os.getenv only -- no extra config-framework dependency.
#
# Every default below reproduces the previous hardcoded local-dev
# behavior exactly, so an unset environment leaves nothing changed.

UPLOAD_ROOT_ENV_VAR = "PRIVACYLENS_UPLOAD_ROOT"
DEFAULT_UPLOAD_ROOT = "tmp/privacylens"

CORS_ORIGINS_ENV_VAR = "PRIVACYLENS_CORS_ORIGINS"
DEFAULT_CORS_ORIGINS = (
    "http://localhost:5173",
    "http://127.0.0.1:5173",
)


def get_upload_root() -> Path:
    """Document storage root. PRIVACYLENS_UPLOAD_ROOT overrides the
    default "tmp/privacylens" used by local development.
    """
    raw = os.environ.get(UPLOAD_ROOT_ENV_VAR)

    if not raw or not raw.strip():
        return Path(DEFAULT_UPLOAD_ROOT)

    return Path(raw.strip())


def get_cors_origins() -> list[str]:
    """Allowed CORS origins, comma-separated in PRIVACYLENS_CORS_ORIGINS
    (whitespace around each entry is trimmed, empty entries dropped).

    Unset, empty, or whitespace-only -- and therefore resolving to no
    entries -- falls back to the local-dev defaults. A literal "*" is
    rejected: the API always sends allow_credentials=True, and a
    wildcard origin combined with credentials is not a safe or even
    browser-honored configuration, so it must be listed as an explicit
    mistake rather than silently accepted.
    """
    raw = os.environ.get(CORS_ORIGINS_ENV_VAR)

    if raw is None:
        return list(DEFAULT_CORS_ORIGINS)

    origins = [
        origin.strip()
        for origin in raw.split(",")
        if origin.strip()
    ]

    if not origins:
        return list(DEFAULT_CORS_ORIGINS)

    if "*" in origins:
        raise ValueError(
            f"{CORS_ORIGINS_ENV_VAR} must not contain \"*\": this API "
            "uses allow_credentials=True, and a wildcard origin is "
            "not a safe pairing with credentialed requests. List "
            "explicit origins instead."
        )

    return origins
