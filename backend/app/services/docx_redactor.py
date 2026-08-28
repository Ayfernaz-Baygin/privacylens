from pathlib import Path

import docx

from backend.app.services.docx_locator import (
    build_docx_run_index,
    locate_entity_runs,
)

REDACTION_CHARACTER = "█"


def _get_run(document, match: dict):
    if match["kind"] == "paragraph":
        paragraph = document.paragraphs[match["paragraph_index"]]
    else:
        table = document.tables[match["table_index"]]
        cell = table.rows[match["row_index"]].cells[
            match["cell_index"]
        ]
        paragraph = cell.paragraphs[match["paragraph_index"]]

    return paragraph.runs[match["run_index"]]


def _redact_run_text(
    run_text: str,
    match_start: int,
    match_end: int,
) -> str:
    redacted_length = match_end - match_start

    return (
        run_text[:match_start]
        + REDACTION_CHARACTER * redacted_length
        + run_text[match_end:]
    )


def create_redacted_docx(
    source_path: Path,
    output_path: Path,
    findings: list[dict],
) -> Path:
    document = docx.Document(source_path)
    run_index = build_docx_run_index(source_path)

    for finding in findings:
        matches = locate_entity_runs(
            run_index,
            finding["start"],
            finding["end"],
        )

        for match in matches:
            run = _get_run(document, match)

            run.text = _redact_run_text(
                run.text,
                match["match_start"],
                match["match_end"],
            )

    document.save(output_path)

    return output_path
