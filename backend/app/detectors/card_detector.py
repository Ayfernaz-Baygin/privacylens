import re


CARD_PATTERN = re.compile(
    r"(?<!\d)"
    r"(?:\d[ -]?){12,18}\d"
    r"(?!\d)"
)


def normalize_card_number(value: str) -> str:
    return re.sub(r"[\s-]+", "", value)


def is_valid_card_number(value: str) -> bool:
    card_number = normalize_card_number(value)

    if not card_number.isdigit():
        return False

    if not 13 <= len(card_number) <= 19:
        return False

    total = 0
    reverse_digits = card_number[::-1]

    for index, digit_character in enumerate(reverse_digits):
        digit = int(digit_character)

        if index % 2 == 1:
            digit *= 2

            if digit > 9:
                digit -= 9

        total += digit

    return total % 10 == 0


def detect_card_numbers(text: str) -> list[dict]:
    findings = []

    for match in CARD_PATTERN.finditer(text):
        value = match.group(0).strip()

        if not is_valid_card_number(value):
            continue

        findings.append(
            {
                "type": "CARD_NUMBER",
                "value": value,
                "normalized_value": normalize_card_number(value),
                "start": match.start(),
                "end": match.end(),
                "confidence": 0.99,
                "source": "rule_engine",
            }
        )

    return findings