import io
from pathlib import Path

import pymupdf
from fastapi.testclient import TestClient

from backend.app import main as main_module
from backend.app.main import app
from backend.app.routes import documents as documents_module

PDF_CONTENT_TYPE = "application/pdf"


def _real_pdf_bytes() -> bytes:
    document = pymupdf.open()
    page = document.new_page()
    page.insert_text((72, 72), "E-mail: test@example.com")

    buffer = io.BytesIO()
    document.save(buffer)
    document.close()

    return buffer.getvalue()


def _upload_pdf(client) -> str:
    response = client.post(
        "/api/documents",
        files={
            "file": (
                "sample.pdf",
                io.BytesIO(_real_pdf_bytes()),
                PDF_CONTENT_TYPE,
            )
        },
    )

    assert response.status_code == 200

    return response.json()["id"]


def test_route_upload_root_is_the_isolated_test_root(
    isolated_upload_root,
):
    assert documents_module.UPLOAD_ROOT == isolated_upload_root
    assert documents_module.UPLOAD_ROOT != Path("tmp/privacylens")


def test_periodic_cleanup_root_is_the_isolated_test_root(
    isolated_upload_root,
):
    """main.py's periodic cleanup loop reads its own module-level
    UPLOAD_ROOT (copied at import time from documents.py); the
    conftest fixture must patch both bindings to the same Path or the
    loop would keep sweeping the real repository tmp/privacylens.
    """
    assert main_module.UPLOAD_ROOT == isolated_upload_root
    assert main_module.UPLOAD_ROOT is documents_module.UPLOAD_ROOT


def test_upload_creates_document_directory_only_under_isolated_root(
    isolated_upload_root,
):
    client = TestClient(app)

    document_id = _upload_pdf(client)

    assert (isolated_upload_root / document_id).exists()
    assert (
        isolated_upload_root / document_id / "source.pdf"
    ).exists()


def test_upload_storage_is_isolated_between_tests_a(
    isolated_upload_root,
):
    """Paired with _b below: each test uploads one document and expects
    to see exactly one document directory in its own isolated root. If
    UPLOAD_ROOT were shared across tests instead of freshly isolated
    per test, whichever of this pair runs second would see two.
    """
    client = TestClient(app)

    _upload_pdf(client)

    document_ids = [
        entry.name
        for entry in isolated_upload_root.iterdir()
        if entry.is_dir()
    ]

    assert len(document_ids) == 1


def test_upload_storage_is_isolated_between_tests_b(
    isolated_upload_root,
):
    client = TestClient(app)

    _upload_pdf(client)

    document_ids = [
        entry.name
        for entry in isolated_upload_root.iterdir()
        if entry.is_dir()
    ]

    assert len(document_ids) == 1


def test_redact_selected_background_cleanup_uses_isolated_root(
    monkeypatch, isolated_upload_root
):
    monkeypatch.setattr(
        "backend.app.services.detection_engine.detect_named_entities",
        lambda text: [],
    )

    client = TestClient(app)

    document_id = _upload_pdf(client)

    assert (isolated_upload_root / document_id).exists()

    response = client.post(
        f"/api/documents/{document_id}/redact-selected",
        json={"selected_finding_ids": []},
    )

    assert response.status_code == 200
    assert not (isolated_upload_root / document_id).exists()
