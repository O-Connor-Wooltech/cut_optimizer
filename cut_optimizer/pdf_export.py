from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, List, Tuple


from .optimizer import OptimizeResult, u_to_mm_str

# Lazy imports so the app can run without reportlab until PDF export is used.
def _string_width(text: str, font_name: str, font_size: float) -> float:
    from reportlab.pdfbase.pdfmetrics import stringWidth
    return stringWidth(text, font_name, font_size)



@dataclass
class _PageLayout:
    page_w: float
    page_h: float
    margin: float
    header_area_h: float
    footer_area_h: float
    index_col_w: float
    min_col_w: float
    max_col_w: float
    font_size: float
    line_h: float
    header_row_h: float
    row_h: float
    block_gap: float
    pad_x: float
    pad_y: float


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def _truncate(text: str, font_name: str, font_size: float, max_w: float) -> str:
    """Truncate a string with ellipsis to fit within max_w points."""
    if not text:
        return ""
    if _string_width(text, font_name, font_size) <= max_w:
        return text
    ell = "..."
    if _string_width(ell, font_name, font_size) >= max_w:
        return ""
    # Binary search a cut length
    lo, hi = 0, len(text)
    while lo < hi:
        mid = (lo + hi) // 2
        cand = text[:mid] + ell
        if _string_width(cand, font_name, font_size) <= max_w:
            lo = mid + 1
        else:
            hi = mid
    return text[: max(0, lo - 1)] + ell


def _measure_col_width(
    header1: str,
    header2: str,
    cells: List[Tuple[str, str]],
    *,
    font_name: str,
    font_bold: str,
    font_size: float,
    pad_x: float,
    min_col_w: float,
    max_col_w: float,
) -> float:
    widths: List[float] = []

    if header1:
        widths.append(_string_width(header1, font_bold, font_size))
    if header2:
        widths.append(_string_width(header2, font_name, font_size))

    for a, b in cells:
        if a:
            widths.append(_string_width(a, font_name, font_size))
        if b:
            widths.append(_string_width(b, font_name, font_size))

    required = (max(widths) if widths else 0.0) + 2 * pad_x
    return _clamp(required, min_col_w, max_col_w)


