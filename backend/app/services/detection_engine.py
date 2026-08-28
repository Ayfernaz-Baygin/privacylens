from backend.app.detectors.card_detector import detect_card_numbers
from backend.app.detectors.email_detector import detect_emails
from backend.app.detectors.iban_detector import detect_ibans
from backend.app.detectors.phone_detector import detect_phone_numbers
from backend.app.detectors.tckn_detector import detect_tckn


DETECTORS = (
    detect_emails,
    detect_phone_numbers,
    detect_tckn,
    detect_ibans,
    detect_card_numbers,
)


def detect_sensitive_data(
    text: str,
    page_number: int | None = None,
) -> list[dict]:
    findings = []

    for detector in DETECTORS:
        detector_findings = detector(text)

        for finding in detector_findings:
            finding = finding.copy()

            if page_number is not None:
                finding["page_number"] = page_number

            findings.append(finding)

    findings.sort(
        key=lambda finding: finding["start"]
    )

    return findings