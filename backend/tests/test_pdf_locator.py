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
    assert bounding_box["start"] == 0
    assert bounding_box["end"] == len("test@example.com")


def test_native_finding_offsets_select_only_the_requested_occurrence(
    tmp_path,
):
    pdf_path = tmp_path / "repeated.pdf"
    value = "same@example.com"

    document = pymupdf.open()
    page = document.new_page()
    page.insert_text((72, 72), f"{value} and {value}")
    document.save(pdf_path)
    document.close()

    document = pymupdf.open(pdf_path)
    page_text = document[0].get_text("text")
    all_rectangles = document[0].search_for(value)
    document.close()
    finding_start = page_text.rindex(value)

    bounding_boxes = locate_text_in_pdf(
        file_path=pdf_path,
        page_number=1,
        value=value,
        finding_start=finding_start,
        finding_end=finding_start + len(value),
        page_text=page_text,
    )

    assert len(bounding_boxes) == 1
    assert bounding_boxes[0]["x0"] == all_rectangles[1].x0
    assert bounding_boxes[0]["start"] == 0
    assert bounding_boxes[0]["end"] == len(value)
