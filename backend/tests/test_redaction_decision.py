from backend.app.services.redaction_decision import (
    enrich_redaction_action,
    filter_auto_redact_findings,
    get_redaction_action,
)

from backend.app.services.redaction_decision import (
    enrich_redaction_action,
    filter_auto_redact_findings,
    get_redaction_action,
    select_redaction_findings,
)


def test_rule_based_sensitive_data_is_auto_redacted():
    finding = {
        "type": "EMAIL",
        "confidence_level": "HIGH",
    }

    assert (
        get_redaction_action(finding)
        == "AUTO_REDACT"
    )


def test_high_confidence_person_is_auto_redacted():
    finding = {
        "type": "PERSON",
        "confidence_level": "HIGH",
    }

    assert (
        get_redaction_action(finding)
        == "AUTO_REDACT"
    )


def test_low_confidence_person_requires_review():
    finding = {
        "type": "PERSON",
        "confidence_level": "LOW",
    }

    assert (
        get_redaction_action(finding)
        == "REVIEW"
    )


def test_location_requires_review():
    finding = {
        "type": "LOCATION",
        "confidence_level": "HIGH",
    }

    assert (
        get_redaction_action(finding)
        == "REVIEW"
    )


def test_filter_auto_redact_findings():
    findings = [
        {
            "type": "EMAIL",
            "redaction_action": "AUTO_REDACT",
        },
        {
            "type": "PERSON",
            "redaction_action": "REVIEW",
        },
        {
            "type": "LOCATION",
            "redaction_action": "REVIEW",
        },
    ]

    result = filter_auto_redact_findings(findings)

    assert len(result) == 1
    assert result[0]["type"] == "EMAIL"

def test_select_redaction_findings():
    findings = [
        {
            "finding_id": "1:10:20:EMAIL",
            "type": "EMAIL",
            "redaction_action": "AUTO_REDACT",
        },
        {
            "finding_id": "1:30:40:PERSON",
            "type": "PERSON",
            "redaction_action": "REVIEW",
        },
        {
            "finding_id": "1:50:60:LOCATION",
            "type": "LOCATION",
            "redaction_action": "REVIEW",
        },
    ]

    result = select_redaction_findings(
        findings=findings,
        selected_finding_ids=[
            "1:30:40:PERSON",
        ],
    )

    assert len(result) == 2

    assert (
        result[0]["type"]
        == "EMAIL"
    )

    assert (
        result[1]["type"]
        == "PERSON"
    )
