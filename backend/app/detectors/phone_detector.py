import re


PHONE_PATTERN = re.compile(
    r"(?<!\d)"
    r"(?:\+90|0090|0)?"
    r"[\s-]?"
    r"5\d{2}"
    r"[\s-]?"
    r"\d{3}"
    r"[\s-]?"
    r"\d{2}"
    r"[\s-]?"
    r"\d{2}"
    r"(?!\d)"
)


def detect_phone_numbers(text: str) -> list[dict]:
    findings = []

    for match in PHONE_PATTERN.finditer(text):
        value = match.group(0).strip()

        findings.append(
            {
                "type": "PHONE",
                "value": value,
                "start": match.start(),
                "end": match.end(),
                "confidence": 0.95,
                "source": "rule_engine",
            }
        )

    return findings