from pathlib import Path

import docx
from docx.table import Table
from docx.text.paragraph import Paragraph

from backend.app.services.docx_parser import iter_block_items

LINE_SEPARATOR_LENGTH = len("\n")
CELL_SEPARATOR_LENGTH = len(" | ")


def _paragraph_run_spans(paragraph: Paragraph) -> list[dict]:
    """Run offsets relative to the paragraph's own text.

    paragraph.text is exactly the concatenation of paragraph.runs' text,
    so a simple prefix sum over the runs gives each run's local span.
    """
    spans = []
    offset = 0

    for run_index, run in enumerate(paragraph.runs):
        run_text = run.text

        if run_text:
            spans.append(
                {
                    "run_index": run_index,
                    "start": offset,
                    "end": offset + len(run_text),
                    "text": run_text,
                }
            )

        offset += len(run_text)

    return spans


def _cell_run_spans(cell) -> tuple[str, list[dict]]:
    """Cell text and run spans relative to that cell's own text.

    Mirrors docx_parser.cell_text(), which joins the cell's paragraphs
    with "\\n" (python-docx's own convention for _Cell.text).
    """
    spans = []
    paragraph_texts = []
    offset = 0

    for paragraph_index, paragraph in enumerate(cell.paragraphs):
        if paragraph_index > 0:
            offset += LINE_SEPARATOR_LENGTH

        for span in _paragraph_run_spans(paragraph):
            spans.append(
                {
                    "paragraph_index": paragraph_index,
                    "run_index": span["run_index"],
                    "start": offset + span["start"],
                    "end": offset + span["end"],
                    "text": span["text"],
                }
            )

        paragraph_text = paragraph.text
        paragraph_texts.append(paragraph_text)
        offset += len(paragraph_text)

    return "\n".join(paragraph_texts), spans


def _build_lines(document) -> list[tuple[str, list[dict]]]:
    """One (line_text, run_records) pair per line of extract_text_from_docx.

    run_records carry offsets relative to the line, and already identify
    which paragraph/table cell/run they came from (block_path fields).
    """
    lines = []

    paragraph_index = 0
    table_index = 0

    for block in iter_block_items(document):
        if isinstance(block, Paragraph):
            text = block.text

            if text:
                records = [
                    {
                        "kind": "paragraph",
                        "paragraph_index": paragraph_index,
                        "run_index": span["run_index"],
                        "start": span["start"],
                        "end": span["end"],
                        "text": span["text"],
                    }
                    for span in _paragraph_run_spans(block)
                ]

                lines.append((text, records))

            paragraph_index += 1

        elif isinstance(block, Table):
            for row_index, row in enumerate(block.rows):
                included_cells = []

                for cell_index, cell in enumerate(row.cells):
                    text, spans = _cell_run_spans(cell)

                    if text:
                        included_cells.append(
                            (cell_index, text, spans)
                        )

                if not included_cells:
                    continue

                row_text_parts = []
                row_records = []
                offset = 0

                for position, (cell_index, text, spans) in enumerate(
                    included_cells
                ):
                    if position > 0:
                        offset += CELL_SEPARATOR_LENGTH

                    for span in spans:
                        row_records.append(
                            {
                                "kind": "table_cell",
                                "table_index": table_index,
                                "row_index": row_index,
                                "cell_index": cell_index,
                                "paragraph_index": span[
                                    "paragraph_index"
                                ],
                                "run_index": span["run_index"],
                                "start": offset + span["start"],
                                "end": offset + span["end"],
                                "text": span["text"],
                            }
                        )

                    row_text_parts.append(text)
                    offset += len(text)

                lines.append(
                    (" | ".join(row_text_parts), row_records)
                )

            table_index += 1

    return lines


def build_docx_run_index(file_path: Path) -> dict:
    """Full document text plus every run's global offset in that text.

    The text is built with the same rules as extract_text_from_docx(), so
    offsets produced by detect_sensitive_data() against that text can be
    looked up here directly.
    """
    document = docx.Document(file_path)

    lines = _build_lines(document)

    text_parts = []
    runs = []
    offset = 0

    for line_index, (line_text, line_records) in enumerate(lines):
        if line_index > 0:
            offset += LINE_SEPARATOR_LENGTH

        for record in line_records:
            runs.append(
                {
                    **{
                        key: value
                        for key, value in record.items()
                        if key not in ("start", "end")
                    },
                    "start": offset + record["start"],
                    "end": offset + record["end"],
                }
            )

        text_parts.append(line_text)
        offset += len(line_text)

    return {
        "text": "\n".join(text_parts),
        "runs": runs,
    }


def locate_entity_runs(
    run_index: dict,
    start: int,
    end: int,
) -> list[dict]:
    """Runs overlapping [start, end), each with its local match range.

    A single-run entity yields one record; an entity split across runs
    (e.g. by inline formatting) yields one record per run it touches, in
    document order.
    """
    matches = []

    for run in run_index["runs"]:
        overlap_start = max(run["start"], start)
        overlap_end = min(run["end"], end)

        if overlap_start >= overlap_end:
            continue

        local_start = overlap_start - run["start"]
        local_end = overlap_end - run["start"]

        matches.append(
            {
                **{
                    key: value
                    for key, value in run.items()
                    if key not in ("start", "end", "text")
                },
                "run_start": run["start"],
                "run_end": run["end"],
                "run_text": run["text"],
                "match_start": local_start,
                "match_end": local_end,
                "matched_text": run["text"][local_start:local_end],
            }
        )

    return matches


def locate_text_in_docx(
    file_path: Path,
    start: int,
    end: int,
) -> list[dict]:
    run_index = build_docx_run_index(file_path)

    return locate_entity_runs(run_index, start, end)
