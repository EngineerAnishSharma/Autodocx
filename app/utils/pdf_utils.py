"""
PDF utilities for AutoDocx.
Converts Markdown to a styled PDF using fpdf2.

Improvements over v1:
- Proper cover page with title, subtitle, and generation metadata
- Visually distinct section headings with numbered accent badges
- Alternating-row tables with better column width distribution
- Mermaid diagrams constrained + centered with caption
- Code blocks with left border accent and rounded background
- Blockquote styling (left bar + tinted background)
- Better inline bold/italic rendering
- Page break safety on every element
- Metadata blockquote rendered as an info card
"""

import re
from typing import Optional, List, Tuple
from fpdf import FPDF
from datetime import datetime
import base64
import zlib
import urllib.request
import io


# ── Text helpers ──────────────────────────────────────────────────────────────


def _safe(text: str) -> str:
    """Keep only printable Latin-1 characters."""
    return "".join(
        ch if (0x20 <= ord(ch) <= 0x7E) or (0xA0 <= ord(ch) <= 0xFF) else " "
        for ch in str(text)
    )


def _soft_wrap(text: str, n: int = 80) -> str:
    """Break very long unbreakable tokens."""
    if len(text) <= n:
        return text
    parts, cur = [], ""
    for ch in text:
        cur += ch
        if len(cur) >= n:
            parts.append(cur)
            cur = ""
    if cur:
        parts.append(cur)
    return " ".join(parts)


def _strip_md(text: str) -> str:
    """Strip inline markdown markers returning plain text."""
    text = re.sub(r"!\[([^\]]*)\]\([^)]+\)", r"[Image: \1]", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"\*{3}([^*\n]+)\*{3}", r"\1", text)
    text = re.sub(r"_{3}([^_\n]+)_{3}", r"\1", text)
    text = re.sub(r"\*{2}([^*\n]+)\*{2}", r"\1", text)
    text = re.sub(r"_{2}([^_\n]+)_{2}", r"\1", text)
    text = re.sub(r"\*([^*\n]+)\*", r"\1", text)
    text = re.sub(r"_([^_\n]+)_", r"\1", text)
    text = re.sub(r"~~([^~\n]+)~~", r"\1", text)
    text = re.sub(r"`([^`]+)`", r"\1", text)
    return text.strip()


def _inline_segments(text: str) -> List[Tuple[bool, bool, str]]:
    """Split markdown inline string into (bold, italic, text) tuples."""
    segments = []
    pattern = re.compile(
        r"(\*{3}[^*\n]+?\*{3}"
        r"|\*{2}[^*\n]+?\*{2}"
        r"|\*[^*\n]+?\*"
        r"|_{2}[^_\n]+?_{2}"
        r"|_[^_\n]+?_"
        r"|`[^`\n]+?`)"
    )
    pos = 0
    for m in pattern.finditer(text):
        if m.start() > pos:
            chunk = _safe(_soft_wrap(text[pos : m.start()]))
            if chunk.strip():
                segments.append((False, False, chunk))
        raw = m.group(0)
        if raw.startswith("***") or raw.startswith("___"):
            segments.append((True, True, _safe(_soft_wrap(raw[3:-3]))))
        elif raw.startswith("**") or raw.startswith("__"):
            segments.append((True, False, _safe(_soft_wrap(raw[2:-2]))))
        elif raw.startswith("`"):
            segments.append((False, False, _safe(_soft_wrap(raw[1:-1]))))
        else:
            segments.append((False, True, _safe(_soft_wrap(raw[1:-1]))))
        pos = m.end()
    if pos < len(text):
        chunk = _safe(_soft_wrap(text[pos:]))
        if chunk.strip():
            segments.append((False, False, chunk))
    if not segments:
        segments = [(False, False, _safe(_soft_wrap(text)))]
    return segments


def _is_separator(line: str) -> bool:
    s = line.strip()
    return bool(s) and "|" in s and bool(re.fullmatch(r"[\s|:\-]+", s))


def _split_row(row: str) -> List[str]:
    return [_strip_md(c.strip()) for c in row.strip().strip("|").split("|")]


