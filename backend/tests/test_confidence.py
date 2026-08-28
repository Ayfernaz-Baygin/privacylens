from backend.app.services.confidence import (
    enrich_finding_confidence,
    get_confidence_level,
)


def test_high_confidence():
    assert get_confidence_level(0.99) == "HIGH"


def test_medium_confidence():
    assert get_confidence_level(0.72) == "MEDIUM"


def test_low_confidence():
    assert get_confidence_level(0.52) == "LOW"


def test_enrich_finding_confidence():
    finding = {
        "type": "PERSON",
        "value": "Ayşe Yılmaz",
        "confidence": 0.52,
    }

    result = enrich_finding_confidence(finding)

    assert result["confidence"] == 0.52
    assert result["confidence_level"] == "LOW"