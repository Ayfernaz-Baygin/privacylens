AUTO_SENSITIVE_TYPES = {
    "EMAIL",
    "PHONE",
    "TCKN",
    "IBAN",
    "CARD_NUMBER",
    "PERSON",
}

REVIEW_TYPES = {
    "LOCATION",
    "ORGANIZATION",
}


def get_privacy_status(
    finding_type: str,
) -> str:
    if finding_type in AUTO_SENSITIVE_TYPES:
        return "SENSITIVE"

    if finding_type in REVIEW_TYPES:
        return "REVIEW"

    return "UNKNOWN"


def enrich_privacy_status(
    finding: dict,
) -> dict:
    enriched = finding.copy()

    enriched["privacy_status"] = (
        get_privacy_status(
            enriched["type"]
        )
    )

    return enriched

def filter_auto_redact_findings(
    findings: list[dict],
) -> list[dict]:
    return [
        finding
        for finding in findings
        if finding.get("privacy_status") == "SENSITIVE"
    ]