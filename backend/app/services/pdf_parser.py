from pathlib import Path

import pymupdf


class PdfOcrError(Exception):
    """OCR could not extract text from a PDF page."""

    def __init__(self, page_number: int):
        super().__init__(
            f"OCR failed for PDF page {page_number}. "
            "Verify that Tesseract and the tur+eng language data "
            "are installed."
        )
        self.page_number = page_number


def _extract_ocr_text_and_regions(
    page,
    text_page,
) -> tuple[str, list[dict]]:
    raw_text = page.get_text(
        "rawdict",
        textpage=text_page,
        sort=True,
    )

    text_parts = []
    regions = []
    offset = 0

    for block in raw_text.get("blocks", []):
        for line in block.get("lines", []):
            line_has_text = False

            for span in line.get("spans", []):
                span_text = "".join(
                    character.get("c", "")
                    for character in span.get("chars", [])
                )

                if not span_text:
                    continue

                start = offset
                end = start + len(span_text)
                x0, y0, x1, y1 = span["bbox"]

                text_parts.append(span_text)
                regions.append(
                    {
                        "start": start,
                        "end": end,
                        "text": span_text,
                        "bbox": {
                            "x0": x0,
                            "y0": y0,
                            "x1": x1,
                            "y1": y1,
                        },
                    }
                )
                offset = end
                line_has_text = True

            if line_has_text:
                text_parts.append("\n")
                offset += 1

    return "".join(text_parts), regions


def extract_text_from_pdf(file_path: Path) -> dict:
    document = pymupdf.open(file_path)

    pages = []

    try:
        for page_number, page in enumerate(document):
            text = page.get_text("text")

            if text.strip():
                parsed_page = {
                    "page_number": page_number + 1,
                    "text": text,
                    "text_source": "native",
                    "regions": [],
                }
            else:
                try:
                    text_page = page.get_textpage_ocr(
                        language="tur+eng",
                        dpi=300,
                        full=True,
                    )
                    ocr_text, regions = (
                        _extract_ocr_text_and_regions(
                            page,
                            text_page,
                        )
                    )
                except Exception as error:
                    raise PdfOcrError(
                        page_number + 1
                    ) from error

                parsed_page = {
                    "page_number": page_number + 1,
                    "text": ocr_text,
                    "text_source": "ocr",
                    "regions": regions,
                }

            pages.append(parsed_page)

        return {
            "page_count": len(document),
            "pages": pages,
        }

    finally:
        document.close()
