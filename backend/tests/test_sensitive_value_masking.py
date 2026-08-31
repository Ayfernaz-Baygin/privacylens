import pytest

from backend.app.services.sensitive_value_masking import (
    mask_sensitive_value,
)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("Ayşe", "A**e"),
        ("Ayşe Yılmaz", "A**e Y****z"),
        ("A", "*"),
        ("Ad", "**"),
        ("Çağla\tÖztürk", "Ç***a\tÖ****k"),
    ],
)
def test_masks_person_words_and_preserves_whitespace(value, expected):
    assert mask_sensitive_value(value, "PERSON") == expected


def test_masks_location_with_turkish_unicode():
    assert mask_sensitive_value("İzmir", "LOCATION") == "İ***r"


def test_masks_organization_per_word():
    assert (
        mask_sensitive_value("ABC Teknoloji", "ORGANIZATION")
        == "A*C T*******i"
    )


@pytest.mark.parametrize(
    ("finding_type", "value", "expected"),
    [
        ("PHONE", "05321234567", "0*********7"),
        (
            "PHONE",
            "0 532-123-45-67",
            "0 ***-***-**-*7",
        ),
        (
            "IBAN",
            "TR330006100519786457841326",
            "T************************6",
        ),
        (
            "IBAN",
            "TR33 0006 1005 1978 6457 8413 26",
            "T*** **** **** **** **** **** *6",
        ),
        (
            "CARD_NUMBER",
            "4111-1111-1111-1111",
            "4***-****-****-***1",
        ),
    ],
)
def test_masks_identifier_types_and_preserves_separators(
    finding_type,
    value,
    expected,
):
    assert mask_sensitive_value(value, finding_type) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (
            "ayse.yilmaz@example.com",
            "a*********z@e*****e.com",
        ),
        ("a@example.com", "*@e*****e.com"),
        ("ab@example.com", "**@e*****e.com"),
    ],
)
def test_masks_email_structure(value, expected):
    assert mask_sensitive_value(value, "EMAIL") == expected


def test_malformed_email_is_fully_masked():
    value = "not-an-email"

    assert mask_sensitive_value(value, "EMAIL") == "*" * len(value)


def test_tckn_is_fully_masked():
    assert (
        mask_sensitive_value("12345678901", "TCKN")
        == "***********"
    )


def test_empty_value_stays_empty():
    assert mask_sensitive_value("", "PERSON") == ""


def test_unknown_type_masks_all_alphanumeric_characters():
    assert (
        mask_sensitive_value("Secret-42", "UNEXPECTED")
        == "******-**"
    )
