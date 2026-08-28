import docx

from backend.app.services.docx_parser import extract_text_from_docx
from backend.app.services.docx_redactor import create_redacted_docx


def _finding_for(text: str, value: str) -> dict:
    start = text.index(value)

    return {"start": start, "end": start + len(value)}


def test_create_redacted_docx_single_run(tmp_path):
    source_path = tmp_path / "source.docx"
    output_path = tmp_path / "redacted.docx"

    document = docx.Document()
    document.add_paragraph("E-mail: test@example.com")
    document.save(source_path)

    text = extract_text_from_docx(source_path)["pages"][0]["text"]
    value = "test@example.com"

    create_redacted_docx(
        source_path,
        output_path,
        [_finding_for(text, value)],
    )

    redacted_document = docx.Document(output_path)
    paragraph = redacted_document.paragraphs[0]

    assert paragraph.text == "E-mail: " + "█" * len(value)
    assert value not in paragraph.text
    assert len(paragraph.runs) == 1


def test_create_redacted_docx_entity_split_across_runs(tmp_path):
    source_path = tmp_path / "source.docx"
    output_path = tmp_path / "redacted.docx"

    document = docx.Document()
    paragraph = document.add_paragraph()
    paragraph.add_run("E-posta: ayse@exa")
    paragraph.add_run("mple.com kayıtlı")
    document.save(source_path)

    text = extract_text_from_docx(source_path)["pages"][0]["text"]
    assert text == "E-posta: ayse@example.com kayıtlı"

    value = "ayse@example.com"

    create_redacted_docx(
        source_path,
        output_path,
        [_finding_for(text, value)],
    )

    redacted_document = docx.Document(output_path)
    paragraph = redacted_document.paragraphs[0]

    assert len(paragraph.runs) == 2
    assert paragraph.runs[0].text == "E-posta: ████████"
    assert paragraph.runs[1].text == "████████ kayıtlı"
    assert value not in paragraph.text
    assert "kayıtlı" in paragraph.text


def test_create_redacted_docx_table_cell(tmp_path):
    source_path = tmp_path / "source.docx"
    output_path = tmp_path / "redacted.docx"

    document = docx.Document()
    document.add_paragraph("Müşteri bilgileri")

    table = document.add_table(rows=1, cols=2)
    table.cell(0, 0).text = "E-posta"
    table.cell(0, 1).text = "test@example.com"
    document.save(source_path)

    text = extract_text_from_docx(source_path)["pages"][0]["text"]
    value = "test@example.com"

    create_redacted_docx(
        source_path,
        output_path,
        [_finding_for(text, value)],
    )

    redacted_document = docx.Document(output_path)
    redacted_table = redacted_document.tables[0]

    assert redacted_table.cell(0, 1).text == "█" * len(value)
    assert redacted_table.cell(0, 0).text == "E-posta"
    assert redacted_document.paragraphs[0].text == "Müşteri bilgileri"


def test_create_redacted_docx_removes_sensitive_text_when_reopened(
    tmp_path,
):
    source_path = tmp_path / "source.docx"
    output_path = tmp_path / "redacted.docx"

    document = docx.Document()
    document.add_paragraph(
        "TCKN: 12345678901 ile başvuru yapıldı."
    )
    document.save(source_path)

    text = extract_text_from_docx(source_path)["pages"][0]["text"]
    value = "12345678901"

    create_redacted_docx(
        source_path,
        output_path,
        [_finding_for(text, value)],
    )

    redacted_text = extract_text_from_docx(output_path)[
        "pages"
    ][0]["text"]

    assert value not in redacted_text
    assert "TCKN:" in redacted_text
    assert "ile başvuru yapıldı." in redacted_text


def test_create_redacted_docx_preserves_neighboring_text(tmp_path):
    source_path = tmp_path / "source.docx"
    output_path = tmp_path / "redacted.docx"

    document = docx.Document()
    document.add_paragraph(
        "Ad Soyad: Ayfer Aycan, Email: test@example.com, "
        "Şehir: İstanbul"
    )
    document.save(source_path)

    text = extract_text_from_docx(source_path)["pages"][0]["text"]
    value = "test@example.com"

    create_redacted_docx(
        source_path,
        output_path,
        [_finding_for(text, value)],
    )

    redacted_text = docx.Document(output_path).paragraphs[0].text

    assert "Ad Soyad: Ayfer Aycan" in redacted_text
    assert "Şehir: İstanbul" in redacted_text
    assert value not in redacted_text


def test_create_redacted_docx_preserves_run_formatting(tmp_path):
    source_path = tmp_path / "source.docx"
    output_path = tmp_path / "redacted.docx"

    document = docx.Document()
    paragraph = document.add_paragraph()
    run = paragraph.add_run("test@example.com")
    run.bold = True
    run.italic = True
    document.save(source_path)

    text = extract_text_from_docx(source_path)["pages"][0]["text"]
    value = "test@example.com"

    create_redacted_docx(
        source_path,
        output_path,
        [_finding_for(text, value)],
    )

    redacted_document = docx.Document(output_path)
    redacted_paragraph = redacted_document.paragraphs[0]

    assert len(redacted_paragraph.runs) == 1

    redacted_run = redacted_paragraph.runs[0]

    assert redacted_run.bold is True
    assert redacted_run.italic is True
    assert redacted_run.text == "█" * len(value)
