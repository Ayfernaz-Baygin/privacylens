from backend.app.services.privacy_policy import (
    enrich_privacy_status,
    get_privacy_status,
)


from backend.app.services.privacy_policy import (
    enrich_privacy_status,
    filter_auto_redact_findings,
    get_privacy_status,
)


def test_person_is_sensitive():
    assert (
        get_privacy_status("PERSON")
        == "SENSITIVE"
    )


def test_email_is_sensitive():
    assert (
        get_privacy_status("EMAIL")
        == "SENSITIVE"
    )


def test_location_requires_review():
    assert (
        get_privacy_status("LOCATION")
        == "REVIEW"
    )


def test_organization_requires_review():
    assert (
        get_privacy_status("ORGANIZATION")
        == "REVIEW"
    )


def test_unknown_type():
    assert (
        get_privacy_status("SOMETHING")
        == "UNKNOWN"
    )


def test_enrich_privacy_status():
    finding = {
        "type": "LOCATION",
        "value": "İstanbul",
    }

    result = enrich_privacy_status(
        finding
    )

    assert result["privacy_status"] == "REVIEW"

def test_filter_auto_redact_findings():
    findings = [
        {
            "type": "PERSON",
            "value": "Ayşe Yılmaz",
            "privacy_status": "SENSITIVE",
        },
        {
            "type": "LOCATION",
            "value": "İstanbul",
            "privacy_status": "REVIEW",
        },
        {
            "type": "EMAIL",
            "value": "test@example.com",
            "privacy_status": "SENSITIVE",
        },
    ]

    result = filter_auto_redact_findings(findings)

    assert len(result) == 2
    assert result[0]["type"] == "PERSON"
    assert result[1]["type"] == "EMAIL"
