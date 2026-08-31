import pymupdf

from backend.app.services.document_processing import (
    locate_finding_in_ocr_regions,
)
from backend.app.services.pdf_redactor import create_redacted_pdf


def _create_scanned_pdf(file_path):
    selected_box = pymupdf.Rect(40, 50, 140, 90)
    unselected_box = pymupdf.Rect(160, 50, 260, 90)

    image_document = pymupdf.open()
    image_page = image_document.new_page(width=300, height=160)
    image_page.draw_rect(
        selected_box,
        color=(1, 0, 0),
        fill=(1, 0, 0),
    )
    image_page.insert_text(
        (50, 75),
        "SECRET",
        color=(1, 1, 1),
        fontsize=14,
    )
    image_page.draw_rect(
        unselected_box,
        color=(0, 1, 0),
        fill=(0, 1, 0),
    )
    image_page.insert_text(
        (180, 75),
        "KEEP",
        color=(0, 0, 0),
        fontsize=14,
    )
    image_bytes = image_page.get_pixmap(
        matrix=pymupdf.Matrix(2, 2),
        alpha=False,
    ).tobytes("png")
    image_document.close()

    scanned_document = pymupdf.open()
    scanned_page = scanned_document.new_page(width=300, height=160)
    scanned_page.insert_image(
        scanned_page.rect,
        stream=image_bytes,
    )
    scanned_document.save(file_path)
    scanned_document.close()

    return selected_box, unselected_box


def _render_rgb_crop(page, rectangle, scale=2):
    pixmap = page.get_pixmap(
        matrix=pymupdf.Matrix(scale, scale),
        alpha=False,
    )
    samples = pixmap.samples
    crop = []

    x0 = round(rectangle.x0 * scale)
    y0 = round(rectangle.y0 * scale)
    x1 = round(rectangle.x1 * scale)
    y1 = round(rectangle.y1 * scale)

    for y in range(y0, y1):
        for x in range(x0, x1):
            offset = (y * pixmap.width + x) * pixmap.n
            crop.append(tuple(samples[offset:offset + 3]))

    return crop


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


def test_create_redacted_pdf_removes_selected_scanned_image_pixels(
    tmp_path,
):
    source_path = tmp_path / "scanned-source.pdf"
    output_path = tmp_path / "scanned-redacted.pdf"
    selected_box, unselected_box = _create_scanned_pdf(source_path)

    source_document = pymupdf.open(source_path)

    try:
        source_page = source_document[0]
        assert source_page.get_text() == ""
        selected_pixels_before = _render_rgb_crop(
            source_page,
            selected_box,
        )
        unselected_pixels_before = _render_rgb_crop(
            source_page,
            unselected_box,
        )
    finally:
        source_document.close()

    ocr_regions = [
        {
            "start": 0,
            "end": 6,
            "text": "SECRET",
            "bbox": {
                "x0": selected_box.x0,
                "y0": selected_box.y0,
                "x1": selected_box.x1,
                "y1": selected_box.y1,
            },
        },
        {
            "start": 7,
            "end": 11,
            "text": "KEEP",
            "bbox": {
                "x0": unselected_box.x0,
                "y0": unselected_box.y0,
                "x1": unselected_box.x1,
                "y1": unselected_box.y1,
            },
        },
    ]
    selected_finding = {
        "type": "PERSON",
        "value": "SECRET",
        "start": 0,
        "end": 6,
        "page_number": 1,
    }
    selected_finding["bounding_boxes"] = (
        locate_finding_in_ocr_regions(
            finding=selected_finding,
            regions=ocr_regions,
        )
    )

    create_redacted_pdf(
        source_path=source_path,
        output_path=output_path,
        findings=[selected_finding],
    )

    redacted_document = pymupdf.open(output_path)

    try:
        redacted_page = redacted_document[0]
        selected_pixels_after = _render_rgb_crop(
            redacted_page,
            selected_box,
        )
        unselected_pixels_after = _render_rgb_crop(
            redacted_page,
            unselected_box,
        )

        assert selected_pixels_before != selected_pixels_after
        assert all(
            red <= 5 and green <= 5 and blue <= 5
            for red, green, blue in selected_pixels_after
        )
        assert unselected_pixels_after == unselected_pixels_before
        assert any(
            green > red and green > blue
            for red, green, blue in unselected_pixels_after
        )
    finally:
        redacted_document.close()
