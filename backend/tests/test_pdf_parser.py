import pytest

from backend.app.services.pdf_parser import (
    PdfOcrError,
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

    def get_text(self, output, **kwargs):
        assert output == "text"
        assert kwargs == {}
        return "Email: test@example.com\n"

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


class FailingOcrPage:
    def get_text(self, output, **kwargs):
        assert output == "text"
        return "  \n"

    def get_textpage_ocr(self, **kwargs):
        raise RuntimeError("No OCR support: TESSDATA_PREFIX not set")


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
