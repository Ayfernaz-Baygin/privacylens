import pytest

from backend.app.services.pdf_parser import (
    PdfOcrError,
    classify_pdf_page,
    extract_text_from_pdf,
)


class FakeDocument:
    def __init__(self, pages):
        self.pages = pages
        self.closed = False

    def __iter__(self):
        return iter(self.pages)

    def __len__(self):
        return len(self.pages)

    def close(self):
        self.closed = True


class NativePage:
    def __init__(self):
        self.ocr_called = False
        self.rect = (0, 0, 100, 100)

    def get_text(self, output, **kwargs):
        if output == "text":
            assert kwargs == {}
            return "Email: test@example.com\n"

        assert output == "words"
        return []

    def get_image_info(self):
        return []

    def get_textpage_ocr(self, **kwargs):
        self.ocr_called = True
        raise AssertionError("OCR must not run for native text")


class OcrPage:
    def __init__(self):
        self.ocr_kwargs = None
        self.text_page = object()

    def get_text(self, output, **kwargs):
        if output == "text":
            return ""

        assert output == "rawdict"
        assert kwargs == {
            "textpage": self.text_page,
            "sort": True,
        }
        return {
            "blocks": [
                {
                    "lines": [
                        {
                            "spans": [
                                {
                                    "bbox": (10, 20, 70, 32),
                                    "chars": [
                                        {"c": character}
                                        for character in "Ahmet"
                                    ],
                                },
                                {
                                    "bbox": (74, 20, 126, 32),
                                    "chars": [
                                        {"c": character}
                                        for character in " Yilmaz"
                                    ],
                                },
                            ]
                        }
                    ]
                }
            ]
        }

    def get_textpage_ocr(self, **kwargs):
        self.ocr_kwargs = kwargs
        return self.text_page


class HybridPage(NativePage):
    def __init__(self, spans=None):
        super().__init__()
        self.ocr_kwargs = None
        self.text_page = object()
        self.spans = spans or [
            {
                "bbox": (0, 0, 100, 10),
                "font": "Helvetica",
                "chars": [
                    {"c": character}
                    for character in "Header"
                ],
            },
            {
                "bbox": (10, 30, 90, 45),
                "font": "GlyphLessFont",
                "chars": [
                    {"c": character}
                    for character in "ocr@example.com"
                ],
            },
        ]

    def get_text(self, output, **kwargs):
        if output == "text":
            return "Header\n"

        if output == "words":
            return [(0, 0, 100, 10, "Header")]

        assert output == "rawdict"
        assert kwargs == {
            "textpage": self.text_page,
            "sort": True,
        }
        return {
            "blocks": [
                {
                    "lines": [
                        {"spans": [self.spans[0]]},
                        {"spans": self.spans[1:]},
                    ]
                }
            ]
        }

    def get_image_info(self):
        return [{"bbox": (0, 20, 100, 100)}]

    def get_textpage_ocr(self, **kwargs):
        self.ocr_called = True
        self.ocr_kwargs = kwargs
        return self.text_page


class FailingOcrPage:
    def get_text(self, output, **kwargs):
        assert output == "text"
        return "  \n"

    def get_textpage_ocr(self, **kwargs):
        raise RuntimeError("No OCR support: TESSDATA_PREFIX not set")


class ClassificationPage:
    def __init__(self, rect, images=None, words=None):
        self.rect = rect
        self.images = images or []
        self.words = words or []

    def get_image_info(self):
        return self.images

    def get_text(self, output):
        assert output == "words"
        return self.words


def test_empty_text_is_classified_as_ocr():
    page = ClassificationPage(
        rect=(0, 0, 100, 100),
        images=[{"bbox": (0, 0, 100, 100)}],
    )

    assert classify_pdf_page(page, " \n") == "ocr"


def test_native_text_without_image_is_classified_as_native():
    page = ClassificationPage(rect=(0, 0, 100, 100))

    assert classify_pdf_page(page, "Native text") == "native"


def test_native_text_with_small_image_is_classified_as_native():
    page = ClassificationPage(
        rect=(0, 0, 100, 100),
        images=[{"bbox": (0, 0, 40, 40)}],
    )

    assert classify_pdf_page(page, "Native text") == "native"


def test_native_text_with_large_uncovered_image_is_hybrid():
    page = ClassificationPage(
        rect=(0, 0, 100, 100),
        images=[{"bbox": (0, 20, 100, 100)}],
        words=[(0, 0, 100, 10, "Header")],
    )

    assert classify_pdf_page(page, "Header") == "hybrid"


def test_large_image_with_enough_native_coverage_is_native():
    page = ClassificationPage(
        rect=(0, 0, 100, 100),
        images=[{"bbox": (0, 0, 100, 100)}],
        words=[(10, 10, 40, 30, "Covered")],
    )

    assert classify_pdf_page(page, "Covered") == "native"


@pytest.mark.parametrize(
    ("page_rect", "image_bbox"),
    [
        ((0, 0, 0, 100), (0, 0, 100, 100)),
        ((0, 0, 100, 100), (20, 20, 20, 80)),
        ((0, 0, 100, 100), (80, 80, 20, 20)),
        ((0, 0, 100, 100), (0, 0)),
    ],
)
def test_invalid_or_zero_area_bboxes_are_safe(
    page_rect,
    image_bbox,
):
    page = ClassificationPage(
        rect=page_rect,
        images=[{"bbox": image_bbox}],
    )

    assert classify_pdf_page(page, "Native text") == "native"


