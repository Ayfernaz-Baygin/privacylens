from html import escape
from pathlib import Path

import pymupdf

from backend.app.services.sensitive_value_masking import (
    mask_sensitive_value,
)


MASK_BOX_PADDING = 1
MASK_FONT_SIZE_POINTS = 11
MASK_CSS = (
    "* {font-family: sans-serif; font-size: 11pt; color: black; "
    "white-space: pre;} body {margin: 0;}"
)


def _mask_segment(mask: str, box: dict, value_length: int) -> str:
    start = box.get("start")
    end = box.get("end")

    if (
        not isinstance(start, int)
        or not isinstance(end, int)
        or start < 0
        or end <= start
        or end > len(mask)
    ):
        return "*" * value_length

    return mask[start:end]


def _render_mask_segment(page, rectangle, segment: str) -> None:
    segment = segment.replace("\r", " ").replace("\n", " ")
    segment = segment.replace("\t", " ")

    if not segment:
        return

    text_rectangle = pymupdf.Rect(
        rectangle.x0 + MASK_BOX_PADDING,
        rectangle.y0 + MASK_BOX_PADDING,
        rectangle.x1 - MASK_BOX_PADDING,
        rectangle.y1 - MASK_BOX_PADDING,
    )

    if text_rectangle.is_empty:
        return

    page.insert_htmlbox(
        text_rectangle,
        f"<span>{escape(segment)}</span>",
        css=MASK_CSS,
        scale_low=0,
        overlay=True,
    )


def create_redacted_pdf(
    source_path: Path,
    output_path: Path,
    findings: list[dict],
) -> Path:
    document = pymupdf.open(source_path)

    try:
        affected_pages = set()
        mask_segments = []

        for finding in findings:
            page_number = finding.get("page_number")
            bounding_boxes = finding.get("bounding_boxes", [])

            if page_number is None:
                continue

            if page_number < 1 or page_number > len(document):
                continue

            page = document[page_number - 1]
            value = finding.get("value", "")
            mask = mask_sensitive_value(
                value,
                finding.get("type", ""),
            )

            for box in bounding_boxes:
                rectangle = pymupdf.Rect(
                    box["x0"],
                    box["y0"],
                    box["x1"],
                    box["y1"],
                )

                page.add_redact_annot(
                    rectangle,
                    fill=(1, 1, 1),
                )

                affected_pages.add(page_number)
                mask_segments.append(
                    (
                        page_number,
                        rectangle,
                        _mask_segment(mask, box, len(value)),
                    )
                )

        for page_number in affected_pages:
            page = document[page_number - 1]
            page.apply_redactions()

        for page_number, rectangle, segment in mask_segments:
            page = document[page_number - 1]
            _render_mask_segment(page, rectangle, segment)

        document.save(
            output_path,
            garbage=4,
            deflate=True,
        )

    finally:
        document.close()

    return output_path
