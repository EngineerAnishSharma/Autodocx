"""
PDF utilities for AutoDocx.

Converts Markdown text into a styled PDF using fpdf2.
The renderer supports common markdown elements used in reports.
"""
import re
from typing import Optional

from fpdf import FPDF


def _sanitize_text(line: str) -> str:
    """
    Remove characters that can't be rendered by core PDF fonts
    (e.g. emojis, some unicode symbols) to avoid rendering errors.
    """
    # Keep basic printable ASCII; replace others with space
    return "".join(ch if 32 <= ord(ch) <= 126 else " " for ch in line)


def _soft_wrap(line: str, max_chunk: int = 80) -> str:
    """
    Soft-wrap very long words/segments by inserting spaces so that
    fpdf2's MultiCell never has to fit an infinite-long word on one line.
    """
    if len(line) <= max_chunk:
        return line

    parts = []
    current = ""
    for ch in line:
        current += ch
        if len(current) >= max_chunk:
            parts.append(current)
            current = ""
    if current:
        parts.append(current)
    return " ".join(parts)


def _clean_inline_markdown(text: str) -> str:
    """Strip simple inline markdown markers for cleaner PDF text."""
    # Images: keep a readable placeholder label.
    text = re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", r"[Image: \1]", text)
    # Links: keep label and URL in plain text.
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1 (\2)", text)

    for marker in ("**", "__", "~~", "`", "*", "_"):
        text = text.replace(marker, "")
    return text.strip()


def _split_table_row(row: str) -> list[str]:
    """Split a markdown table row into cleaned cells."""
    cells = [cell.strip() for cell in row.strip().strip("|").split("|")]
    return [_clean_inline_markdown(cell) for cell in cells]