def test_native_page_does_not_call_ocr(monkeypatch):
    page = NativePage()
    document = FakeDocument([page])
    monkeypatch.setattr(
        "backend.app.services.pdf_parser.pymupdf.open",
        lambda file_path: document,
    )

    result = extract_text_from_pdf("native.pdf")

    assert page.ocr_called is False
    assert result == {
        "page_count": 1,
        "pages": [
            {
                "page_number": 1,
                "text": "Email: test@example.com\n",
                "text_source": "native",
                "regions": [],
            }
        ],
    }
    assert document.closed is True


def test_hybrid_page_uses_partial_ocr_and_builds_canonical_regions(
    monkeypatch,
):
    page = HybridPage()
    document = FakeDocument([page])
    monkeypatch.setattr(
        "backend.app.services.pdf_parser.pymupdf.open",
        lambda file_path: document,
    )

    result = extract_text_from_pdf("hybrid.pdf")

    assert page.ocr_called is True
    assert page.ocr_kwargs == {
        "language": "tur+eng",
        "dpi": 300,
        "full": False,
    }
    assert result["pages"][0] == {
        "page_number": 1,
        "text": "Header\n|\nocr@example.com",
        "text_source": "hybrid",
        "regions": [
            {
                "start": 0,
                "end": 6,
                "text": "Header",
                "source": "native",
                "bbox": {
                    "x0": 0,
                    "y0": 0,
                    "x1": 100,
                    "y1": 10,
                },
            },
            {
                "start": 9,
                "end": 24,
                "text": "ocr@example.com",
                "source": "ocr",
                "bbox": {
                    "x0": 10,
                    "y0": 30,
                    "x1": 90,
                    "y1": 45,
                },
            },
        ],
    }

    parsed_page = result["pages"][0]

    for region in parsed_page["regions"]:
        assert parsed_page["text"][
            region["start"]:region["end"]
        ] == region["text"]


def test_hybrid_removes_normalized_spatial_duplicate(monkeypatch):
    page = HybridPage(
        spans=[
            {
                "bbox": (10, 30, 90, 45),
                "font": "Helvetica",
                "chars": [
                    {"c": character}
                    for character in "Test   User"
                ],
            },
            {
                "bbox": (11, 30, 89, 45),
                "font": "GlyphLessFont",
                "chars": [
                    {"c": character}
                    for character in " test user "
                ],
            },
        ]
    )
    document = FakeDocument([page])
    monkeypatch.setattr(
        "backend.app.services.pdf_parser.pymupdf.open",
        lambda file_path: document,
    )

    parsed_page = extract_text_from_pdf("hybrid.pdf")["pages"][0]

    assert parsed_page["text"] == "Test   User"
    assert [
        region["source"]
        for region in parsed_page["regions"]
    ] == ["native"]


def test_hybrid_keeps_same_text_at_different_bbox(monkeypatch):
    page = HybridPage(
        spans=[
            {
                "bbox": (0, 0, 40, 10),
                "font": "Helvetica",
                "chars": [
                    {"c": character}
                    for character in "Same text"
                ],
            },
            {
                "bbox": (10, 40, 50, 50),
                "font": "GlyphLessFont",
                "chars": [
                    {"c": character}
                    for character in "Same text"
                ],
            },
        ]
    )
    document = FakeDocument([page])
    monkeypatch.setattr(
        "backend.app.services.pdf_parser.pymupdf.open",
        lambda file_path: document,
    )

    parsed_page = extract_text_from_pdf("hybrid.pdf")["pages"][0]

    assert parsed_page["text"] == "Same text\n|\nSame text"
    assert [
        region["source"]
        for region in parsed_page["regions"]
    ] == ["native", "ocr"]


def test_empty_page_uses_ocr_fallback(monkeypatch):
    page = OcrPage()
    document = FakeDocument([page])
    monkeypatch.setattr(
        "backend.app.services.pdf_parser.pymupdf.open",
        lambda file_path: document,
    )

    result = extract_text_from_pdf("scanned.pdf")

    assert page.ocr_kwargs == {
        "language": "tur+eng",
        "dpi": 300,
        "full": True,
    }
    assert result["pages"][0]["text_source"] == "ocr"


def test_ocr_text_and_coordinate_map_use_matching_offsets(monkeypatch):
    page = OcrPage()
    document = FakeDocument([page])
    monkeypatch.setattr(
        "backend.app.services.pdf_parser.pymupdf.open",
        lambda file_path: document,
    )

    result = extract_text_from_pdf("scanned.pdf")

    assert result["pages"][0] == {
        "page_number": 1,
        "text": "Ahmet Yilmaz\n",
        "text_source": "ocr",
        "regions": [
            {
                "start": 0,
                "end": 5,
                "text": "Ahmet",
                "bbox": {
                    "x0": 10,
                    "y0": 20,
                    "x1": 70,
                    "y1": 32,
                },
            },
            {
                "start": 5,
                "end": 12,
                "text": " Yilmaz",
                "bbox": {
                    "x0": 74,
                    "y0": 20,
                    "x1": 126,
                    "y1": 32,
                },
            },
        ],
    }
    assert document.closed is True


def test_ocr_failure_raises_readable_error_and_closes_document(
    monkeypatch,
):
    document = FakeDocument([FailingOcrPage()])
    monkeypatch.setattr(
        "backend.app.services.pdf_parser.pymupdf.open",
        lambda file_path: document,
    )

    with pytest.raises(PdfOcrError) as excinfo:
        extract_text_from_pdf("scanned.pdf")

    assert excinfo.value.page_number == 1
    assert "Tesseract" in str(excinfo.value)
    assert "tur+eng" in str(excinfo.value)
    assert document.closed is True
