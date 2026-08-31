from math import isfinite
from pathlib import Path

import pymupdf


MIN_IMAGE_PAGE_AREA_RATIO = 0.20
MIN_NATIVE_WORD_IMAGE_COVERAGE_RATIO = 0.05


class PdfOcrError(Exception):
    """OCR could not extract text from a PDF page."""

    def __init__(self, page_number: int):
        super().__init__(
            f"OCR failed for PDF page {page_number}. "
            "Verify that Tesseract and the tur+eng language data "
            "are installed."
        )
        self.page_number = page_number


def _bbox_coordinates(bbox) -> tuple[float, float, float, float]:
    if all(
        hasattr(bbox, coordinate)
        for coordinate in ("x0", "y0", "x1", "y1")
    ):
        coordinates = bbox.x0, bbox.y0, bbox.x1, bbox.y1
    else:
        coordinates = bbox[0], bbox[1], bbox[2], bbox[3]

    return tuple(float(coordinate) for coordinate in coordinates)


def _intersection_area(first_bbox, second_bbox) -> float:
    try:
        first_x0, first_y0, first_x1, first_y1 = (
            _bbox_coordinates(first_bbox)
        )
        second_x0, second_y0, second_x1, second_y1 = (
            _bbox_coordinates(second_bbox)
        )
    except (IndexError, KeyError, TypeError, ValueError):
        return 0.0

    if not all(
        isfinite(coordinate)
        for coordinate in (
            first_x0,
            first_y0,
            first_x1,
            first_y1,
            second_x0,
            second_y0,
            second_x1,
            second_y1,
        )
    ):
        return 0.0

    width = min(first_x1, second_x1) - max(first_x0, second_x0)
    height = min(first_y1, second_y1) - max(first_y0, second_y0)

    if width <= 0 or height <= 0:
        return 0.0

    return width * height


def classify_pdf_page(page, native_text: str) -> str:
    if not native_text.strip():
        return "ocr"

    try:
        page_x0, page_y0, page_x1, page_y1 = (
            _bbox_coordinates(page.rect)
        )
    except (AttributeError, IndexError, TypeError, ValueError):
        return "native"

    page_area = max(0, page_x1 - page_x0) * max(
        0,
        page_y1 - page_y0,
    )

    if page_area <= 0:
        return "native"

    candidate_images = []

    for image_info in page.get_image_info():
        image_bbox = image_info.get("bbox")

        if image_bbox is None:
            continue

        image_area = _intersection_area(image_bbox, page.rect)

        if image_area / page_area >= MIN_IMAGE_PAGE_AREA_RATIO:
            candidate_images.append((image_bbox, image_area))

    if not candidate_images:
        return "native"

    native_words = page.get_text("words")

    for image_bbox, image_area in candidate_images:
        covered_area = sum(
            _intersection_area(word[:4], image_bbox)
            for word in native_words
            if len(word) >= 4
        )
        coverage_ratio = min(covered_area, image_area) / image_area

        if coverage_ratio < MIN_NATIVE_WORD_IMAGE_COVERAGE_RATIO:
            return "hybrid"

    return "native"


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
            text_source = classify_pdf_page(page, text)

            if text_source != "ocr":
                parsed_page = {
                    "page_number": page_number + 1,
                    "text": text,
                    "text_source": text_source,
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
