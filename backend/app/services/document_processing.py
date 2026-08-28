from pathlib import Path

from backend.app.services.detection_engine import detect_sensitive_data
from backend.app.services.docx_parser import extract_text_from_docx
from backend.app.services.pdf_locator import locate_text_in_pdf
from backend.app.services.pdf_parser import extract_text_from_pdf


class UnsupportedDocumentFormatError(Exception):
    """Neither a PDF nor a DOCX source was found."""


class DocumentParseError(Exception):
    """The selected parser could not read the source file."""

    def __init__(self, document_format: str):
        super().__init__(document_format)
        self.document_format = document_format


def build_finding_id(finding: dict) -> str:
    return (
        f"{finding['page_number']}:"
        f"{finding['start']}:"
        f"{finding['end']}:"
        f"{finding['type']}"
    )


def analyze_document_file(
    pdf_path: Path,
    docx_path: Path,
) -> dict:
    """Parses whichever of pdf_path/docx_path exists and returns
    document_format ("pdf"/"docx") plus findings with bounding_boxes and
    finding_id already attached.

    PDF findings get real bounding_boxes via locate_text_in_pdf; DOCX has
    no page/coordinate concept yet, so its findings get bounding_boxes=[].
    Raises UnsupportedDocumentFormatError if neither file exists, and
    DocumentParseError (carrying "pdf"/"docx") if the parser fails.
    """
    if pdf_path.exists():
        document_format = "pdf"

        try:
            parsed_document = extract_text_from_pdf(pdf_path)
        except Exception as error:
            raise DocumentParseError("pdf") from error

    elif docx_path.exists():
        document_format = "docx"

        try:
            parsed_document = extract_text_from_docx(docx_path)
        except Exception as error:
            raise DocumentParseError("docx") from error

    else:
        raise UnsupportedDocumentFormatError()

    findings = []

    for page in parsed_document["pages"]:
        page_findings = detect_sensitive_data(
            text=page["text"],
            page_number=page["page_number"],
            include_ner=True,
        )

        for finding in page_findings:
            if document_format == "pdf":
                finding["bounding_boxes"] = locate_text_in_pdf(
                    file_path=pdf_path,
                    page_number=page["page_number"],
                    value=finding["value"],
                )
            else:
                finding["bounding_boxes"] = []

            finding["finding_id"] = build_finding_id(finding)

        findings.extend(page_findings)

    return {
        "document_format": document_format,
        "page_count": parsed_document["page_count"],
        "findings": findings,
    }
