from pathlib import Path

import pytest

from backend.app.config import (
    CORS_ORIGINS_ENV_VAR,
    DEFAULT_CORS_ORIGINS,
    DEFAULT_UPLOAD_ROOT,
    UPLOAD_ROOT_ENV_VAR,
    get_cors_origins,
    get_upload_root,
)


# --- get_upload_root -----------------------------------------------


def test_get_upload_root_uses_default_when_unset(monkeypatch):
    monkeypatch.delenv(UPLOAD_ROOT_ENV_VAR, raising=False)

    assert get_upload_root() == Path(DEFAULT_UPLOAD_ROOT)


def test_get_upload_root_uses_custom_value(monkeypatch):
    monkeypatch.setenv(UPLOAD_ROOT_ENV_VAR, "custom/storage/path")

    assert get_upload_root() == Path("custom/storage/path")


def test_get_upload_root_falls_back_on_blank_value(monkeypatch):
    monkeypatch.setenv(UPLOAD_ROOT_ENV_VAR, "   ")

    assert get_upload_root() == Path(DEFAULT_UPLOAD_ROOT)


def test_get_upload_root_trims_whitespace(monkeypatch):
    monkeypatch.setenv(UPLOAD_ROOT_ENV_VAR, "  custom/path  ")

    assert get_upload_root() == Path("custom/path")


# --- get_cors_origins -------------------------------------------------


def test_get_cors_origins_uses_default_when_unset(monkeypatch):
    monkeypatch.delenv(CORS_ORIGINS_ENV_VAR, raising=False)

    assert get_cors_origins() == list(DEFAULT_CORS_ORIGINS)


def test_get_cors_origins_parses_comma_separated_list(monkeypatch):
    monkeypatch.setenv(
        CORS_ORIGINS_ENV_VAR,
        "https://app.example.com,https://admin.example.com",
    )

    assert get_cors_origins() == [
        "https://app.example.com",
        "https://admin.example.com",
    ]


def test_get_cors_origins_trims_whitespace_around_entries(monkeypatch):
    monkeypatch.setenv(
        CORS_ORIGINS_ENV_VAR,
        " https://app.example.com , https://admin.example.com ",
    )

    assert get_cors_origins() == [
        "https://app.example.com",
        "https://admin.example.com",
    ]


def test_get_cors_origins_drops_empty_entries(monkeypatch):
    monkeypatch.setenv(
        CORS_ORIGINS_ENV_VAR,
        "https://app.example.com,,https://admin.example.com,",
    )

    assert get_cors_origins() == [
        "https://app.example.com",
        "https://admin.example.com",
    ]


def test_get_cors_origins_falls_back_on_blank_value(monkeypatch):
    monkeypatch.setenv(CORS_ORIGINS_ENV_VAR, "   ")

    assert get_cors_origins() == list(DEFAULT_CORS_ORIGINS)


def test_get_cors_origins_falls_back_on_only_commas(monkeypatch):
    monkeypatch.setenv(CORS_ORIGINS_ENV_VAR, " , , ")

    assert get_cors_origins() == list(DEFAULT_CORS_ORIGINS)


def test_get_cors_origins_rejects_wildcard(monkeypatch):
    monkeypatch.setenv(CORS_ORIGINS_ENV_VAR, "*")

    with pytest.raises(ValueError):
        get_cors_origins()


def test_get_cors_origins_rejects_wildcard_mixed_with_explicit_origin(
    monkeypatch,
):
    monkeypatch.setenv(
        CORS_ORIGINS_ENV_VAR, "https://app.example.com,*"
    )

    with pytest.raises(ValueError):
        get_cors_origins()
