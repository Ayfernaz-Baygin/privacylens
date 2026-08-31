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


# --- TASK 23.10.1 root-cause regression -------------------------------
#
# Investigated: the real repository tmp/privacylens occasionally showed
# up, empty, after a pytest run. Root cause turned out to be external to
# this test process entirely -- unrelated `uvicorn backend.app.main:app
# --reload` dev-server processes (not started by this suite) re-running
# their own module-level startup (which does
# `UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)` against the real,
# unpatched default) every time source files are edited and the
# reloader restarts. Confirmed by process inspection: both live uvicorn
# processes' start time matched the directory's mtime exactly, and a
# ~40-iteration instrumented mkdir spy around the pytest process itself
# never caught pathlib.Path.mkdir touching the real path.
#
# There is no defect in this process's own fixtures/lifecycle to fix --
# the isolation from TASK 23.9 already holds under repeated tracing.
# These tests pin that down deterministically (no sleeps) so a future
# regression in the fixture/lifecycle patching would be caught here
# instead of being mistaken for the same red herring again.


def test_full_lifespan_cycle_never_binds_the_real_default_upload_root(
    isolated_upload_root,
):
    """documents.UPLOAD_ROOT and main.UPLOAD_ROOT must never resolve to
    the real default path, before, during, or after a full FastAPI
    lifespan cycle (startup sweep + periodic task creation + shutdown)
    -- and the two must stay the identical object throughout, since
    main.py copied the reference at import time rather than sharing
    documents.py's module attribute live.
    """
    real_default = Path("tmp/privacylens")

    assert documents_module.UPLOAD_ROOT != real_default
    assert main_module.UPLOAD_ROOT != real_default

    with TestClient(app):
        assert documents_module.UPLOAD_ROOT == isolated_upload_root
        assert main_module.UPLOAD_ROOT == isolated_upload_root
        assert (
            main_module.UPLOAD_ROOT is documents_module.UPLOAD_ROOT
        )
        assert documents_module.UPLOAD_ROOT != real_default
        assert main_module.UPLOAD_ROOT != real_default

    assert documents_module.UPLOAD_ROOT != real_default
    assert main_module.UPLOAD_ROOT != real_default


def test_lifespan_startup_sweep_never_uses_the_real_default_upload_root(
    monkeypatch, isolated_upload_root
):
    """Spies on main.cleanup_stale_documents (rather than waiting on the
    periodic loop's timing) to deterministically capture the upload_root
    the synchronous lifespan-startup sweep is called with -- no sleep
    needed, since that call happens synchronously before `lifespan`
    yields, i.e. before `with TestClient(app):` returns control here.
    """
    real_default = Path("tmp/privacylens")
    observed_roots = []

    original_cleanup = main_module.cleanup_stale_documents

    def spy_cleanup_stale_documents(upload_root, *args, **kwargs):
        observed_roots.append(upload_root)
        return original_cleanup(upload_root, *args, **kwargs)

    monkeypatch.setattr(
        main_module,
        "cleanup_stale_documents",
        spy_cleanup_stale_documents,
    )

    with TestClient(app):
        pass

    assert observed_roots
    assert all(root != real_default for root in observed_roots)
    assert all(
        root == isolated_upload_root for root in observed_roots
    )
