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
    pdf = MarkdownPDF()
    if title:
        pdf.set_title(title)

    pdf.add_markdown(markdown_text)

    # fpdf2: get PDF as bytes with dest="S"
    pdf_bytes = pdf.output(dest="S").encode("latin-1")
    return pdf_bytes


