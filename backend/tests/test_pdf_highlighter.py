import pymupdf

from backend.app.services.pdf_highlighter import create_highlighted_pdf


def test_create_highlighted_pdf(tmp_path):
    source_path = tmp_path / "source.pdf"
    output_path = tmp_path / "highlighted.pdf"

    document = pymupdf.open()
    page = document.new_page()

    page.insert_text(
        (72, 72),
        "Email: test@example.com",
    )

    document.save(source_path)
    document.close()

    findings = [
        {
            "type": "EMAIL",
            "value": "test@example.com",
            "page_number": 1,
            "bounding_boxes": [
                {
                    "x0": 104,
                    "y0": 60,
                    "x1": 190,
                    "y1": 76,
                }
            ],
        }
    ]

    result_path = create_highlighted_pdf(
        source_path=source_path,
        output_path=output_path,
        findings=findings,
    )

    assert result_path.exists()

    highlighted_document = pymupdf.open(result_path)

    try:
        page = highlighted_document[0]
        annotations = list(page.annots() or [])

        assert len(annotations) == 1

    finally:
        highlighted_document.close()