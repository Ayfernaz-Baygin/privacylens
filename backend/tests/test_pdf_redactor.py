import pymupdf
import pytest

from backend.app.services.document_processing import (
    analyze_document_file,
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


def _bbox_dict(rectangle):
    return {
        "x0": rectangle.x0,
        "y0": rectangle.y0,
        "x1": rectangle.x1,
        "y1": rectangle.y1,
    }


def _create_hybrid_pdf(
    file_path,
    native_value="native@example.com",
    ocr_value="ocr@example.com",
):
    image_rect = pymupdf.Rect(40, 90, 360, 170)
    ocr_box = pymupdf.Rect(40, 90, 190, 170)
    control_box = pymupdf.Rect(220, 90, 360, 170)

    image_document = pymupdf.open()
    image_page = image_document.new_page(width=320, height=80)
    image_page.draw_rect(
        pymupdf.Rect(0, 0, 150, 80),
        color=(1, 0, 0),
        fill=(1, 0, 0),
    )
    image_page.insert_text(
        (8, 45),
        ocr_value,
        color=(1, 1, 1),
        fontsize=15,
    )
    image_page.draw_rect(
        pymupdf.Rect(180, 0, 320, 80),
        color=(0, 1, 0),
        fill=(0, 1, 0),
    )
    image_page.insert_text(
        (205, 45),
        "CONTROL",
        color=(0, 0, 0),
        fontsize=15,
    )
    image_bytes = image_page.get_pixmap(
        matrix=pymupdf.Matrix(2, 2),
        alpha=False,
    ).tobytes("png")
    image_document.close()

    document = pymupdf.open()
    page = document.new_page(width=400, height=220)
    page.insert_text(
        (40, 50),
        native_value,
        fontsize=14,
    )
    native_box = page.search_for(native_value)[0]
    page.insert_image(image_rect, stream=image_bytes)
    document.save(file_path)
    document.close()

    return native_box, ocr_box, control_box


def _analyze_hybrid_pdf(
    pdf_path,
    native_value,
    ocr_value,
    native_box,
    ocr_box,
    monkeypatch,
):
    separator = "\n|\n"
    canonical_text = native_value + separator + ocr_value
    ocr_start = len(native_value) + len(separator)

    monkeypatch.setattr(
        "backend.app.services.document_processing.extract_text_from_pdf",
        lambda file_path: {
            "page_count": 1,
            "pages": [
                {
                    "page_number": 1,
                    "text": canonical_text,
                    "text_source": "hybrid",
                    "regions": [
                        {
                            "start": 0,
                            "end": len(native_value),
                            "text": native_value,
                            "source": "native",
                            "bbox": _bbox_dict(native_box),
                        },
                        {
                            "start": ocr_start,
                            "end": ocr_start + len(ocr_value),
                            "text": ocr_value,
                            "source": "ocr",
                            "bbox": _bbox_dict(ocr_box),
                        },
                    ],
                }
            ],
        },
    )
    monkeypatch.setattr(
        "backend.app.services.detection_engine.detect_named_entities",
        lambda text: [],
    )

    return analyze_document_file(
        pdf_path=pdf_path,
        docx_path=pdf_path.with_suffix(".docx"),
        xlsx_path=pdf_path.with_suffix(".xlsx"),
    )


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


@pytest.mark.parametrize(
    (
        "selected_values",
        "native_should_remain",
        "ocr_should_remain",
    ),
    [
        ({"ocr@example.com"}, True, False),
        ({"native@example.com"}, False, True),
        (
            {"native@example.com", "ocr@example.com"},
            False,
            False,
        ),
    ],
)
def test_hybrid_pdf_selectively_redacts_native_and_ocr_findings(
    tmp_path,
    monkeypatch,
    selected_values,
    native_should_remain,
    ocr_should_remain,
):
    source_path = tmp_path / "hybrid-source.pdf"
    output_path = tmp_path / "hybrid-redacted.pdf"
    native_box, ocr_box, control_box = _create_hybrid_pdf(source_path)
    analysis = _analyze_hybrid_pdf(
        pdf_path=source_path,
        native_value="native@example.com",
        ocr_value="ocr@example.com",
        native_box=native_box,
        ocr_box=ocr_box,
        monkeypatch=monkeypatch,
    )

    assert {
        finding["value"]
        for finding in analysis["findings"]
    } == {"native@example.com", "ocr@example.com"}
    assert all(
        finding["bounding_boxes"]
        for finding in analysis["findings"]
    )

    selected_findings = [
        finding
        for finding in analysis["findings"]
        if finding["value"] in selected_values
    ]

    source_document = pymupdf.open(source_path)

    try:
        source_page = source_document[0]
        ocr_pixels_before = _render_rgb_crop(source_page, ocr_box)
        control_pixels_before = _render_rgb_crop(
            source_page,
            control_box,
        )
    finally:
        source_document.close()

    create_redacted_pdf(
        source_path=source_path,
        output_path=output_path,
        findings=selected_findings,
    )

    redacted_document = pymupdf.open(output_path)

    try:
        redacted_page = redacted_document[0]
        native_matches = redacted_page.search_for(
            "native@example.com"
        )
        ocr_pixels_after = _render_rgb_crop(redacted_page, ocr_box)
        control_pixels_after = _render_rgb_crop(
            redacted_page,
            control_box,
        )

        assert bool(native_matches) is native_should_remain

        if ocr_should_remain:
            assert ocr_pixels_after == ocr_pixels_before
        else:
            assert ocr_pixels_after != ocr_pixels_before
            assert all(
                red <= 5 and green <= 5 and blue <= 5
                for red, green, blue in ocr_pixels_after
            )

        assert control_pixels_after == control_pixels_before
    finally:
        redacted_document.close()


def test_hybrid_repeated_value_redacts_only_selected_occurrence(
    tmp_path,
    monkeypatch,
):
    source_path = tmp_path / "hybrid-repeated-source.pdf"
    output_path = tmp_path / "hybrid-repeated-redacted.pdf"
    repeated_value = "same@example.com"
    native_box, ocr_box, control_box = _create_hybrid_pdf(
        source_path,
        native_value=repeated_value,
        ocr_value=repeated_value,
    )
    analysis = _analyze_hybrid_pdf(
        pdf_path=source_path,
        native_value=repeated_value,
        ocr_value=repeated_value,
        native_box=native_box,
        ocr_box=ocr_box,
        monkeypatch=monkeypatch,
    )

    assert len(analysis["findings"]) == 2
    native_finding, ocr_finding = analysis["findings"]
    assert native_finding["bounding_boxes"] == [
        {**_bbox_dict(native_box), "start": 0, "end": 16}
    ]
    assert ocr_finding["bounding_boxes"] == [
        {**_bbox_dict(ocr_box), "start": 0, "end": 16}
    ]

    source_document = pymupdf.open(source_path)

    try:
        source_page = source_document[0]
        control_pixels_before = _render_rgb_crop(
            source_page,
            control_box,
        )
    finally:
        source_document.close()

    create_redacted_pdf(
        source_path=source_path,
        output_path=output_path,
        findings=[ocr_finding],
    )

    redacted_document = pymupdf.open(output_path)

    try:
        redacted_page = redacted_document[0]
        assert redacted_page.search_for(repeated_value)
        assert all(
            red <= 5 and green <= 5 and blue <= 5
            for red, green, blue in _render_rgb_crop(
                redacted_page,
                ocr_box,
            )
        )
        assert _render_rgb_crop(
            redacted_page,
            control_box,
        ) == control_pixels_before
    finally:
        redacted_document.close()
