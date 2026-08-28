import pymupdf

from backend.app.services.pdf_redactor import create_redacted_pdf


def test_create_redacted_pdf_removes_text(tmp_path):
    source_path = tmp_path / "source.pdf"
    output_path = tmp_path / "redacted.pdf"

    document = pymupdf.open()
    page = document.new_page()

    page.insert_text(
        (72, 72),
        "Email: test@example.com",
    )

    document.save(source_path)
    document.close()

    source_document = pymupdf.open(source_path)

    try:
        page = source_document[0]
        rectangles = page.search_for("test@example.com")

        assert len(rectangles) == 1

        rectangle = rectangles[0]

        bounding_box = {
            "x0": rectangle.x0,
            "y0": rectangle.y0,
            "x1": rectangle.x1,
            "y1": rectangle.y1,
        }

    finally:
        source_document.close()

    findings = [
        {
            "type": "EMAIL",
            "value": "test@example.com",
            "page_number": 1,
            "bounding_boxes": [
                bounding_box
            ],
        }
    ]

    result_path = create_redacted_pdf(
        source_path=source_path,
        output_path=output_path,
        findings=findings,
    )

    assert result_path.exists()

    redacted_document = pymupdf.open(result_path)

    try:
        page = redacted_document[0]
        text = page.get_text()

        assert "test@example.com" not in text

    finally:
        redacted_document.close()