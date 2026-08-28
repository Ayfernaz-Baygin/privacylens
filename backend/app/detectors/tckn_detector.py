import re


TCKN_PATTERN = re.compile(
    r"(?<!\d)[1-9]\d{10}(?!\d)"
)


def is_valid_tckn(value: str) -> bool:
    if len(value) != 11:
        return False

    if not value.isdigit():
        return False

    if value[0] == "0":
        return False

    digits = [int(digit) for digit in value]

    odd_sum = (
        digits[0]
        + digits[2]
        + digits[4]
        + digits[6]
        + digits[8]
    )

    even_sum = (
        digits[1]
        + digits[3]
        + digits[5]
        + digits[7]
    )

    tenth_digit = ((odd_sum * 7) - even_sum) % 10

    if digits[9] != tenth_digit:
        return False

    eleventh_digit = sum(digits[:10]) % 10

    if digits[10] != eleventh_digit:
        return False

    return True


def detect_tckn(text: str) -> list[dict]:
    findings = []

    for match in TCKN_PATTERN.finditer(text):
        value = match.group(0)

        if not is_valid_tckn(value):
            continue

        findings.append(
            {
                "type": "TCKN",
                "value": value,
                "start": match.start(),
                "end": match.end(),
                "confidence": 0.99,
                "source": "rule_engine",
            }
        )

    return findings