# ── Colour palette ────────────────────────────────────────────────────────────
# All as RGB tuples for easy unpacking.
_NAVY = (15, 40, 100)  # primary brand dark blue
_ACCENT = (16, 185, 129)  # emerald green accent (matches UI)
_ACCENT_DARK = (10, 130, 90)  # darker green for text on light bg
_LIGHT_MINT = (236, 253, 245)  # very light green tint
_LIGHT_BLUE = (239, 246, 255)  # section header bg
_CODE_BG = (248, 249, 250)  # code block background
_CODE_BORDER = (209, 213, 219)  # code block left border
_TABLE_HEAD = (15, 40, 100)  # table header fill (navy)
_TABLE_ALT = (249, 250, 251)  # alternating table row
_TABLE_EVEN = (255, 255, 255)  # even table row
_MERMAID_BG = (239, 246, 255)  # mermaid fallback bg
_BQ_BG = (240, 253, 250)  # blockquote / info card bg
_BQ_BAR = (16, 185, 129)  # blockquote left bar colour
_RULE = (209, 213, 219)  # horizontal rule
_SUBTEXT = (100, 116, 139)  # muted grey for metadata
_BODY = (30, 41, 59)  # body text (not pure black)


# ── Section number extractor ──────────────────────────────────────────────────
_SECTION_RE = re.compile(r"^(\d+)\.\s+(.+)$")

# ── Diagram title keywords — any H3 whose text contains one of these
# keywords (case-insensitive) is treated as a diagram caption heading.
# It is stored pending and drawn on the diagram's own page.
_DIAGRAM_TITLE_KEYWORDS = (
    "use case", "interaction flow", "architecture layer", "entity relationship",
    "er diagram", "sequence", "class diagram", "core interaction", "flow diagram",
    "architecture layers",
)


# ── PDF class ─────────────────────────────────────────────────────────────────


