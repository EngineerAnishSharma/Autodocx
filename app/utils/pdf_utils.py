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


# ── PDF class ─────────────────────────────────────────────────────────────────


class MarkdownPDF(FPDF):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.report_title = ""
        self.report_subtitle = ""
        self.set_auto_page_break(auto=True, margin=20)
        self.set_margins(left=20, top=20, right=20)
        self._in_cover = False

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
            self.multi_cell(0, 7, _safe(subtitle), align="C")

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
        self._check_page_break(20)
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
            # badge
            badge_w = 7
            self.set_fill_color(*_NAVY)
            self.rect(text_x, bar_y, badge_w, bar_h, "F")
            self.set_xy(text_x, bar_y)
            self.set_font("Helvetica", "B", 9)
            self.set_text_color(255, 255, 255)
            self.cell(badge_w, bar_h, _safe(num), align="C")
            # heading text
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
        """H3: underlined with accent colour."""
        self._check_page_break(14)
        self.ln(3)
        self.set_font("Helvetica", "B", 11)
        self.set_text_color(*_NAVY)
        self.multi_cell(0, 6.5, _safe(_soft_wrap(title)))
        y = self.get_y()
        self.set_draw_color(*_ACCENT)
        self.set_line_width(0.5)
        self.line(self.l_margin, y, self.l_margin + 60, y)
        self.set_line_width(0.2)
        self.ln(3)
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

        # Measure total height
        total_h = padding + line_h * len(lines_text) + padding

        # Draw tinted background
        self.set_fill_color(*_BQ_BG)
        self.rect(card_x, card_y, card_w, total_h, "F")

        # Draw left bar
        self.set_fill_color(*_BQ_BAR)
        self.rect(card_x, card_y, 3, total_h, "F")

        # Draw border
        self.set_draw_color(*_ACCENT)
        self.set_line_width(0.3)
        self.rect(card_x, card_y, card_w, total_h, "D")

        # Write lines
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

        # Calculate column widths — give more room to longer columns
        usable_w = self.w - self.l_margin - self.r_margin

        # Estimate content width per column from headers + first 5 rows
        sample = [headers] + rows[:5]
        col_lens = [0] * col_count
        for r in sample:
            for i, cell in enumerate(r):
                if i < col_count:
                    col_lens[i] = max(col_lens[i], len(_safe(cell)))
        total_len = sum(col_lens) or 1
        col_widths = [max(14, (cl / total_len) * usable_w) for cl in col_lens]
        # Normalise so they sum to usable_w
        scale = usable_w / sum(col_widths)
        col_widths = [cw * scale for cw in col_widths]

        line_h = 6.5
        head_h = 7.5

        # Header row
        self.set_fill_color(*_TABLE_HEAD)
        self.set_text_color(255, 255, 255)
        self.set_font("Helvetica", "B", 9)
        x_start = self.l_margin
        for i in range(col_count):
            hdr = _safe(headers[i]) if i < len(headers) else ""
            self.set_xy(x_start + sum(col_widths[:i]), self.get_y())
            self.cell(col_widths[i], head_h, hdr, border=1, fill=True, align="C")
        self.ln(head_h)

        # Data rows
        self.set_font("Helvetica", size=8.5)
        for row_idx, row in enumerate(rows):
            fill_color = _TABLE_ALT if row_idx % 2 == 0 else _TABLE_EVEN
            self.set_fill_color(*fill_color)
            self.set_text_color(*_BODY)
            row_y = self.get_y()

            # Estimate row height (multi_cell wrapping)
            row_h = line_h
            for i in range(col_count):
                cell_val = _safe(row[i]) if i < len(row) else ""
                # fpdf2 char width approximation: ~2.0 mm per char at size 8.5
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
                # Reset y to row_y after each multi_cell so columns stay aligned
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

        self._check_page_break(12)
        self.ln(3)

        # Language label
        if lang and lang not in ("", "text", "plain"):
            self.set_font("Helvetica", "B", 7.5)
            self.set_text_color(*_ACCENT_DARK)
            self.cell(0, 5, lang.upper(), align="L")
            self.ln(5)

        # Background rect — compute height first
        line_h = 4.5
        # Estimate: render then measure
        code_x = self.l_margin
        code_w = self.w - self.l_margin - self.r_margin
        block_start_y = self.get_y()

        # Left accent bar
        self.set_fill_color(*_CODE_BG)
        # We'll draw the rect after we know the height; for now just track y

        self.set_font("Courier", size=8)
        self.set_text_color(50, 50, 80)

        text_x = code_x + 5  # indent inside the block
        self.set_x(text_x)

        rendered_lines = []
        for raw_line in lines_in:
            safe_line = _safe(raw_line.rstrip())
            # hard-wrap very long lines at 90 chars
            while len(safe_line) > 90:
                rendered_lines.append(safe_line[:90])
                safe_line = "  " + safe_line[90:]
            rendered_lines.append(safe_line)

        # Compute block height
        block_h = len(rendered_lines) * line_h + 6  # 3px padding top + bottom

        # Draw background
        self.set_fill_color(*_CODE_BG)
        self.rect(code_x, block_start_y, code_w, block_h, "F")

        # Draw left accent bar
        self.set_fill_color(*_ACCENT)
        self.rect(code_x, block_start_y, 2.5, block_h, "F")

        # Draw border
        self.set_draw_color(*_CODE_BORDER)
        self.set_line_width(0.3)
        self.rect(code_x, block_start_y, code_w, block_h, "D")

        # Write lines
        self.set_y(block_start_y + 3)
        self.set_font("Courier", size=8)
        self.set_text_color(50, 50, 80)
        for line in rendered_lines:
            self._check_page_break(line_h + 2)
            self.set_x(text_x)
            self.cell(code_w - 6, line_h, line)
            self.ln(line_h)

        self.set_y(block_start_y + block_h)
        self.ln(4)
        self._reset()

    def _render_mermaid(self, lines_in: List[str]):
        """Render a Mermaid diagram via Kroki API with constrained sizing."""
        self._check_page_break(60)
        self.ln(3)

        diagram_text = "\n".join(lines_in)
        avail_w = self.w - self.l_margin - self.r_margin
        # Constrain diagram width: max 130mm, centered
        display_w = min(130, avail_w * 0.80)
        x_offset = self.l_margin + (avail_w - display_w) / 2

        rendered = False
        try:
            data = diagram_text.encode("utf-8")
            compressed = zlib.compress(data, 9)
            encoded = base64.urlsafe_b64encode(compressed).decode("ascii")
            url = f"https://kroki.io/mermaid/png/{encoded}"
            req = urllib.request.Request(url, headers={"User-Agent": "AutoDocx/1.0"})
            res = urllib.request.urlopen(req, timeout=12)
            img_data = res.read()

            img_start_y = self.get_y()
            self.image(io.BytesIO(img_data), x=x_offset, w=display_w)
            rendered = True

            # Caption below diagram
            self.ln(2)
            self.set_font("Helvetica", "I", 8)
            self.set_text_color(*_SUBTEXT)
            self.cell(0, 5, "Figure: System Diagram (rendered via Mermaid)", align="C")
            self.ln(5)

        except Exception as e:
            print(f"MERMAID RENDER ERROR: {e}")

        if not rendered:
            # Fallback: tinted box with source code
            self.set_fill_color(*_MERMAID_BG)
            self.set_draw_color(*_ACCENT)
            self.set_line_width(0.4)
            box_h = min(len(lines_in) * 4.5 + 14, 60)
            self.rect(self.l_margin, self.get_y(), avail_w, box_h, "FD")
            self.ln(4)
            self.set_font("Helvetica", "I", 9)
            self.set_text_color(*_NAVY)
            self.cell(0, 6, "[ Diagram — open the Markdown file to view ]", align="C")
            self.ln(8)
            # Show source in a compact code-like listing
            self.set_font("Courier", size=7.5)
            self.set_text_color(*_SUBTEXT)
            for line in lines_in[:20]:
                self.set_x(self.l_margin + 4)
                self.cell(avail_w - 8, 4, _safe(line[:100]))
                self.ln(4)
            if len(lines_in) > 20:
                self.set_x(self.l_margin + 4)
                self.cell(avail_w - 8, 4, f"... ({len(lines_in)-20} more lines)")
                self.ln(4)

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
                    # Green bullet dot
                    self.set_font("Helvetica", "B", 14)
                    self.set_text_color(*_ACCENT)
                    self.cell(4, 5.5, "\x95" if False else "-")  # bullet char
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

        # Cover page
        pdf.make_cover(display_title, subtitle, generated_at)

        # Strip the metadata blockquote from the markdown before rendering
        # (it's already shown on the cover) — keep it if you prefer to show both
        # md_clean = re.sub(r"(^|\n)(> .+\n?)+", "\n", markdown_text)
        # For now render as-is (the info card style will make it look nice)
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
