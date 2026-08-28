import pymupdf

from backend.app.services.pdf_locator import locate_text_in_pdf


def test_locate_text_in_pdf(tmp_path):
    pdf_path = tmp_path / "sample.pdf"

    document = pymupdf.open()
    page = document.new_page()

    page.insert_text(
        (72, 72),
        "Email: test@example.com",
    )

    document.save(pdf_path)
    document.close()

    bounding_boxes = locate_text_in_pdf(
        file_path=pdf_path,
        page_number=1,
        value="test@example.com",
    )

    assert len(bounding_boxes) == 1

    bounding_box = bounding_boxes[0]

    assert bounding_box["x0"] < bounding_box["x1"]
    assert bounding_box["y0"] < bounding_box["y1"]