class MarkdownPDF(FPDF):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.report_title = ""
        self.report_subtitle = ""
        self.set_auto_page_break(auto=True, margin=20)
        self.set_margins(left=20, top=20, right=20)
        self._in_cover = False
        self._started_sections = False
        # When we see a diagram heading (H3) in markdown, we don't render it
        # immediately. Instead we remember it here and let the diagram renderer
        # place the title on the same page as the figure.
        self._pending_diagram_title: Optional[str] = None

    # ── Header / Footer ───────────────────────────────────────────────────────

    def header(self):
        if self._in_cover or self.page_no() <= 1:
            return
        self.set_font("Helvetica", "I", 7.5)
        self.set_text_color(*_SUBTEXT)
        title = (
            _safe(self.report_title)[:80] if self.report_title else "AutoDocx Report"
        )
        self.cell(0, 5, title, align="L")
        self.ln(5)
        self.set_draw_color(*_RULE)
        self.set_line_width(0.3)
        self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())
        self.ln(3)
        self.set_text_color(*_BODY)

    def footer(self):
        if self._in_cover:
            return
        self.set_y(-14)
        self.set_draw_color(*_RULE)
        self.set_line_width(0.3)
        self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())
        self.ln(2)
        self.set_font("Helvetica", "I", 7.5)
        self.set_text_color(*_SUBTEXT)
        self.cell(0, 5, f"Page {self.page_no()}", align="C")
        self.set_text_color(*_BODY)

    # ── Cover page ────────────────────────────────────────────────────────────

    def make_cover(self, title: str, subtitle: str = "", generated_at: str = ""):
        """Render a clean cover page."""
        self._in_cover = True
        self.add_page()

        # Full-width navy header band
        self.set_fill_color(*_NAVY)
        self.rect(0, 0, self.w, 80, "F")

        # Green accent stripe at bottom of band
        self.set_fill_color(*_ACCENT)
        self.rect(0, 77, self.w, 3, "F")

        # Title text
        self.set_y(18)
        self.set_text_color(255, 255, 255)
        self.set_font("Helvetica", "B", 22)
        self.multi_cell(0, 10, _safe(title), align="C")

        # Subtitle
        if subtitle:
            self.set_font("Helvetica", "", 12)
            self.set_text_color(196, 230, 210)
            safe_sub = _safe(subtitle)
            try:
                self.multi_cell(0, 7, safe_sub, align="C")
            except Exception:
                self.set_x(self.l_margin)
                self.cell(0, 7, safe_sub[:80], align="C")

        # Body area: decorative box
        self.set_y(100)
        self.set_fill_color(*_LIGHT_MINT)
        self.set_draw_color(*_ACCENT)
        self.set_line_width(0.8)
        self.rect(self.l_margin, 100, self.w - self.l_margin - self.r_margin, 60, "FD")

        # Inside the box: metadata
        self.set_y(112)
        self.set_text_color(*_ACCENT_DARK)
        self.set_font("Helvetica", "B", 11)
        self.cell(0, 7, "Documentation Report", align="C")
        self.ln(8)

        self.set_font("Helvetica", "", 10)
        self.set_text_color(*_BODY)
        lines = [
            f"Generated by AutoDocx Multi-Agent Engine",
            f"Date: {generated_at or datetime.now().strftime('%Y-%m-%d %H:%M')}",
        ]
        for line in lines:
            self.cell(0, 6, _safe(line), align="C")
            self.ln(6)

        # Bottom accent bar
        self.set_fill_color(*_ACCENT)
        self.rect(0, self.h - 12, self.w, 12, "F")
        self.set_y(self.h - 10)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(255, 255, 255)
        self.cell(0, 6, "AutoDocx  |  Intelligent Documentation Generator", align="C")

        self._in_cover = False
        self.add_page()

    # ── Utility ───────────────────────────────────────────────────────────────

    def _reset(self, size: float = 11):
        self.set_font("Helvetica", size=size)
        self.set_text_color(*_BODY)
        self.set_line_width(0.2)

    def _check_page_break(self, needed: float = 10):
        if self.get_y() + needed > self.h - self.b_margin:
            self.add_page()

    def _write_inline(self, text: str, lh: float = 5.5):
        """Write text honouring **bold** and *italic* markers inline."""
        for bold, italic, chunk in _inline_segments(text):
            style = ("B" if bold else "") + ("I" if italic else "")
            self.set_font("Helvetica", style, 11)
            self.set_text_color(*_BODY)
            if chunk:
                self.write(lh, chunk)
        self._reset()

    # ── Headings ──────────────────────────────────────────────────────────────

    def _h1(self, title: str):
        """H1: full-width navy bar — used only for the doc title."""
        self._check_page_break(16)
        self.ln(4)
        self.set_fill_color(*_NAVY)
        self.set_text_color(255, 255, 255)
        self.set_font("Helvetica", "B", 17)
        self.multi_cell(0, 11, _safe(_soft_wrap(title)), fill=True, align="L")
        self.ln(3)
        self._reset()

    def _h2(self, title: str):
        """H2: accent-bordered section heading with optional number badge."""
        is_numbered = bool(_SECTION_RE.match(title))
        if is_numbered and self.get_y() > self.t_margin + 10:
            self.add_page()
        else:
            self._check_page_break(25)
        self.ln(5)

        # Green left accent bar (3 px wide)
        bar_x = self.l_margin
        bar_y = self.get_y()
        bar_h = 9
        self.set_fill_color(*_ACCENT)
        self.rect(bar_x, bar_y, 3, bar_h, "F")

        # Light blue fill for the rest of the row
        self.set_fill_color(*_LIGHT_BLUE)
        text_x = bar_x + 4
        self.set_xy(text_x, bar_y)
        available_w = self.w - text_x - self.r_margin

        # Check for numbered section — draw a small badge
        sm = _SECTION_RE.match(title)
        if sm:
            num, rest = sm.group(1), sm.group(2)
            badge_w = 7
            self.set_fill_color(*_NAVY)
            self.rect(text_x, bar_y, badge_w, bar_h, "F")
            self.set_xy(text_x, bar_y)
            self.set_font("Helvetica", "B", 9)
            self.set_text_color(255, 255, 255)
            self.cell(badge_w, bar_h, _safe(num), align="C")
            self.set_fill_color(*_LIGHT_BLUE)
            self.set_font("Helvetica", "B", 12)
            self.set_text_color(*_NAVY)
            self.cell(
                available_w - badge_w,
                bar_h,
                _safe(_soft_wrap(rest)),
                fill=True,
                align="L",
            )
        else:
            self.set_font("Helvetica", "B", 12)
            self.set_text_color(*_NAVY)
            self.cell(
                available_w, bar_h, _safe(_soft_wrap(title)), fill=True, align="L"
            )

        self.ln(bar_h + 3)
        self._reset()

    def _h3(self, title: str):
        """H3: small band with subtle background to stand out from body text."""
        self._check_page_break(14)
        self.ln(3)
        y = self.get_y()
        band_h = 7
        self.set_fill_color(246, 248, 252)
        self.rect(self.l_margin, y, self.w - self.l_margin - self.r_margin, band_h, "F")
        self.set_xy(self.l_margin + 1.5, y + 1)
        self.set_font("Helvetica", "B", 10.5)
        self.set_text_color(*_NAVY)
        self.multi_cell(
            0,
            5,
            _safe(_soft_wrap(title)),
        )
        self.ln(2)
        self._reset()

    def _h4(self, title: str):
        self._check_page_break(10)
        self.ln(2)
        self.set_font("Helvetica", "B", 10.5)
        self.set_text_color(*_BODY)
        self.multi_cell(0, 6, _safe(_soft_wrap(title)))
        self.ln(1)
        self._reset()

    def _hN(self, title: str):
        self._check_page_break(8)
        self.ln(1)
        self.set_font("Helvetica", "B", 10)
        self.set_text_color(*_SUBTEXT)
        self.multi_cell(0, 5.5, _safe(_soft_wrap(title)))
        self._reset()

    # ── Info card (blockquote / metadata) ────────────────────────────────────

    def _info_card(self, lines_text: List[str]):
        """Render a tinted card with a left green bar — used for > blockquotes."""
        self._check_page_break(6 * len(lines_text) + 8)
        self.ln(2)
        card_x = self.l_margin
        card_y = self.get_y()
        card_w = self.w - self.l_margin - self.r_margin
        line_h = 5.5
        padding = 4

        total_h = padding + line_h * len(lines_text) + padding

        self.set_fill_color(*_BQ_BG)
        self.rect(card_x, card_y, card_w, total_h, "F")

        self.set_fill_color(*_BQ_BAR)
        self.rect(card_x, card_y, 3, total_h, "F")

        self.set_draw_color(*_ACCENT)
        self.set_line_width(0.3)
        self.rect(card_x, card_y, card_w, total_h, "D")

        self.set_xy(card_x + 6, card_y + padding)
        self.set_font("Helvetica", "", 9)
        self.set_text_color(*_BODY)
        for line in lines_text:
            self.set_x(card_x + 6)
            self._write_inline(_strip_md(line), line_h)
            self.ln(line_h)

        self.set_y(card_y + total_h + 3)
        self._reset()

    # ── Table ─────────────────────────────────────────────────────────────────

    def _table(self, headers: List[str], rows: List[List[str]]):
        if not headers:
            return
        col_count = max(len(headers), max((len(r) for r in rows), default=1))
        if col_count == 0:
            return

        self._check_page_break(12)
        self.ln(3)

        usable_w = self.w - self.l_margin - self.r_margin

        sample = [headers] + rows[:5]
        col_lens = [0] * col_count
        for r in sample:
            for i, cell in enumerate(r):
                if i < col_count:
                    col_lens[i] = max(col_lens[i], len(_safe(cell)))
        total_len = sum(col_lens) or 1
        col_widths = [max(14, (cl / total_len) * usable_w) for cl in col_lens]
        scale = usable_w / sum(col_widths)
        col_widths = [cw * scale for cw in col_widths]

        line_h = 6.5
        head_h = 7.5

        self.set_fill_color(*_TABLE_HEAD)
        self.set_text_color(255, 255, 255)
        self.set_font("Helvetica", "B", 9)
        x_start = self.l_margin
        for i in range(col_count):
            hdr = _safe(headers[i]) if i < len(headers) else ""
            self.set_xy(x_start + sum(col_widths[:i]), self.get_y())
            self.cell(col_widths[i], head_h, hdr, border=1, fill=True, align="C")
        self.ln(head_h)

        self.set_font("Helvetica", size=8.5)
        for row_idx, row in enumerate(rows):
            fill_color = _TABLE_ALT if row_idx % 2 == 0 else _TABLE_EVEN
            self.set_fill_color(*fill_color)
            self.set_text_color(*_BODY)
            row_y = self.get_y()

            row_h = line_h
            for i in range(col_count):
                cell_val = _safe(row[i]) if i < len(row) else ""
                chars_per_line = max(1, int(col_widths[i] / 2.0))
                lines_needed = max(1, len(cell_val) // chars_per_line + 1)
                row_h = max(row_h, lines_needed * line_h)

            self._check_page_break(row_h + 2)
            row_y = self.get_y()

            for i in range(col_count):
                cell_val = _safe(row[i]) if i < len(row) else ""
                cx = x_start + sum(col_widths[:i])
                self.set_xy(cx, row_y)
                self.multi_cell(
                    col_widths[i],
                    line_h,
                    cell_val,
                    border=1,
                    fill=True,
                    align="L",
                    max_line_height=line_h,
                )
                self.set_y(row_y)

            self.ln(row_h)

        self.ln(3)
        self._reset()

    # ── Code block ────────────────────────────────────────────────────────────

    def _code(self, lines_in: List[str], lang: str):
        if lang == "mermaid" and lines_in:
            self._render_mermaid(lines_in)
            return

        if not lines_in:
            return

        # ── Pre-process: wrap long lines ──────────────────────────────────
        rendered_lines = []
        for raw_line in lines_in:
            safe_line = _safe(raw_line.rstrip())
            while len(safe_line) > 90:
                rendered_lines.append(safe_line[:90])
                safe_line = "  " + safe_line[90:]
            rendered_lines.append(safe_line)

        line_h = 4.5
        code_x = self.l_margin
        code_w = self.w - self.l_margin - self.r_margin
        text_x = code_x + 5

        # ── How much space is available on one page (body area) ───────────
        page_body_h = self.h - self.t_margin - self.b_margin
        # Height of one full "chunk" of code lines (fits in remaining page)

        # Language pill height
        pill_h_total = 0
        if lang and lang not in ("", "text", "plain"):
            pill_h_total = 4.5 + 1.5  # pill + gap

        # Chunk lines into page-sized groups so we never pre-draw a rect
        # that is taller than the remaining page — avoiding blank pages.
        # We render chunk by chunk, starting a new page when needed.
        first_chunk = True
        i = 0
        while i < len(rendered_lines):
            # How much vertical space is left on this page?
            avail = self.h - self.b_margin - self.get_y() - 6  # 6px bottom pad

            # First chunk also needs room for the lang pill
            extra = pill_h_total if first_chunk else 0

            # How many lines fit?
            usable = avail - extra - 6  # 6px = top+bottom padding inside block
            lines_this_chunk = max(1, int(usable / line_h))

            # If fewer than 3 lines fit and it's not the last batch, start new page
            if lines_this_chunk < 3 and i < len(rendered_lines) - 1:
                self.add_page()
                avail = self.h - self.b_margin - self.get_y() - 6
                extra = pill_h_total if first_chunk else 0
                usable = avail - extra - 6
                lines_this_chunk = max(1, int(usable / line_h))

            chunk = rendered_lines[i : i + lines_this_chunk]
            i += lines_this_chunk

            self.ln(3)

            # Draw lang pill on very first chunk only
            if first_chunk and lang and lang not in ("", "text", "plain"):
                pill_text = lang.upper()
                self.set_font("Helvetica", "B", 7)
                text_w = self.get_string_width(pill_text) + 4
                x = self.l_margin
                y = self.get_y()
                self.set_fill_color(*_ACCENT)
                self.set_text_color(255, 255, 255)
                self.rect(x, y, text_w, 4.5, "F")
                self.set_xy(x, y + 0.7)
                self.cell(text_w, 3.1, pill_text, align="C")
                self.ln(4.5 + 1.5)
                first_chunk = False

            # Draw background + borders for this chunk
            block_start_y = self.get_y()
            block_h = len(chunk) * line_h + 6

            self.set_fill_color(*_CODE_BG)
            self.rect(code_x, block_start_y, code_w, block_h, "F")
            self.set_fill_color(*_ACCENT)
            self.rect(code_x, block_start_y, 2.5, block_h, "F")
            self.set_draw_color(*_CODE_BORDER)
            self.set_line_width(0.3)
            self.rect(code_x, block_start_y, code_w, block_h, "D")

            # Write lines
            self.set_y(block_start_y + 3)
            self.set_font("Courier", size=8)
            self.set_text_color(50, 50, 80)
            for line in chunk:
                self.set_x(text_x)
                self.cell(code_w - 6, line_h, line)
                self.ln(line_h)

            self.set_y(block_start_y + block_h)
            first_chunk = False

        self.ln(4)
        self._reset()

    def _render_mermaid(self, lines_in: List[str]):
        """Render a Mermaid diagram on its own dedicated page.

        Fixed layout (all coordinates absolute, no fpdf cursor involvement):
          - 5%  of page height  = top gap
          - 10% of page height  = title band
          - 80% of page height  = image box  (image ALWAYS fills this exactly)
          - 5%  of page height  = bottom gap

        auto_page_break is disabled for the whole page so fpdf can never
        inject a second page regardless of image dimensions.
        """
        import struct

        # ── 1. New page, kill auto-break immediately ──────────────────────
        self.add_page()
        self.set_auto_page_break(False)

        # ── 2. Grab & clear pending title ────────────────────────────────
        title_to_draw = self._pending_diagram_title or ""
        self._pending_diagram_title = None

        # ── 3. Fixed-layout geometry (all in mm, absolute) ────────────────
        #
        #   page height  = self.h   (e.g. 297 mm for A4)
        #   usable zone  = full page (header/footer drawn independently)
        #   We carve the full page height into four fixed bands:
        #
        ph = self.h                          # full page height in mm
        gap_top    = ph * 0.05               # 5%
        title_h    = ph * 0.10               # 10%
        img_h      = ph * 0.80               # 80%
        # gap_bot  = ph * 0.05               # 5% (implicit — nothing drawn there)

        y_title = gap_top                    # title band starts here
        y_img   = y_title + title_h          # image box starts here

        avail_w = self.w - self.l_margin - self.r_margin
        img_x   = self.l_margin             # image left edge (centered below)

        # ── 4. Draw title band ────────────────────────────────────────────
        if title_to_draw:
            self.set_fill_color(246, 248, 252)
            self.rect(self.l_margin, y_title, avail_w, title_h, "F")
            # Green left accent stripe
            self.set_fill_color(*_ACCENT)
            self.rect(self.l_margin, y_title, 3, title_h, "F")
            # Title text — vertically centred in the band
            self.set_font("Helvetica", "B", 14)
            self.set_text_color(*_NAVY)
            text_y = y_title + (title_h - 6) / 2   # 6 ≈ font cap height in mm
            self.set_xy(self.l_margin + 8, text_y)
            self.cell(avail_w - 8, 6, _safe(_soft_wrap(title_to_draw)), align="L")
        else:
            # No title — draw a thin accent line as a divider
            self.set_fill_color(*_ACCENT)
            self.rect(self.l_margin, y_title + title_h - 1, avail_w, 1, "F")

        # ── 5. Fetch diagram PNG from Kroki ───────────────────────────────
        diagram_text = "\n".join(lines_in)
        img_data: Optional[bytes] = None
        try:
            data       = diagram_text.encode("utf-8")
            compressed = zlib.compress(data, 9)
            encoded    = base64.urlsafe_b64encode(compressed).decode("ascii")
            url        = f"https://kroki.io/mermaid/png/{encoded}"
            req        = urllib.request.Request(url, headers={"User-Agent": "AutoDocx/1.0"})
            res        = urllib.request.urlopen(req, timeout=12)
            img_data   = res.read()
        except Exception as e:
            print(f"MERMAID RENDER ERROR: {e}")

        # ── 6. Place image — ALWAYS exactly fills the 80% box ────────────
        if img_data:
            # Centre horizontally while filling the full img_h vertically.
            # We pass BOTH w and h explicitly so fpdf scales to fit the box
            # exactly — no auto-sizing, no overflow, no page injection.
            #
            # We keep aspect ratio by fitting inside the box (letterbox):
            img_w_px = img_h_px = None
            try:
                if len(img_data) >= 24 and img_data[:8] == b'\x89PNG\r\n\x1a\n':
                    img_w_px = struct.unpack('>I', img_data[16:20])[0]
                    img_h_px = struct.unpack('>I', img_data[20:24])[0]
            except Exception:
                pass

            if img_w_px and img_h_px and img_w_px > 0 and img_h_px > 0:
                aspect = img_h_px / img_w_px          # h/w ratio
                # Fit inside avail_w × img_h, maintaining aspect
                fit_w = avail_w
                fit_h = fit_w * aspect
                if fit_h > img_h:
                    fit_h = img_h
                    fit_w = fit_h / aspect
                # Hard-clamp: never exceed the box in either dimension
                fit_w = min(fit_w, avail_w)
                fit_h = min(fit_h, img_h)
            else:
                # Unknown dimensions — fill the box completely
                fit_w = avail_w
                fit_h = img_h

            # Centre horizontally inside the image box
            x_img = self.l_margin + (avail_w - fit_w) / 2
            # Centre vertically inside the 80% band
            y_img_placed = y_img + (img_h - fit_h) / 2

            # Place with EXPLICIT x, y, w, h — fpdf will never move the
            # page cursor past the page boundary because auto-break is off.
            self.image(
                io.BytesIO(img_data),
                x=x_img,
                y=y_img_placed,
                w=fit_w,
                h=fit_h,
            )

        else:
            # ── Fallback: tinted box with "not rendered" message ──────────
            self.set_fill_color(*_MERMAID_BG)
            self.set_draw_color(*_ACCENT)
            self.set_line_width(0.4)
            self.rect(self.l_margin, y_img, avail_w, img_h, "FD")
            msg_y = y_img + img_h / 2 - 4
            self.set_font("Helvetica", "I", 10)
            self.set_text_color(*_NAVY)
            self.set_xy(self.l_margin, msg_y)
            self.cell(avail_w, 8,
                      "[Mermaid diagram — view in Markdown report]",
                      align="C")

        # ── 7. Restore auto page break for all subsequent content ─────────
        self.set_auto_page_break(auto=True, margin=20)
        self._reset()

    # ── Main markdown renderer ────────────────────────────────────────────────

    def add_markdown(self, text: str):
        """Parse markdown and render it into the PDF."""
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        lines = text.split("\n")
        in_code = False
        code_lang = ""
        code_lines: List[str] = []
        bq_buffer: List[str] = []  # accumulate consecutive blockquote lines
        idx = 0

        def _flush_bq():
            nonlocal bq_buffer
            if bq_buffer:
                self._info_card(bq_buffer)
                bq_buffer = []

        while idx < len(lines):
            raw = lines[idx]
            stripped = raw.strip()

            # ── fenced code block ──────────────────────────────────────────
            if stripped.startswith("```"):
                _flush_bq()
                if not in_code:
                    in_code = True
                    code_lang = stripped[3:].strip().lower()
                    code_lines = []
                else:
                    try:
                        self._code(code_lines, code_lang)
                    except Exception as e:
                        print(f"CODE BLOCK ERROR: {e}")
                    in_code = False
                    code_lang = ""
                    code_lines = []
                idx += 1
                continue

            if in_code:
                code_lines.append(raw)
                idx += 1
                continue

            # ── blank line ─────────────────────────────────────────────────
            if not stripped:
                _flush_bq()
                self.ln(3)
                idx += 1
                continue

            # ── horizontal rule ────────────────────────────────────────────
            if re.fullmatch(r"[-_*]{3,}", stripped.replace(" ", "")):
                _flush_bq()
                try:
                    self._check_page_break(6)
                    self.ln(2)
                    y = self.get_y()
                    self.set_draw_color(*_RULE)
                    self.set_line_width(0.3)
                    self.line(self.l_margin, y, self.w - self.r_margin, y)
                    self.ln(5)
                except Exception:
                    pass
                idx += 1
                continue

            # ── heading ────────────────────────────────────────────────────
            hm = re.match(r"^(#{1,6})\s+(.+)$", stripped)
            if hm:
                _flush_bq()
                try:
                    level = len(hm.group(1))
                    title = _strip_md(hm.group(2))

                    # Special handling: if this H3 heading is immediately
                    # followed (within the next few lines) by a mermaid code
                    # fence, store it as pending so _render_mermaid can draw
                    # it on the diagram's own page.  We use a lookahead rather
                    # than a hardcoded name list so any diagram title works.
                    if level == 3:
                        title_lower = title.lower()
                        is_diagram_title = any(
                            kw in title_lower for kw in _DIAGRAM_TITLE_KEYWORDS
                        )
                        if not is_diagram_title:
                            # Also check: is the next non-blank line a mermaid fence?
                            peek = idx + 1
                            while peek < len(lines) and not lines[peek].strip():
                                peek += 1
                            if (
                                peek < len(lines)
                                and lines[peek].strip().startswith("```mermaid")
                            ):
                                is_diagram_title = True
                        if is_diagram_title:
                            # Remember this as the caption for the upcoming diagram
                            # page, but still render the heading here so the section
                            # page is not visually empty when only diagrams follow.
                            self._pending_diagram_title = title

                    if level == 2 and _SECTION_RE.match(title):
                        self.add_page()
                    if level == 1:
                        self._h1(title)
                    elif level == 2:
                        self._h2(title)
                    elif level == 3:
                        self._h3(title)
                    elif level == 4:
                        self._h4(title)
                    else:
                        self._hN(title)
                except Exception as e:
                    print(f"HEADING ERROR: {e}")
                idx += 1
                continue

            # ── table ──────────────────────────────────────────────────────
            if (
                stripped.startswith("|")
                and idx + 1 < len(lines)
                and _is_separator(lines[idx + 1])
            ):
                _flush_bq()
                try:
                    headers = _split_row(stripped)
                    idx += 2
                    data_rows = []
                    while idx < len(lines) and lines[idx].strip().startswith("|"):
                        data_rows.append(_split_row(lines[idx]))
                        idx += 1
                    self._table(headers, data_rows)
                except Exception as e:
                    print(f"TABLE ERROR: {e}")
                continue

            # ── blockquote (accumulate consecutive lines) ──────────────────
            bq = re.match(r"^\s*>\s?(.*)$", raw)
            if bq:
                bq_buffer.append(bq.group(1))
                idx += 1
                continue

            # ── flush bq if non-bq line follows ───────────────────────────
            _flush_bq()

            # ── unordered list ─────────────────────────────────────────────
            ul = re.match(r"^(\s*)[-*+]\s+(.+)$", raw)
            if ul:
                try:
                    self._check_page_break(6)
                    indent = min(len(ul.group(1)), 16)
                    item = ul.group(2)
                    self.set_x(self.l_margin + indent + 2)
                    self.set_font("Helvetica", "B", 14)
                    self.set_text_color(*_ACCENT)
                    self.cell(4, 5.5, "\x95" if False else "-")
                    self.set_font("Helvetica", size=10.5)
                    self.set_text_color(*_BODY)
                    self._write_inline(item, 5.5)
                    self.ln(5.5)
                except Exception as e:
                    print(f"UL ERROR: {e}")
                idx += 1
                continue

            # ── ordered list ───────────────────────────────────────────────
            ol = re.match(r"^(\s*)(\d+)\.\s+(.+)$", raw)
            if ol:
                try:
                    self._check_page_break(6)
                    indent = min(len(ol.group(1)), 16)
                    num = ol.group(2)
                    item = ol.group(3)
                    self.set_x(self.l_margin + indent + 2)
                    self.set_font("Helvetica", "B", 10)
                    self.set_text_color(*_ACCENT_DARK)
                    self.cell(6, 5.5, f"{num}.")
                    self.set_font("Helvetica", size=10.5)
                    self.set_text_color(*_BODY)
                    self._write_inline(item, 5.5)
                    self.ln(5.5)
                except Exception as e:
                    print(f"OL ERROR: {e}")
                idx += 1
                continue

            # ── plain paragraph ────────────────────────────────────────────
            try:
                self._check_page_break(6)
                self.set_font("Helvetica", size=10.5)
                self.set_text_color(*_BODY)
                self._write_inline(stripped, 5.5)
                self.ln(5.5)
            except Exception as e:
                print(f"PARA ERROR: {e}")
            idx += 1

        # flush any remaining blockquote
        _flush_bq()


# ── Public API ────────────────────────────────────────────────────────────────


def markdown_to_pdf_bytes(markdown_text: str, title: Optional[str] = None) -> bytes:
    """Convert a markdown string to PDF bytes."""

    def _to_bytes(raw) -> bytes:
        data = (
            bytes(raw)
            if isinstance(raw, (bytes, bytearray))
            else str(raw).encode("latin-1", errors="ignore")
        )
        if not data.startswith(b"%PDF"):
            raise ValueError("Not a valid PDF stream")
        return data

    try:
        pdf = MarkdownPDF()
        pdf.set_margins(left=20, top=20, right=20)

        # Extract repo name and generated_at from metadata block in the markdown
        repo_name = ""
        generated_at = datetime.now().strftime("%Y-%m-%d %H:%M")
        meta_repo = re.search(r"\*\*Repository:\*\*\s*`([^`]+)`", markdown_text)
        meta_date = re.search(r"\*\*Generated:\*\*\s*([^\n|]+)", markdown_text)
        meta_engine = re.search(r"\*\*Engine:\*\*\s*([^\n]+)", markdown_text)
        if meta_repo:
            repo_name = meta_repo.group(1).strip()
        if meta_date:
            generated_at = meta_date.group(1).strip()

        display_title = title or (
            f"{repo_name} — Documentation" if repo_name else "Project Documentation"
        )
        subtitle = (
            meta_engine.group(1).strip()
            if meta_engine
            else "AutoDocx Multi-Agent Engine"
        )

        pdf.report_title = _safe(display_title)[:80]
        pdf.set_title(display_title)

        # Start directly with the documentation content — no separate cover
        # sheet. The metadata card at the top of the markdown serves as the
        # visual header, so we just add a normal page and render the markdown.
        pdf.add_page()
        pdf.add_markdown(markdown_text)

        return _to_bytes(pdf.output())

    except Exception as e:
        import traceback

        print(f"PDF GENERATION CRASHED: {e}")
        traceback.print_exc()

        # Ultra-safe plain-text fallback
        safe = "".join(
            ch if (ch == "\n" or 0x20 <= ord(ch) <= 0x7E) else " "
            for ch in markdown_text
        )
        fb = FPDF()
        fb.set_auto_page_break(auto=True, margin=15)
        fb.set_margins(15, 15, 15)
        fb.add_page()
        fb.set_font("Helvetica", size=10)
        if title:
            fb.set_font("Helvetica", "B", 13)
            fb.cell(0, 8, _safe(title)[:80])
            fb.ln(10)
            fb.set_font("Helvetica", size=10)
        for line in safe.splitlines()[:500]:
            fb.multi_cell(0, 5, _safe(line)[:120])
        return _to_bytes(fb.output())