from pathlib import Path

import pymupdf


def locate_text_in_pdf(
    file_path: Path,
    page_number: int,
    value: str,
) -> list[dict]:
    document = pymupdf.open(file_path)

    try:
        if page_number < 1 or page_number > len(document):
            return []

        page = document[page_number - 1]

        rectangles = page.search_for(value)

        bounding_boxes = []

        for rectangle in rectangles:
            bounding_boxes.append(
                {
                    "x0": rectangle.x0,
                    "y0": rectangle.y0,
                    "x1": rectangle.x1,
                    "y1": rectangle.y1,
                }
            )

        return bounding_boxes

    finally:
        document.close()