class MarkdownPDF(FPDF):
    """Simple PDF renderer for markdown-like text."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.report_title = ""
        self.set_auto_page_break(auto=True, margin=15)
        # Reasonable margins to ensure space for text
        self.set_margins(left=15, top=15, right=15)
        self.add_page()
        # Core fonts don't support full unicode, but are enough for sanitized ASCII markdown
        self.set_font("Helvetica", size=11)

    def header(self):
        """Draw a lightweight header on each page."""
        if self.page_no() == 1:
            return
        self.set_font("Helvetica", "I", 9)
        header_text = _sanitize_text(self.report_title)[:80] if self.report_title else "AutoDocx Report"
        self.set_text_color(100, 100, 100)
        self.cell(0, 8, header_text, align="L")
        self.ln(8)
        self.set_draw_color(220, 220, 220)
        self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())
        self.ln(3)
        self.set_text_color(0, 0, 0)

    def footer(self):
        """Draw page number footer on each page."""
        self.set_y(-12)
        self.set_font("Helvetica", "I", 9)
        self.set_text_color(110, 110, 110)
        self.cell(0, 6, f"Page {self.page_no()}", align="C")
        self.set_text_color(0, 0, 0)

    def _render_table(self, header_cells: list[str], rows: list[list[str]]):
        """Render markdown table as bordered grid."""
        if not header_cells:
            return

        table_width = self.w - self.l_margin - self.r_margin
        col_count = max(len(header_cells), max((len(row) for row in rows), default=0))
        if col_count == 0:
            return

        col_width = table_width / col_count
        row_height = 7
        max_chars = max(int(col_width / 2.2), 6)

        def _fit(text: str) -> str:
            clean = _clean_inline_markdown(text)
            return clean if len(clean) <= max_chars else clean[: max_chars - 3] + "..."

        def _page_break_if_needed(next_row_height: float):
            if self.get_y() + next_row_height > self.h - self.b_margin:
                self.add_page()

        # Header row
        _page_break_if_needed(row_height)
        self.set_fill_color(240, 240, 240)
        self.set_font("Helvetica", "B", 10)
        for i in range(col_count):
            val = _fit(header_cells[i]) if i < len(header_cells) else ""
            self.cell(col_width, row_height, _sanitize_text(val), border=1, align="L", fill=True)
        self.ln(row_height)

        # Body rows
        self.set_font("Helvetica", size=10)
        for row in rows:
            _page_break_if_needed(row_height)
            for i in range(col_count):
                val = _fit(row[i]) if i < len(row) else ""
                self.cell(col_width, row_height, _sanitize_text(val), border=1, align="L")
            self.ln(row_height)

        self.ln(2)

    def add_markdown(self, text: str):
        """Render markdown-like content with headings, lists, and code blocks."""
        in_code_block = False
        code_lang = ""
        lines = text.splitlines()
        idx = 0

        while idx < len(lines):
            line = _sanitize_text(lines[idx].rstrip("\n"))
            stripped = line.strip()

            if stripped.startswith("```"):
                fence_lang = stripped[3:].strip().lower()
                in_code_block = not in_code_block
                if in_code_block:
                    code_lang = fence_lang
                    self.ln(1)
                    if code_lang == "mermaid":
                        self.set_font("Helvetica", "I", 10)
                        self.multi_cell(0, 5, "Diagram (Mermaid):")
                    else:
                        self.set_font("Courier", size=9)
                else:
                    code_lang = ""
                    self.set_font("Helvetica", size=11)
                    self.ln(1)
                idx += 1
                continue

            if in_code_block:
                if code_lang == "mermaid":
                    mer = stripped
                    if mer and not mer.startswith(("flowchart", "graph", "sequenceDiagram", "classDiagram")):
                        mer = mer.replace("-->", " -> ")
                        mer = mer.replace("--", " - ")
                        mer = mer.replace("|", " ")
                        self.multi_cell(0, 5, _soft_wrap(f"- {_clean_inline_markdown(mer)}"))
                else:
                    code_line = _soft_wrap(line)
                    self.multi_cell(0, 4.5, code_line)
                idx += 1
                continue

            if not stripped:
                self.ln(3)
                idx += 1
                continue

            # Markdown table: header row + separator row + data rows.
            if (
                stripped.startswith("|")
                and idx + 1 < len(lines)
                and re.fullmatch(r"\s*\|?\s*[:\- ]+\|[|:\- ]+\|?\s*", _sanitize_text(lines[idx + 1].strip()))
            ):
                header_cells = _split_table_row(stripped)
                idx += 2  # Skip header and separator row

                data_rows: list[list[str]] = []
                while idx < len(lines) and _sanitize_text(lines[idx].strip()).startswith("|"):
                    data_rows.append(_split_table_row(_sanitize_text(lines[idx])))
                    idx += 1

                self._render_table(header_cells, data_rows)
                continue

            heading_match = re.match(r"^(#{1,6})\s+(.+)$", stripped)
            if heading_match:
                level = len(heading_match.group(1))
                title = _clean_inline_markdown(heading_match.group(2))
                size_map = {1: 18, 2: 15, 3: 13, 4: 12, 5: 11, 6: 11}
                style = "B" if level <= 4 else ""
                self.set_font("Helvetica", style, size_map[level])
                self.multi_cell(0, 7 if level <= 2 else 6, _soft_wrap(title))
                self.ln(1)
                self.set_font("Helvetica", size=11)
                idx += 1
                continue

            marker_only = stripped.replace(" ", "")
            if re.fullmatch(r"[-_*]{3,}", marker_only):
                y = self.get_y()
                self.line(15, y, self.w - 15, y)
                self.ln(3)
                idx += 1
                continue

            unordered = re.match(r"^(\s*)[-*+]\s+(.+)$", line)
            if unordered:
                indent = min(len(unordered.group(1)), 12)
                item_text = _clean_inline_markdown(unordered.group(2))
                self.set_x(15 + indent)
                self.multi_cell(0, 5, _soft_wrap(f"- {item_text}"))
                idx += 1
                continue

            ordered = re.match(r"^(\s*)(\d+)\.\s+(.+)$", line)
            if ordered:
                indent = min(len(ordered.group(1)), 12)
                num = ordered.group(2)
                item_text = _clean_inline_markdown(ordered.group(3))
                self.set_x(15 + indent)
                self.multi_cell(0, 5, _soft_wrap(f"{num}. {item_text}"))
                idx += 1
                continue

            quote_match = re.match(r"^\s*>\s?(.*)$", line)
            if quote_match:
                quote_text = _clean_inline_markdown(quote_match.group(1))
                self.set_x(19)
                self.multi_cell(0, 5, _soft_wrap(f"| {quote_text}"))
                idx += 1
                continue

            plain = _clean_inline_markdown(stripped)
            self.multi_cell(0, 5, _soft_wrap(plain))
            idx += 1


def markdown_to_pdf_bytes(markdown_text: str, title: Optional[str] = None) -> bytes:
    """
    Convert markdown text to a PDF and return the PDF as bytes.
    """
    def _ensure_pdf_bytes(raw_obj) -> bytes:
        """Normalize output object to bytes and verify PDF signature."""
        if isinstance(raw_obj, (bytes, bytearray)):
            data = bytes(raw_obj)
        else:
            data = str(raw_obj).encode("latin-1", errors="ignore")

        if not data.startswith(b"%PDF"):
            raise ValueError("Generated content is not a valid PDF stream")
        return data

    # First try the richer markdown-aware rendering
    try:
        pdf = MarkdownPDF()
        if title:
            pdf.report_title = title
            pdf.set_title(title)
            pdf.set_font("Helvetica", "B", 15)
            pdf.multi_cell(0, 8, _sanitize_text(title))
            pdf.ln(2)
            pdf.set_font("Helvetica", size=11)

        pdf.add_markdown(markdown_text)

        # fpdf2: get PDF as bytes/bytearray with dest="S"
        raw = pdf.output(dest="S")
        return _ensure_pdf_bytes(raw)
    except Exception:
        # Fallback: ultra-safe plain-text export (no complex wrapping)
        safe_text = "".join(
            ch if (ch == "\n" or 32 <= ord(ch) <= 126) else " "
            for ch in markdown_text
        )

        fb = FPDF()
        fb.set_auto_page_break(auto=True, margin=15)
        fb.set_margins(left=15, top=15, right=15)
        fb.add_page()
        fb.set_font("Helvetica", size=11)

        if title:
            fb.set_font("Helvetica", "B", 14)
            fb.cell(0, 8, _sanitize_text(title)[:80], ln=1)
            fb.ln(4)
            fb.set_font("Helvetica", size=11)

        # Limit to first N lines / chars to keep it simple and robust
        max_lines = 300
        lines = safe_text.splitlines()[:max_lines]
        for raw in lines:
            line = _sanitize_text(raw)[:100]
            fb.cell(0, 5, line, ln=1)

        raw_fb = fb.output(dest="S")
        return _ensure_pdf_bytes(raw_fb)


