import docx
import pymupdf
import pytest

from backend.app.services.document_processing import (
    DocumentParseError,
    UnsupportedDocumentFormatError,
    analyze_document_file,
    build_finding_id,
)


def _no_ner(monkeypatch):
    monkeypatch.setattr(
        "backend.app.services.detection_engine.detect_named_entities",
        lambda text: [],
    )


def test_build_finding_id_combines_page_start_end_type():
    finding = {
        "page_number": 3,
        "start": 10,
        "end": 20,
        "type": "EMAIL",
    }

    assert build_finding_id(finding) == "3:10:20:EMAIL"


def test_analyze_document_file_uses_pdf_and_locates_boxes(
    tmp_path, monkeypatch
):
    _no_ner(monkeypatch)

    pdf_path = tmp_path / "source.pdf"
    docx_path = tmp_path / "source.docx"

    document = pymupdf.open()
    page = document.new_page()
    page.insert_text((72, 72), "E-mail: test@example.com")
    document.save(pdf_path)
    document.close()

    result = analyze_document_file(
        pdf_path=pdf_path,
        docx_path=docx_path,
    )

    assert result["document_format"] == "pdf"
    assert result["page_count"] == 1
    assert len(result["findings"]) == 1

    finding = result["findings"][0]

    assert finding["type"] == "EMAIL"
    assert len(finding["bounding_boxes"]) == 1
    assert finding["finding_id"] == build_finding_id(finding)


def test_analyze_document_file_uses_docx_with_empty_boxes(
    tmp_path, monkeypatch
):
    _no_ner(monkeypatch)

    pdf_path = tmp_path / "source.pdf"
    docx_path = tmp_path / "source.docx"

    document = docx.Document()
    document.add_paragraph("E-mail: test@example.com")
    document.save(docx_path)

    result = analyze_document_file(
        pdf_path=pdf_path,
        docx_path=docx_path,
    )

    assert result["document_format"] == "docx"
    assert result["page_count"] == 1
    assert len(result["findings"]) == 1

    finding = result["findings"][0]

    assert finding["type"] == "EMAIL"
    assert finding["bounding_boxes"] == []
    assert finding["finding_id"] == build_finding_id(finding)


def test_analyze_document_file_prefers_pdf_when_both_exist(
    tmp_path, monkeypatch
):
    _no_ner(monkeypatch)

    pdf_path = tmp_path / "source.pdf"
    docx_path = tmp_path / "source.docx"

    document = pymupdf.open()
    page = document.new_page()
    page.insert_text((72, 72), "test@example.com")
    document.save(pdf_path)
    document.close()

    docx.Document().save(docx_path)

    result = analyze_document_file(
        pdf_path=pdf_path,
        docx_path=docx_path,
    )

    assert result["document_format"] == "pdf"


def test_analyze_document_file_raises_when_neither_exists(tmp_path):
    with pytest.raises(UnsupportedDocumentFormatError):
        analyze_document_file(
            pdf_path=tmp_path / "source.pdf",
            docx_path=tmp_path / "source.docx",
        )


def test_analyze_document_file_raises_parse_error_for_corrupt_pdf(
    tmp_path,
):
    pdf_path = tmp_path / "source.pdf"
    docx_path = tmp_path / "source.docx"

    pdf_path.write_bytes(b"not a real pdf")

    with pytest.raises(DocumentParseError) as excinfo:
        analyze_document_file(
            pdf_path=pdf_path,
            docx_path=docx_path,
        )

    assert excinfo.value.document_format == "pdf"


def test_analyze_document_file_raises_parse_error_for_corrupt_docx(
    tmp_path,
):
    pdf_path = tmp_path / "source.pdf"
    docx_path = tmp_path / "source.docx"

    docx_path.write_bytes(b"not a real docx")

    with pytest.raises(DocumentParseError) as excinfo:
        analyze_document_file(
            pdf_path=pdf_path,
            docx_path=docx_path,
        )

    assert excinfo.value.document_format == "docx"
