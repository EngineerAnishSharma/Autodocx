"""
PDF utilities for AutoDocx.

Converts Markdown text into a simple PDF using fpdf2.
This is a lightweight conversion that preserves text content
and basic headings, not full Markdown styling.
"""
from io import BytesIO
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


class MarkdownPDF(FPDF):
    """Simple PDF renderer for markdown-like text."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.set_auto_page_break(auto=True, margin=15)
        # Reasonable margins to ensure space for text
        self.set_margins(left=15, top=15, right=15)
        self.add_page()
        # Core fonts don't support full unicode, but are enough for sanitized ASCII markdown
        self.set_font("Helvetica", size=11)

    def add_markdown(self, text: str):
        """
        Very lightweight markdown handling:
        - Lines starting with '# ' become big bold titles
        - Lines starting with '## ' become section headers
        - Lines starting with '- ' become bullet points
        - Everything else is rendered as normal text
        """
        for raw_line in text.splitlines():
            # Strip trailing spaces and sanitize unsupported characters
            line = _sanitize_text(raw_line.rstrip())
            # Soft-wrap extremely long sequences to avoid layout errors
            line = _soft_wrap(line)

            if not line:
                self.ln(4)
                continue

            if line.startswith("# "):
                self.set_font("Helvetica", "B", 16)
                self.multi_cell(0, 8, line[2:].strip())
                self.ln(2)
                self.set_font("Helvetica", size=11)
            elif line.startswith("## "):
                self.set_font("Helvetica", "B", 13)
                self.multi_cell(0, 7, line[3:].strip())
                self.ln(2)
                self.set_font("Helvetica", size=11)
            elif line.startswith("### "):
                self.set_font("Helvetica", "B", 11)
                self.multi_cell(0, 6, line[4:].strip())
                self.ln(1)
                self.set_font("Helvetica", size=11)
            elif line.startswith("- "):
                # Bullet point
                bullet_text = "- " + line[2:].strip()
                self.multi_cell(0, 5, bullet_text)
            else:
                # Normal text
                self.multi_cell(0, 5, line)


def markdown_to_pdf_bytes(markdown_text: str, title: Optional[str] = None) -> bytes:
    """
    Convert markdown text to a PDF and return the PDF as bytes.
    """
    # First try the richer markdown-aware rendering
    try:
        pdf = MarkdownPDF()
        if title:
            pdf.set_title(title)

        pdf.add_markdown(markdown_text)

        # fpdf2: get PDF as bytes/bytearray with dest="S"
        raw = pdf.output(dest="S")
        if isinstance(raw, (bytes, bytearray)):
            return bytes(raw)
        # Fallback: if some backend returns str
        return str(raw).encode("latin-1", errors="ignore")
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
        if isinstance(raw_fb, (bytes, bytearray)):
            return bytes(raw_fb)
        return str(raw_fb).encode("latin-1", errors="ignore")


