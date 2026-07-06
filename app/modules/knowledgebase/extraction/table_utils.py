"""
Table formatting helpers for structured extraction.
"""

from __future__ import annotations


def table_rows_to_markdown(rows: list[list[str | None]]) -> str | None:
    """Convert table rows into readable Markdown, preserving columns."""
    if not rows:
        return None

    normalized_rows: list[list[str]] = []
    for row in rows:
        cells = [str(cell or "").strip() for cell in row]
        if any(cells):
            normalized_rows.append(cells)

    if not normalized_rows:
        return None

    column_count = max(len(row) for row in normalized_rows)
    padded_rows = [row + [""] * (column_count - len(row)) for row in normalized_rows]

    header = padded_rows[0]
    body = padded_rows[1:] if len(padded_rows) > 1 else []

    lines = [
        "| " + " | ".join(header) + " |",
        "| " + " | ".join(["---"] * column_count) + " |",
    ]
    for row in body:
        lines.append("| " + " | ".join(row) + " |")

    return "\n".join(lines)


def dataframe_to_markdown(dataframe) -> str:
    """Convert a pandas DataFrame to Markdown table text."""
    headers = [str(column) for column in dataframe.columns.tolist()]
    rows = [[str(value) for value in row] for row in dataframe.values.tolist()]
    markdown = table_rows_to_markdown([headers, *rows])
    return markdown or ""
