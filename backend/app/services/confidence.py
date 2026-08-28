HIGH_CONFIDENCE_THRESHOLD = 0.85
MEDIUM_CONFIDENCE_THRESHOLD = 0.60


def get_confidence_level(confidence: float) -> str:
    if confidence >= HIGH_CONFIDENCE_THRESHOLD:
        return "HIGH"

    if confidence >= MEDIUM_CONFIDENCE_THRESHOLD:
        return "MEDIUM"

    return "LOW"


def enrich_finding_confidence(finding: dict) -> dict:
    enriched = finding.copy()

    confidence = float(
        enriched.get("confidence", 0.0)
    )

    enriched["confidence"] = confidence
    enriched["confidence_level"] = get_confidence_level(
        confidence
    )

    return enriched