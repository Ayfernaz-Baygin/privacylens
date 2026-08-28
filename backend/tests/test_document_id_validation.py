import uuid
from pathlib import Path

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.routes.documents import validate_document_id


# --- Direct unit tests of the helper -------------------------------
# These don't depend on Starlette's URL/slash normalization behavior.


def test_validate_document_id_accepts_valid_uuid4():
    valid_id = str(uuid.uuid4())

    assert validate_document_id(valid_id) is None


@pytest.mark.parametrize(
    "bad_id",
    [
        "..",
        "../something",
        "../../etc",
        "../../etc/passwd",
        "not-a-uuid",
        "",
        "   ",
        "00000000-0000-0000-0000-00000000000",  # too short
        "00000000-0000-0000-0000-0000000000000",  # too long
        "ef17ccda-e4b9-198e-89b6-9039d1834706",  # well-formed, but v1
        "EF17CCDA-E4B9-498E-89B6-9039D1834706",  # valid v4, wrong case
        "{ef17ccda-e4b9-498e-89b6-9039d1834706}",  # valid v4, braces
        "urn:uuid:ef17ccda-e4b9-498e-89b6-9039d1834706",
        "ef17ccdae4b9498e89b69039d1834706",  # valid v4, no dashes
        "/etc/passwd",
        "..%2f..%2fetc",
        "C:\\Windows\\System32",
    ],
)
def test_validate_document_id_rejects_malformed_or_traversal_values(
    bad_id,
):
    with pytest.raises(HTTPException) as excinfo:
        validate_document_id(bad_id)

    assert excinfo.value.status_code == 404


def test_validate_document_id_never_touches_the_filesystem(
    monkeypatch,
):
    def exploding_exists(self):
        raise AssertionError(
            "validate_document_id must reject before any "
            "filesystem access"
        )

    monkeypatch.setattr(Path, "exists", exploding_exists)

    with pytest.raises(HTTPException) as excinfo:
        validate_document_id("../../etc/passwd")

    assert excinfo.value.status_code == 404


# --- Route-level tests -----------------------------------------------
# Confirm the helper is actually wired into the endpoints, end to end.


@pytest.mark.parametrize(
    "endpoint",
    ["text", "analyze", "highlight", "redact"],
)
def test_get_endpoints_reject_malformed_document_id(endpoint):
    client = TestClient(app)

    response = client.get(
        f"/api/documents/not-a-uuid/{endpoint}"
    )

    assert response.status_code == 404


def test_redact_selected_rejects_malformed_document_id():
    client = TestClient(app)

    response = client.post(
        "/api/documents/not-a-uuid/redact-selected",
        json={"selected_finding_ids": []},
    )

    assert response.status_code == 404


def test_analyze_rejects_percent_encoded_traversal_document_id():
    client = TestClient(app)

    response = client.get(
        "/api/documents/..%2F..%2Fetc/analyze"
    )

    assert response.status_code == 404


def test_redact_selected_rejects_percent_encoded_traversal_document_id():
    client = TestClient(app)

    response = client.post(
        "/api/documents/..%2F..%2Fetc/redact-selected",
        json={"selected_finding_ids": []},
    )

    assert response.status_code == 404


def test_analyze_returns_404_for_well_formed_but_unknown_document_id():
    client = TestClient(app)

    unknown_id = str(uuid.uuid4())

    response = client.get(
        f"/api/documents/{unknown_id}/analyze"
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Belge bulunamadı."


def test_redact_selected_returns_404_for_well_formed_but_unknown_id():
    client = TestClient(app)

    unknown_id = str(uuid.uuid4())

    response = client.post(
        f"/api/documents/{unknown_id}/redact-selected",
        json={"selected_finding_ids": []},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Belge bulunamadı."


def test_no_filesystem_access_for_invalid_id_through_full_route(
    monkeypatch,
):
    """End-to-end proof: an invalid id never reaches document_directory
    .exists(), i.e. rejection happens before any UPLOAD_ROOT lookup.
    """

    def exploding_exists(self):
        raise AssertionError(
            "no Path.exists() call should happen for an "
            "invalid document_id"
        )

    monkeypatch.setattr(Path, "exists", exploding_exists)

    client = TestClient(app)

    response = client.get(
        "/api/documents/not-a-uuid/analyze"
    )

    assert response.status_code == 404
