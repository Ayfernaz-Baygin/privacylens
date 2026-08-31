from collections import defaultdict
from pathlib import Path

import openpyxl

from backend.app.services.xlsx_locator import (
    build_xlsx_cell_index,
    locate_entity_cells,
)
from backend.app.services.sensitive_value_masking import (
    mask_sensitive_value,
)


def _apply_masks_to_cell(text: str, matches: list[dict]) -> str:
    masked_characters = list(text)

    for match in matches:
        match_start = match["match_start"]
        match_end = match["match_end"]
        mask_slice = match["mask_slice"]

        if len(mask_slice) != match_end - match_start:
            mask_slice = "*" * (match_end - match_start)

        for offset, replacement in enumerate(mask_slice):
            cell_offset = match_start + offset

            if (
                masked_characters[cell_offset] == "*"
                or replacement == "*"
            ):
                masked_characters[cell_offset] = "*"
            else:
                masked_characters[cell_offset] = replacement

    return "".join(masked_characters)


def _group_matches_by_cell(
    index: dict,
    findings: list[dict],
) -> dict:
    """(sheet_name, coordinate) -> every cell match any finding produced.

    Grouping first (rather than mutating the workbook finding-by-finding)
    lets all masks be combined against the original cell text. A star
    contributed by any overlapping mask can therefore never be reopened.
    """
    pages_by_number = {
        page["page_number"]: page for page in index["pages"]
    }

    grouped = defaultdict(list)

    for finding in findings:
        page = pages_by_number.get(finding["page_number"])

        if page is None:
            continue

        finding_start = finding["start"]
        finding_end = finding["end"]
        masked_value = mask_sensitive_value(
            finding["value"],
            finding["type"],
        )

        if len(masked_value) != finding_end - finding_start:
            masked_value = "*" * (finding_end - finding_start)

        matches = locate_entity_cells(
            page,
            finding_start,
            finding_end,
        )

        for match in matches:
            key = (match["sheet_name"], match["coordinate"])
            overlap_start = (
                match["cell_start"] + match["match_start"]
            )
            relative_start = overlap_start - finding_start
            relative_end = relative_start + (
                match["match_end"] - match["match_start"]
            )
            grouped[key].append(
                {
                    **match,
                    "mask_slice": masked_value[
                        relative_start:relative_end
                    ],
                }
            )

    return grouped


def create_redacted_xlsx(
    source_path: Path,
    output_path: Path,
    findings: list[dict],
) -> Path:
    """Replace located values with masks while preserving workbook data.

    Formula matches are masked against their cached result. Assigning
    that safe plain string removes the formula instead of applying
    cached-result offsets to unrelated formula syntax.
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

            cell.value = _apply_masks_to_cell(cell_text, matches)

        workbook.save(output_path)

    finally:
        workbook.close()

    return output_path
