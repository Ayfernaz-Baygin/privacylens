from pathlib import Path

import docx


def extract_text_from_docx(file_path: Path) -> dict:
    document = docx.Document(file_path)

    lines = [
        paragraph.text
        for paragraph in document.paragraphs
        if paragraph.text
    ]

    for table in document.tables:
        for row in table.rows:
            cell_texts = [
                cell.text
                for cell in row.cells
                if cell.text
            ]

            if cell_texts:
                lines.append(" | ".join(cell_texts))

    text = "\n".join(lines)

    return {
        "page_count": 1,
        "pages": [
            {
                "page_number": 1,
                "text": text,
            }
        ],
    }
