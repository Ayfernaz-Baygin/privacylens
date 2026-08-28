ALWAYS_AUTO_REDACT_TYPES = {
    "EMAIL",
    "PHONE",
    "TCKN",
    "IBAN",
    "CARD_NUMBER",
}

ALWAYS_REVIEW_TYPES = {
    "LOCATION",
    "ORGANIZATION",
}


def get_redaction_action(
    finding: dict,
) -> str:
    finding_type = finding.get("type")
    confidence_level = finding.get(
        "confidence_level"
    )

    if finding_type in ALWAYS_AUTO_REDACT_TYPES:
        return "AUTO_REDACT"

    if finding_type in ALWAYS_REVIEW_TYPES:
        return "REVIEW"

    if finding_type == "PERSON":
        if confidence_level == "LOW":
            return "REVIEW"

        return "AUTO_REDACT"

    return "KEEP"


def enrich_redaction_action(
    finding: dict,
) -> dict:
    enriched = finding.copy()

    enriched["redaction_action"] = (
        get_redaction_action(enriched)
    )

    return enriched


def filter_auto_redact_findings(
    findings: list[dict],
) -> list[dict]:
    return [
        finding
        for finding in findings
        if finding.get("redaction_action")
        == "AUTO_REDACT"
    ]