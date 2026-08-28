from backend.app.detectors.card_detector import (
    detect_card_numbers,
    is_valid_card_number,
    normalize_card_number,
)


def test_normalize_card_number():
    value = "4111 1111 1111 1111"

    assert normalize_card_number(value) == "4111111111111111"


def test_valid_card_number():
    assert is_valid_card_number("4111111111111111") is True


def test_invalid_luhn_checksum():
    assert is_valid_card_number("4111111111111112") is False


def test_card_number_with_hyphens():
    assert is_valid_card_number("4111-1111-1111-1111") is True


def test_detect_card_number_in_text():
    text = "Test kart numarası: 4111 1111 1111 1111"

    findings = detect_card_numbers(text)

    assert len(findings) == 1
    assert findings[0]["type"] == "CARD_NUMBER"
    assert findings[0]["normalized_value"] == "4111111111111111"