from collections import defaultdict
from pathlib import Path

import openpyxl

from backend.app.services.xlsx_locator import (
    build_xlsx_cell_index,
    locate_entity_cells,
)

REDACTION_CHARACTER = "█"


def _merge_spans(spans: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """Merges overlapping/adjacent (start, end) ranges into disjoint ones.

    Several findings can land inside the same cell with overlapping
    ranges; merging first means each character is redacted exactly
    once, regardless of how many findings touched it.
    """
    merged = []

    for start, end in sorted(spans):
        if merged and start <= merged[-1][1]:
            merged[-1] = (
                merged[-1][0],
                max(merged[-1][1], end),
            )
        else:
            merged.append((start, end))

    return merged


def _redact_spans(text: str, spans: list[tuple[int, int]]) -> str:
    result = text

    for start, end in _merge_spans(spans):
        result = (
            result[:start]
            + REDACTION_CHARACTER * (end - start)
            + result[end:]
        )

    return result


def _group_matches_by_cell(
    index: dict,
    findings: list[dict],
) -> dict:
    """(sheet_name, coordinate) -> every cell match any finding produced.

    Grouping first (rather than mutating the workbook finding-by-finding)
    is what lets a cell touched by several findings get redacted exactly
    once, correctly, whether it's a plain cell (spans merged) or a
    formula cell (whole-cell redaction is naturally idempotent).
    """
    pages_by_number = {
        page["page_number"]: page for page in index["pages"]
    }

    grouped = defaultdict(list)

    for finding in findings:
        page = pages_by_number.get(finding["page_number"])

        if page is None:
            continue

        matches = locate_entity_cells(
            page,
            finding["start"],
            finding["end"],
        )

        for match in matches:
            key = (match["sheet_name"], match["coordinate"])
            grouped[key].append(match)

    return grouped


def create_redacted_xlsx(
    source_path: Path,
    output_path: Path,
    findings: list[dict],
) -> Path:
    """Redacts the real workbook cells the locator maps findings to.

    Loaded with data_only=False so untouched formula cells keep their
    formulas verbatim on save (data_only=True would flatten every
    formula in the workbook to its cached value, not just the ones
    being redacted). For a plain cell this is the same value the
    detector saw, so match_start/match_end apply directly.

    A formula cell is handled as a fail-safe whole-cell replacement:
    match_start/match_end were computed against the cached *result*
    text (data_only=True), which has no relationship to the formula
    string itself (data_only=False) — applying those offsets to the
    formula would corrupt it silently. Instead the entire cell becomes
    REDACTION_CHARACTER repeated for the cached result's length, and the
    formula is gone (assigning a plain string replaces it outright).
    """
    index = build_xlsx_cell_index(source_path)
    matches_by_cell = _group_matches_by_cell(index, findings)

    workbook = openpyxl.load_workbook(
        source_path,
        data_only=False,
    )

    try:
        for (sheet_name, coordinate), matches in (
            matches_by_cell.items()
        ):
            cell = workbook[sheet_name][coordinate]
            cell_text = matches[0]["cell_text"]

            if matches[0]["is_formula"]:
                cell.value = REDACTION_CHARACTER * len(
                    cell_text
                )
                continue

            spans = [
                (match["match_start"], match["match_end"])
                for match in matches
            ]

            cell.value = _redact_spans(cell_text, spans)

        workbook.save(output_path)

    finally:
        workbook.close()

    return output_path