def export_plan_pdf(
    path: str,
    result: OptimizeResult,
    kerf_mm: float,
    *,
    title: str = "Cut plan",
) -> None:
    """Export the cut plan as a multi-page PDF.

    Layout:
      - Cuts listed vertically (rows)
      - Sticks listed horizontally (columns)
      - Column widths are computed from the label/length text so they fit (within bounds)
      - If sticks exceed page width, columns wrap into a new block below
      - If blocks exceed page height, flow onto additional pages

    This makes the number of sticks per row automatically adapt based on the
    actual label/length text width.
    """

    try:
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.pdfgen.canvas import Canvas
    except Exception as e:
        raise RuntimeError(
            "PDF export requires the 'reportlab' package. Install it with: pip install reportlab"
        ) from e

    c = Canvas(path, pagesize=landscape(A4))
    page_w, page_h = landscape(A4)

    font_name = "Helvetica"
    font_bold = "Helvetica-Bold"
    font_size = 8.0
    line_h = font_size + 1.5
    pad_x = 3.0
    pad_y = 2.5

    # Two-line cells (length on line 1, label on line 2)
    row_h = 2 * line_h + 2 * pad_y
    header_row_h = 2 * line_h + 2 * pad_y

    layout = _PageLayout(
        page_w=page_w,
        page_h=page_h,
        margin=36.0,
        header_area_h=40.0,
        footer_area_h=18.0,
        index_col_w=32.0,
        min_col_w=72.0,
        max_col_w=190.0,
        font_size=font_size,
        line_h=line_h,
        header_row_h=header_row_h,
        row_h=row_h,
        block_gap=14.0,
        pad_x=pad_x,
        pad_y=pad_y,
    )

    plans = result.plans
    stick_count = len(plans)

    # Pre-rendered text for each stick's cuts.
    stick_headers: List[Tuple[str, str]] = []  # (line1, line2)
    stick_cells: List[List[Tuple[str, str]]] = []  # [(len_mm, label), ...]
    max_rows_total = 0

    for i, plan in enumerate(plans, start=1):
        stock_mm = u_to_mm_str(plan.stock_length_u)
        stick_headers.append((f"Stick {i}", f"({stock_mm})"))

        cells: List[Tuple[str, str]] = []
        for p in plan.parts:
            length_mm = u_to_mm_str(p.length_u)
            label = (p.label or "").strip()
            cells.append((length_mm, label))

        stick_cells.append(cells)
        max_rows_total = max(max_rows_total, len(cells))

    # If there are no plans, still create a PDF with a header.
    if stick_count == 0:
        _draw_page_header(c, layout, title, kerf_mm, page_no=1)
        c.setFont(font_name, 12)
        c.drawString(layout.margin, layout.page_h - layout.margin - layout.header_area_h, "(No sticks in plan)")
        c.showPage()
        c.save()
        return

    # If there are sticks but no cuts at all.
    if max_rows_total == 0:
        _draw_page_header(c, layout, title, kerf_mm, page_no=1)
        c.setFont(font_name, 12)
        c.drawString(layout.margin, layout.page_h - layout.margin - layout.header_area_h, "(No cuts in plan)")
        c.showPage()
        c.save()
        return

    # Compute a per-stick column width based on the actual text.
    col_widths: List[float] = []
    for (h1, h2), cells in zip(stick_headers, stick_cells):
        col_w = _measure_col_width(
            h1,
            h2,
            cells,
            font_name=font_name,
            font_bold=font_bold,
            font_size=layout.font_size,
            pad_x=layout.pad_x,
            min_col_w=layout.min_col_w,
            max_col_w=layout.max_col_w,
        )
        col_widths.append(col_w)

    usable_w = layout.page_w - 2 * layout.margin - layout.index_col_w

    # Partition sticks into blocks that fit across the page.
    blocks: List[Tuple[int, int]] = []
    col_start = 0
    while col_start < stick_count:
        w_sum = 0.0
        col_end = col_start
        while col_end < stick_count:
            w = col_widths[col_end]
            if col_end > col_start and (w_sum + w) > usable_w:
                break
            w_sum += w
            col_end += 1
        # Always make progress.
        if col_end == col_start:
            col_end = col_start + 1
        blocks.append((col_start, col_end))
        col_start = col_end

    top_y = layout.page_h - layout.margin - layout.header_area_h
    bottom_y = layout.margin + layout.footer_area_h
    usable_h = top_y - bottom_y

    # How many cut rows can fit in one "row slice" on a page.
    max_rows_fit = max(1, int((usable_h - layout.header_row_h) / layout.row_h))
    rows_per_slice = min(max_rows_total, max_rows_fit)

    page_no = 1
    row_start = 0
    while row_start < max_rows_total:
        row_end = min(max_rows_total, row_start + rows_per_slice)

        _draw_page_header(c, layout, title, kerf_mm, page_no=page_no, row_range=(row_start + 1, row_end))
        y_cursor = top_y

        for b_start, b_end in blocks:
            # Only render as many rows as are needed for this *block* of sticks.
            # Previously we always used the global row slice height (row_end-row_start),
            # which created lots of empty rows when some sticks in the block had fewer cuts.
            # This in turn reduced how many blocks could fit on a page and increased page count.
            rows_needed = 0
            for stick_list in stick_cells[b_start:b_end]:
                if len(stick_list) > row_start:
                    rows_needed = max(rows_needed, min(row_end, len(stick_list)) - row_start)

            # If every stick in this block is exhausted for this row slice, skip it.
            if rows_needed <= 0:
                continue

            block_row_end = row_start + rows_needed
            block_h = layout.header_row_h + rows_needed * layout.row_h

            # If the next block won't fit, start a new page and continue the same row slice.
            if y_cursor - block_h < bottom_y:
                c.showPage()
                page_no += 1
                _draw_page_header(
                    c,
                    layout,
                    title,
                    kerf_mm,
                    page_no=page_no,
                    row_range=(row_start + 1, row_end),
                )
                y_cursor = top_y

            _draw_block(
                c,
                layout,
                x0=layout.margin,
                y_top=y_cursor,
                headers=stick_headers[b_start:b_end],
                cells=stick_cells[b_start:b_end],
                col_widths=col_widths[b_start:b_end],
                row_start=row_start,
                row_end=block_row_end,
            )

            y_cursor -= block_h + layout.block_gap

        # Move to next row slice.
        row_start = row_end
        if row_start < max_rows_total:
            c.showPage()
            page_no += 1

    c.save()


