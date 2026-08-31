from pathlib import Path

import pymupdf


def locate_text_in_pdf(
    file_path: Path,
    page_number: int,
    value: str,
    finding_start: int | None = None,
    finding_end: int | None = None,
    page_text: str | None = None,
) -> list[dict]:
    document = pymupdf.open(file_path)

    try:
        if page_number < 1 or page_number > len(document):
            return []

        page = document[page_number - 1]

        rectangles = page.search_for(value)

        if (
            finding_start is None
            or finding_end is None
            or page_text is None
        ):
            selected_rectangles = rectangles
        else:
            occurrence_starts = []
            search_start = 0

            while True:
                occurrence_start = page_text.find(value, search_start)

                if occurrence_start < 0:
                    break

                occurrence_starts.append(occurrence_start)
                search_start = occurrence_start + max(1, len(value))

            try:
                occurrence_index = occurrence_starts.index(finding_start)
            except ValueError:
                occurrence_index = 0

            occurrence_count = max(1, len(occurrence_starts))

            base_group_size, larger_group_count = divmod(
                len(rectangles),
                occurrence_count,
            )
            group_start = (
                occurrence_index * base_group_size
                + min(occurrence_index, larger_group_count)
            )
            group_size = base_group_size + (
                1 if occurrence_index < larger_group_count else 0
            )
            selected_rectangles = rectangles[
                group_start:group_start + group_size
            ]

        relative_starts = _relative_rectangle_starts(
            page,
            selected_rectangles,
            value,
        )
        bounding_boxes = []

        for index, rectangle in enumerate(selected_rectangles):
            relative_start = relative_starts[index]
            relative_end = (
                relative_starts[index + 1]
                if index + 1 < len(relative_starts)
                else len(value)
            )
            bounding_boxes.append(
                {
                    "x0": rectangle.x0,
                    "y0": rectangle.y0,
                    "x1": rectangle.x1,
                    "y1": rectangle.y1,
                    "start": relative_start,
                    "end": relative_end,
                }
            )

        return bounding_boxes

    finally:
        document.close()


def _relative_rectangle_starts(page, rectangles, value: str) -> list[int]:
    if not rectangles:
        return []

    starts = [0]
    cursor = 0

    for rectangle in rectangles[1:]:
        fragment = page.get_textbox(rectangle).strip()
        fragment_start = value.find(fragment, cursor) if fragment else -1

        if fragment_start < 0:
            fragment_start = round(
                len(value) * len(starts) / len(rectangles)
            )

        fragment_start = max(cursor, min(fragment_start, len(value)))
        starts.append(fragment_start)
        cursor = fragment_start

    return starts
