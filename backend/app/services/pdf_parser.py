from math import isfinite
from pathlib import Path

import pymupdf


MIN_IMAGE_PAGE_AREA_RATIO = 0.20
MIN_NATIVE_WORD_IMAGE_COVERAGE_RATIO = 0.05
HYBRID_DUPLICATE_BBOX_OVERLAP_RATIO = 0.80
HYBRID_SOURCE_SEPARATOR = "\n|\n"
OCR_FONT_NAME = "GlyphLessFont"


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
    if isinstance(bbox, dict):
        coordinates = (
            bbox["x0"],
            bbox["y0"],
            bbox["x1"],
            bbox["y1"],
        )
    elif all(
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


def _bbox_area(bbox) -> float:
    return _intersection_area(bbox, bbox)


def _bbox_overlap_ratio(first_bbox, second_bbox) -> float:
    smaller_area = min(
        _bbox_area(first_bbox),
        _bbox_area(second_bbox),
    )

    if smaller_area <= 0:
        return 0.0

    return _intersection_area(first_bbox, second_bbox) / smaller_area


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


def _normalize_hybrid_text(text: str) -> str:
    return " ".join(text.casefold().split())


def _extract_hybrid_spans(page, text_page) -> list[dict]:
    raw_text = page.get_text(
        "rawdict",
        textpage=text_page,
        sort=True,
    )
    spans = []
    line_number = 0

    for block in raw_text.get("blocks", []):
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                span_text = "".join(
                    character.get("c", "")
                    for character in span.get("chars", [])
                )

                if not span_text:
                    continue

                x0, y0, x1, y1 = span["bbox"]
                spans.append(
                    {
                        "text": span_text,
                        "source": (
                            "ocr"
                            if span.get("font") == OCR_FONT_NAME
                            else "native"
                        ),
                        "bbox": {
                            "x0": x0,
                            "y0": y0,
                            "x1": x1,
                            "y1": y1,
                        },
                        "line_number": line_number,
                    }
                )

            line_number += 1

    return spans


def _deduplicate_hybrid_spans(spans: list[dict]) -> list[dict]:
    native_spans = [
        span
        for span in spans
        if span["source"] == "native"
    ]
    deduplicated = []

    for span in spans:
        if span["source"] != "ocr":
            deduplicated.append(span)
            continue

        normalized_text = _normalize_hybrid_text(span["text"])
        is_duplicate = any(
            normalized_text
            and normalized_text
            == _normalize_hybrid_text(native_span["text"])
            and _bbox_overlap_ratio(
                span["bbox"],
                native_span["bbox"],
            )
            >= HYBRID_DUPLICATE_BBOX_OVERLAP_RATIO
            for native_span in native_spans
        )

        if not is_duplicate:
            deduplicated.append(span)

    return deduplicated


def _build_hybrid_text_and_regions(
    spans: list[dict],
) -> tuple[str, list[dict]]:
    text_parts = []
    regions = []
    offset = 0
    source_has_text = False

    for source in ("native", "ocr"):
        source_spans = [
            span
            for span in spans
            if span["source"] == source
        ]

        if not source_spans:
            continue

        if source_has_text:
            text_parts.append(HYBRID_SOURCE_SEPARATOR)
            offset += len(HYBRID_SOURCE_SEPARATOR)

        previous_line_number = None

        for span in source_spans:
            if (
                previous_line_number is not None
                and span["line_number"] != previous_line_number
            ):
                text_parts.append("\n")
                offset += 1

            start = offset
            end = start + len(span["text"])
            text_parts.append(span["text"])
            regions.append(
                {
                    "start": start,
                    "end": end,
                    "text": span["text"],
                    "source": source,
                    "bbox": span["bbox"].copy(),
                }
            )
            offset = end
            previous_line_number = span["line_number"]

        source_has_text = True

    return "".join(text_parts), regions


def _extract_hybrid_text_and_regions(
    page,
    text_page,
) -> tuple[str, list[dict]]:
    spans = _extract_hybrid_spans(page, text_page)
    deduplicated_spans = _deduplicate_hybrid_spans(spans)
    return _build_hybrid_text_and_regions(deduplicated_spans)


def extract_text_from_pdf(file_path: Path) -> dict:
    document = pymupdf.open(file_path)

    pages = []

    try:
        for page_number, page in enumerate(document):
            text = page.get_text("text")
            text_source = classify_pdf_page(page, text)

            if text_source == "native":
                parsed_page = {
                    "page_number": page_number + 1,
                    "text": text,
                    "text_source": text_source,
                    "regions": [],
                }
            elif text_source == "ocr":
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
            else:
                try:
                    text_page = page.get_textpage_ocr(
                        language="tur+eng",
                        dpi=300,
                        full=False,
                    )
                    hybrid_text, regions = (
                        _extract_hybrid_text_and_regions(
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
                    "text": hybrid_text,
                    "text_source": "hybrid",
                    "regions": regions,
                }

            pages.append(parsed_page)

        return {
            "page_count": len(document),
            "pages": pages,
        }

    finally:
        document.close()
