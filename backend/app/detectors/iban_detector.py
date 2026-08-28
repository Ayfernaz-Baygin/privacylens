import re


IBAN_PATTERN = re.compile(
    r"(?<![A-Z0-9])"
    r"TR\d{2}(?:[\s]?\d{4}){5}[\s]?\d{2}"
    r"(?![A-Z0-9])",
    re.IGNORECASE,
)


def normalize_iban(value: str) -> str:
    return re.sub(r"\s+", "", value).upper()


def is_valid_iban(value: str) -> bool:
    iban = normalize_iban(value)

    if len(iban) != 26:
        return False

    if not iban.startswith("TR"):
        return False

    if not iban[2:].isdigit():
        return False

    rearranged = iban[4:] + iban[:4]

    numeric_value = ""

    for character in rearranged:
        if character.isalpha():
            numeric_value += str(ord(character) - 55)
        else:
            numeric_value += character

    remainder = 0

    for digit in numeric_value:
        remainder = (remainder * 10 + int(digit)) % 97

    return remainder == 1


def detect_ibans(text: str) -> list[dict]:
    findings = []

    for match in IBAN_PATTERN.finditer(text):
        value = match.group(0)

        if not is_valid_iban(value):
            continue

        findings.append(
            {
                "type": "IBAN",
                "value": value,
                "normalized_value": normalize_iban(value),
                "start": match.start(),
                "end": match.end(),
                "confidence": 0.99,
                "source": "rule_engine",
            }
        )

    return findings