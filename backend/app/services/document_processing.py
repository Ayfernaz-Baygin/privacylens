from pathlib import Path

from backend.app.services.detection_engine import detect_sensitive_data
from backend.app.services.docx_parser import extract_text_from_docx
from backend.app.services.pdf_locator import locate_text_in_pdf
from backend.app.services.pdf_parser import (
    PdfOcrError,
    extract_text_from_pdf,
)
from backend.app.services.xlsx_parser import extract_text_from_xlsx


class UnsupportedDocumentFormatError(Exception):
    """No PDF, DOCX, or XLSX source was found."""


class DocumentParseError(Exception):
    """The selected parser could not read the source file."""

    def __init__(
        self,
        document_format: str,
        detail: str | None = None,
    ):
        super().__init__(detail or document_format)
        self.document_format = document_format
        self.detail = detail


def build_finding_id(finding: dict) -> str:
    return (
        f"{finding['page_number']}:"
        f"{finding['start']}:"
        f"{finding['end']}:"
        f"{finding['type']}"
    )


def locate_finding_in_ocr_regions(
    finding: dict,
    regions: list[dict],
) -> list[dict]:
    return _locate_finding_in_pdf_regions(finding, regions)


def locate_finding_in_hybrid_regions(
    finding: dict,
    regions: list[dict],
) -> list[dict]:
    return _locate_finding_in_pdf_regions(finding, regions)


def _locate_finding_in_pdf_regions(
    finding: dict,
    regions: list[dict],
) -> list[dict]:
    finding_start = finding["start"]
    finding_end = finding["end"]
    intersections = []

    for region in regions:
        intersection_start = max(region["start"], finding_start)
        intersection_end = min(region["end"], finding_end)

        if intersection_start >= intersection_end:
            continue

        intersections.append(
            {
                "absolute_start": intersection_start,
                "absolute_end": intersection_end,
                "bbox": region["bbox"],
            }
        )

    intersections.sort(key=lambda item: item["absolute_start"])

    for index, intersection in enumerate(intersections[:-1]):
        next_start = intersections[index + 1]["absolute_start"]
        intersection["absolute_end"] = next_start

    if intersections:
        intersections[0]["absolute_start"] = finding_start
        intersections[-1]["absolute_end"] = finding_end

    bounding_boxes_by_coordinates = {}

    for intersection in intersections:
        bbox = intersection["bbox"]
        coordinates = (
            bbox["x0"],
            bbox["y0"],
            bbox["x1"],
            bbox["y1"],
        )
        relative_start = (
            intersection["absolute_start"] - finding_start
        )
        relative_end = intersection["absolute_end"] - finding_start
        existing = bounding_boxes_by_coordinates.get(coordinates)

        if existing is not None:
            existing["start"] = min(existing["start"], relative_start)
            existing["end"] = max(existing["end"], relative_end)
            continue

        bounding_boxes_by_coordinates[coordinates] = {
            **bbox,
            "start": relative_start,
            "end": relative_end,
        }

    return list(bounding_boxes_by_coordinates.values())


def analyze_document_file(
    pdf_path: Path,
    docx_path: Path,
    xlsx_path: Path,
) -> dict:
    """Parses whichever of pdf_path/docx_path/xlsx_path exists and
    returns document_format ("pdf"/"docx"/"xlsx") plus findings with
    bounding_boxes and finding_id already attached.

    Native PDF findings get real bounding_boxes via locate_text_in_pdf;
    OCR and hybrid PDF findings use the parser's offset-based regions.
    DOCX and XLSX have no page/coordinate concept yet, so their findings
    get bounding_boxes=[]. For XLSX, each sheet is treated as one "page"
    (the parser already numbers page_number by sheet order and sets
    page_count to the sheet count), so detection and finding_id run per
    sheet exactly like they run per PDF page.
    Raises UnsupportedDocumentFormatError if none of the files exist,
    and DocumentParseError (carrying "pdf"/"docx"/"xlsx") if the parser
    fails.
    """
    if pdf_path.exists():
        document_format = "pdf"

        try:
            parsed_document = extract_text_from_pdf(pdf_path)
        except PdfOcrError as error:
            raise DocumentParseError(
                "pdf",
                detail=str(error),
            ) from error
        except Exception as error:
            raise DocumentParseError("pdf") from error

    elif docx_path.exists():
        document_format = "docx"

        try:
            parsed_document = extract_text_from_docx(docx_path)
        except Exception as error:
            raise DocumentParseError("docx") from error

    elif xlsx_path.exists():
        document_format = "xlsx"

        try:
            parsed_document = extract_text_from_xlsx(xlsx_path)
        except Exception as error:
            raise DocumentParseError("xlsx") from error

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
                text_source = page.get("text_source", "native")

                if text_source == "ocr":
                    finding["bounding_boxes"] = (
                        locate_finding_in_ocr_regions(
                            finding=finding,
                            regions=page.get("regions", []),
                        )
                    )
                elif text_source == "hybrid":
                    finding["bounding_boxes"] = (
                        locate_finding_in_hybrid_regions(
                            finding=finding,
                            regions=page.get("regions", []),
                        )
                    )
                else:
                    finding["bounding_boxes"] = locate_text_in_pdf(
                        file_path=pdf_path,
                        page_number=page["page_number"],
                        value=finding["value"],
                        finding_start=finding["start"],
                        finding_end=finding["end"],
                        page_text=page["text"],
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