def _draw_page_header(
    c: Any,
    layout: _PageLayout,
    title: str,
    kerf_mm: float,
    *,
    page_no: int,
    row_range: Tuple[int, int] | None = None,
) -> None:
    x = layout.margin
    y = layout.page_h - layout.margin

    c.setFont("Helvetica-Bold", 14)
    c.drawString(x, y, title)

    c.setFont("Helvetica", 9)
    meta = f"Kerf: {kerf_mm:.1f} mm"
    if row_range is not None:
        meta += f"   Cuts: {row_range[0]}-{row_range[1]}"
    meta += f"   Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    c.drawRightString(layout.page_w - layout.margin, y, meta)

    # Footer page number
    c.setFont("Helvetica", 9)
    c.drawRightString(layout.page_w - layout.margin, layout.margin - 6, f"Page {page_no}")


def _draw_block(
    c: Any,
    layout: _PageLayout,
    *,
    x0: float,
    y_top: float,
    headers: List[Tuple[str, str]],
    cells: List[List[Tuple[str, str]]],
    col_widths: List[float],
    row_start: int,
    row_end: int,
) -> None:
    """Draw one block of columns (sticks) for a given row slice."""

    font_name = "Helvetica"
    font_bold = "Helvetica-Bold"
    font_size = layout.font_size

    rows = row_end - row_start
    cols = len(headers)

    total_w = layout.index_col_w + sum(col_widths)
    total_h = layout.header_row_h + rows * layout.row_h

    y0 = y_top - total_h

    # Outer box
    c.setLineWidth(0.6)
    c.rect(x0, y0, total_w, total_h)

    # Vertical grid lines
    c.setLineWidth(0.4)
    x = x0 + layout.index_col_w
    c.line(x, y0, x, y_top)
    x_cursor = x
    for w in col_widths:
        x_cursor += w
        c.line(x_cursor, y0, x_cursor, y_top)

    # Horizontal grid lines
    y = y_top - layout.header_row_h
    c.line(x0, y, x0 + total_w, y)
    for i in range(rows):
        y = y_top - layout.header_row_h - (i + 1) * layout.row_h
        c.line(x0, y, x0 + total_w, y)

    # Header: Cut #
    c.setFont(font_bold, font_size)
    header_y1 = y_top - layout.pad_y - font_size
    c.drawString(x0 + layout.pad_x, header_y1, "Cut")

    # Stick headers
    x_left = x0 + layout.index_col_w
    for j, ((h1, h2), w) in enumerate(zip(headers, col_widths)):
        max_w = w - 2 * layout.pad_x
        c.setFont(font_bold, font_size)
        c.drawString(x_left + layout.pad_x, header_y1, _truncate(h1, font_bold, font_size, max_w))
        if h2:
            c.setFont(font_name, font_size)
            header_y2 = header_y1 - layout.line_h
            c.drawString(x_left + layout.pad_x, header_y2, _truncate(h2, font_name, font_size, max_w))
        x_left += w

    # Body cells (two-line: length then label)
    for i in range(rows):
        cut_idx = row_start + i
        row_top = y_top - layout.header_row_h - i * layout.row_h
        line1_y = row_top - layout.pad_y - font_size
        line2_y = line1_y - layout.line_h

        # Cut index column
        c.setFont(font_name, font_size)
        c.drawRightString(x0 + layout.index_col_w - layout.pad_x, line1_y, str(cut_idx + 1))

        x_left = x0 + layout.index_col_w
        for stick_list, w in zip(cells, col_widths):
            max_w = w - 2 * layout.pad_x
            if cut_idx < len(stick_list):
                length_mm, label = stick_list[cut_idx]
                if length_mm:
                    c.setFont(font_name, font_size)
                    c.drawString(x_left + layout.pad_x, line1_y, _truncate(length_mm, font_name, font_size, max_w))
                if label:
                    c.setFont(font_name, font_size)
                    c.drawString(x_left + layout.pad_x, line2_y, _truncate(label, font_name, font_size, max_w))
            x_left += w
