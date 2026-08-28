from pathlib import Path

import pymupdf


def extract_text_from_pdf(file_path: Path) -> dict:
    document = pymupdf.open(file_path)

    pages = []

    try:
        for page_number, page in enumerate(document):
            text = page.get_text("text")

            pages.append(
                {
                    "page_number": page_number + 1,
                    "text": text,
                }
            )

        return {
            "page_count": len(document),
            "pages": pages,
        }

    finally:
        document.close()