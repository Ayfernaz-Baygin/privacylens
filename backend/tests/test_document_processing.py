import docx
import openpyxl
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
    xlsx_path = tmp_path / "source.xlsx"

    document = pymupdf.open()
    page = document.new_page()
    page.insert_text((72, 72), "E-mail: test@example.com")
    document.save(pdf_path)
    document.close()

    result = analyze_document_file(
        pdf_path=pdf_path,
        docx_path=docx_path,
        xlsx_path=xlsx_path,
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
    xlsx_path = tmp_path / "source.xlsx"

    document = docx.Document()
    document.add_paragraph("E-mail: test@example.com")
    document.save(docx_path)

    result = analyze_document_file(
        pdf_path=pdf_path,
        docx_path=docx_path,
        xlsx_path=xlsx_path,
    )

    assert result["document_format"] == "docx"
    assert result["page_count"] == 1
    assert len(result["findings"]) == 1

    finding = result["findings"][0]

    assert finding["type"] == "EMAIL"
    assert finding["bounding_boxes"] == []
    assert finding["finding_id"] == build_finding_id(finding)


def test_analyze_document_file_uses_xlsx_with_empty_boxes(
    tmp_path, monkeypatch
):
    _no_ner(monkeypatch)

    pdf_path = tmp_path / "source.pdf"
    docx_path = tmp_path / "source.docx"
    xlsx_path = tmp_path / "source.xlsx"

    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = "Müşteriler"
    sheet["A1"] = "E-mail: test@example.com"
    workbook.save(xlsx_path)

    result = analyze_document_file(
        pdf_path=pdf_path,
        docx_path=docx_path,
        xlsx_path=xlsx_path,
    )

    assert result["document_format"] == "xlsx"
    assert result["page_count"] == 1
    assert len(result["findings"]) == 1

    finding = result["findings"][0]

    assert finding["type"] == "EMAIL"
    assert finding["bounding_boxes"] == []
    assert finding["page_number"] == 1
    assert finding["finding_id"] == build_finding_id(finding)


def test_analyze_document_file_prefers_pdf_when_all_exist(
    tmp_path, monkeypatch
):
    _no_ner(monkeypatch)

    pdf_path = tmp_path / "source.pdf"
    docx_path = tmp_path / "source.docx"
    xlsx_path = tmp_path / "source.xlsx"

    document = pymupdf.open()
    page = document.new_page()
    page.insert_text((72, 72), "test@example.com")
    document.save(pdf_path)
    document.close()

    docx.Document().save(docx_path)
    openpyxl.Workbook().save(xlsx_path)

    result = analyze_document_file(
        pdf_path=pdf_path,
        docx_path=docx_path,
        xlsx_path=xlsx_path,
    )

    assert result["document_format"] == "pdf"


def test_analyze_document_file_prefers_docx_over_xlsx(
    tmp_path, monkeypatch
):
    _no_ner(monkeypatch)

    pdf_path = tmp_path / "source.pdf"
    docx_path = tmp_path / "source.docx"
    xlsx_path = tmp_path / "source.xlsx"

    docx.Document().save(docx_path)
    openpyxl.Workbook().save(xlsx_path)

    result = analyze_document_file(
        pdf_path=pdf_path,
        docx_path=docx_path,
        xlsx_path=xlsx_path,
    )

    assert result["document_format"] == "docx"


def test_analyze_document_file_raises_when_none_exist(tmp_path):
    with pytest.raises(UnsupportedDocumentFormatError):
        analyze_document_file(
            pdf_path=tmp_path / "source.pdf",
            docx_path=tmp_path / "source.docx",
            xlsx_path=tmp_path / "source.xlsx",
        )


def test_analyze_document_file_raises_parse_error_for_corrupt_pdf(
    tmp_path,
):
    pdf_path = tmp_path / "source.pdf"
    docx_path = tmp_path / "source.docx"
    xlsx_path = tmp_path / "source.xlsx"

    pdf_path.write_bytes(b"not a real pdf")

    with pytest.raises(DocumentParseError) as excinfo:
        analyze_document_file(
            pdf_path=pdf_path,
            docx_path=docx_path,
            xlsx_path=xlsx_path,
        )

    assert excinfo.value.document_format == "pdf"


def test_analyze_document_file_raises_parse_error_for_corrupt_docx(
    tmp_path,
):
    pdf_path = tmp_path / "source.pdf"
    docx_path = tmp_path / "source.docx"
    xlsx_path = tmp_path / "source.xlsx"

    docx_path.write_bytes(b"not a real docx")

    with pytest.raises(DocumentParseError) as excinfo:
        analyze_document_file(
            pdf_path=pdf_path,
            docx_path=docx_path,
            xlsx_path=xlsx_path,
        )

    assert excinfo.value.document_format == "docx"


def test_analyze_document_file_raises_parse_error_for_corrupt_xlsx(
    tmp_path,
):
    pdf_path = tmp_path / "source.pdf"
    docx_path = tmp_path / "source.docx"
    xlsx_path = tmp_path / "source.xlsx"

    xlsx_path.write_bytes(b"not a real xlsx")

    with pytest.raises(DocumentParseError) as excinfo:
        analyze_document_file(
            pdf_path=pdf_path,
            docx_path=docx_path,
            xlsx_path=xlsx_path,
        )

    assert excinfo.value.document_format == "xlsx"
