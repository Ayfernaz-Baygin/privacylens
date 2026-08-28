import re


EMAIL_PATTERN = re.compile(
    r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"
)


def detect_emails(text: str) -> list[dict]:
    findings = []

    for match in EMAIL_PATTERN.finditer(text):
        findings.append(
            {
                "type": "EMAIL",
                "value": match.group(0),
                "start": match.start(),
                "end": match.end(),
                "confidence": 0.99,
                "source": "rule_engine",
            }
        )

    return findings