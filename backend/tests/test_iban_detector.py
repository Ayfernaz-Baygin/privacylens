from backend.app.detectors.iban_detector import (
    detect_ibans,
    is_valid_iban,
    normalize_iban,
)


def test_normalize_iban():
    value = "TR33 0006 1005 1978 6457 8413 26"

    assert normalize_iban(value) == "TR330006100519786457841326"


def test_valid_turkish_iban():
    assert is_valid_iban("TR330006100519786457841326") is True


def test_invalid_iban_checksum():
    assert is_valid_iban("TR340006100519786457841326") is False


def test_detect_iban_in_text():
    text = "Ödeme hesabı: TR33 0006 1005 1978 6457 8413 26"

    findings = detect_ibans(text)

    assert len(findings) == 1
    assert findings[0]["type"] == "IBAN"