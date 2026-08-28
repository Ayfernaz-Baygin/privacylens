from pathlib import Path

import openpyxl


def cell_to_text(value) -> str:
    """Safely stringify any openpyxl cell value.

    str() already produces deterministic, sensible text for every type
    openpyxl can hand back (str, int, float, bool, datetime/date/time),
    so no per-type branching is needed beyond treating an empty cell as
    an empty string.
    """
    if value is None:
        return ""

    return str(value)


def iter_included_row_cells(row):
    """Yields (cell, text) for the non-empty cells of a row, in order.

    This is the single place that decides which cells count as "empty"
    (skipped) vs. included in a row's " | "-joined text. xlsx_locator
    reuses it so its cell index can never disagree with the text the
    detector actually sees.
    """
    for cell in row:
        text = cell_to_text(cell.value)

        if text != "":
            yield cell, text


def extract_text_from_xlsx(file_path: Path) -> dict:
    """Reads a workbook sheet by sheet, row by row, in file order.

    data_only=True reads each formula cell's last cached result (the
    value Excel itself computed and stored) instead of the formula
    string, and without evaluating anything ourselves. A formula cell
    that was never calculated by a spreadsheet application has no cached
    value and comes back as None, which is treated as empty like any
    other blank cell.

    Merged cells are safe: openpyxl only keeps a value on the top-left
    cell of a merge, every other covered cell reports value=None, so no
    special handling is needed to avoid duplicated or crashing reads.
    """
    workbook = openpyxl.load_workbook(
        file_path,
        data_only=True,
    )

    try:
        pages = []

        for page_number, sheet in enumerate(
            workbook.worksheets,
            start=1,
        ):
            lines = []

            for row in sheet.iter_rows():
                cell_texts = [
                    text
                    for _, text in iter_included_row_cells(
                        row
                    )
                ]

                if cell_texts:
                    lines.append(
                        " | ".join(cell_texts)
                    )

            pages.append(
                {
                    "page_number": page_number,
                    "text": "\n".join(lines),
                    "sheet_name": sheet.title,
                }
            )

        return {
            "page_count": len(pages),
            "pages": pages,
        }

    finally:
        workbook.close()
