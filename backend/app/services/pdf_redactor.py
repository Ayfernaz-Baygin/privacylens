from pathlib import Path

import pymupdf


def create_redacted_pdf(
    source_path: Path,
    output_path: Path,
    findings: list[dict],
) -> Path:
    document = pymupdf.open(source_path)

    try:
        affected_pages = set()

        for finding in findings:
            page_number = finding.get("page_number")
            bounding_boxes = finding.get("bounding_boxes", [])

            if page_number is None:
                continue

            if page_number < 1 or page_number > len(document):
                continue

            page = document[page_number - 1]

            for box in bounding_boxes:
                rectangle = pymupdf.Rect(
                    box["x0"],
                    box["y0"],
                    box["x1"],
                    box["y1"],
                )

                page.add_redact_annot(
                    rectangle,
                    fill=(0, 0, 0),
                )

                affected_pages.add(page_number)

        for page_number in affected_pages:
            page = document[page_number - 1]
            page.apply_redactions()

        document.save(output_path)

    finally:
        document.close()

    return output_path