from backend.app.services.detection_engine import detect_sensitive_data


def test_detection_engine_detects_multiple_types():
    text = (
        "E-mail: test@example.com\n"
        "Telefon: 0532 123 45 67\n"
        "Kart: 4111 1111 1111 1111"
    )

    findings = detect_sensitive_data(
        text=text,
        page_number=3,
    )

    types = [
        finding["type"]
        for finding in findings
    ]

    assert types == [
        "EMAIL",
        "PHONE",
        "CARD_NUMBER",
    ]


def test_detection_engine_adds_page_number():
    text = "E-mail: test@example.com"

    findings = detect_sensitive_data(
        text=text,
        page_number=7,
    )

    assert findings[0]["page_number"] == 7


def test_detection_engine_returns_document_order():
    text = (
        "Kart: 4111 1111 1111 1111\n"
        "E-mail: test@example.com"
    )

    findings = detect_sensitive_data(text)

    assert findings[0]["type"] == "CARD_NUMBER"
    assert findings[1]["type"] == "EMAIL"



def test_detection_engine_can_include_ner(monkeypatch):
    def fake_detect_named_entities(text):
        return [
            {
                "type": "PERSON",
                "value": "Ayşe Yılmaz",
                "start": 0,
                "end": 11,
                "confidence": 0.95,
                "source": "ner_model",
            }
        ]

    monkeypatch.setattr(
        "backend.app.services.detection_engine.detect_named_entities",
        fake_detect_named_entities,
    )

    findings = detect_sensitive_data(
        text="Ayşe Yılmaz",
        page_number=2,
        include_ner=True,
    )

    assert len(findings) == 1
    assert findings[0]["type"] == "PERSON"
    assert findings[0]["value"] == "Ayşe Yılmaz"
    assert findings[0]["page_number"] == 2
    assert findings[0]["source"] == "ner_model"    