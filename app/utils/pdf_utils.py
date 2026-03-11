"""
PDF utilities for AutoDocx.
Converts Markdown to a styled PDF using fpdf2.
Properly renders headings, bold/italic, tables, bullets, code blocks.
"""

import re
from typing import Optional
from fpdf import FPDF
from datetime import datetime
import base64
import zlib
import urllib.request
import io


# ---------------------------------------------------------------------------
# Text helpers
# ---------------------------------------------------------------------------


def _safe(text: str) -> str:
    """Keep only printable Latin-1 characters (0x20-0xFF excluding 0x7F)."""
    return "".join(
        ch if (0x20 <= ord(ch) <= 0x7E) or (0xA0 <= ord(ch) <= 0xFF) else " "
        for ch in str(text)
    )


def _soft_wrap(text: str, n: int = 70) -> str:
    """Break very long unbreakable tokens so fpdf2 can wrap them."""
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
    """Return plain text — strip all common inline markdown markers."""
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


def _inline_segments(text: str):
    """
    Split a markdown inline string into (bold, italic, plain_text) tuples.
    Used to render **bold** and *italic* with actual font styles.
    """
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
        elif raw.startswith("*") or raw.startswith("_"):
            segments.append((False, True, _safe(_soft_wrap(raw[1:-1]))))
        elif raw.startswith("`"):
            segments.append((False, False, _safe(_soft_wrap(raw[1:-1]))))
        pos = m.end()
    if pos < len(text):
        chunk = _safe(_soft_wrap(text[pos:]))
        if chunk.strip():
            segments.append((False, False, chunk))
    if not segments:
        segments = [(False, False, _safe(_soft_wrap(text)))]
    return segments


def _is_separator(line: str) -> bool:
    """True if the line is a markdown table separator like |---|:---|."""
    s = line.strip()
    return bool(s) and "|" in s and bool(re.fullmatch(r"[\s|:\-]+", s))


def _split_row(row: str):
    return [_strip_md(c.strip()) for c in row.strip().strip("|").split("|")]


# ---------------------------------------------------------------------------
# PDF class
# ---------------------------------------------------------------------------


class MarkdownPDF(FPDF):
    NAVY = (30, 58, 138)
    LIGHT_BLUE = (219, 234, 254)
    CODE_BG = (245, 245, 245)
    MERMAID_BG = (230, 240, 255)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.report_title = ""
        self.set_auto_page_break(auto=True, margin=18)
        self.set_margins(left=18, top=18, right=18)
        self.add_page()
        self.set_font("Helvetica", size=11)

    def header(self):
        if self.page_no() == 1:
            return
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(130, 130, 130)
        title = (
            _safe(self.report_title)[:90] if self.report_title else "AutoDocx Report"
        )
        self.cell(0, 6, title, align="L")
        self.ln(6)
        self.set_draw_color(200, 200, 200)
        self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())
        self.ln(2)
        self.set_text_color(0, 0, 0)

    def footer(self):
        self.set_y(-12)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(130, 130, 130)
        self.cell(0, 6, f"Page {self.page_no()}", align="C")
        self.set_text_color(0, 0, 0)

    def _reset(self, size=11):
        self.set_font("Helvetica", size=size)
        self.set_text_color(0, 0, 0)

    def _write_inline(self, text: str, lh: float = 5.5):
        """Write text honouring **bold** and *italic* markers."""
        for bold, italic, chunk in _inline_segments(text):
            style = ("B" if bold else "") + ("I" if italic else "")
            self.set_font("Helvetica", style, 11)
            if chunk:
                self.write(lh, chunk)
        self._reset()

    # ---- headings --------------------------------------------------------

    def _h1(self, title: str):
        self.ln(3)
        self.set_fill_color(*self.NAVY)
        self.set_text_color(255, 255, 255)
        self.set_font("Helvetica", "B", 16)
        self.multi_cell(0, 10, _safe(_soft_wrap(title)), fill=True, align="L")
        self.ln(2)
        self._reset()

    def _h2(self, title: str):
        self.ln(2)
        self.set_fill_color(*self.LIGHT_BLUE)
        self.set_text_color(*self.NAVY)
        self.set_font("Helvetica", "B", 13)
        self.multi_cell(0, 8, _safe(_soft_wrap(title)), fill=True, align="L")
        self.ln(1)
        self._reset()

    def _h3(self, title: str):
        self.ln(2)
        self.set_text_color(*self.NAVY)
        self.set_font("Helvetica", "B", 12)
        self.multi_cell(0, 7, _safe(_soft_wrap(title)))
        y = self.get_y()
        self.set_draw_color(*self.NAVY)
        self.line(self.l_margin, y, self.w - self.r_margin, y)
        self.ln(2)
        self._reset()

    def _h4(self, title: str):
        self.ln(1)
        self.set_font("Helvetica", "B", 11)
        self.set_text_color(50, 50, 50)
        self.multi_cell(0, 6, _safe(_soft_wrap(title)))
        self.ln(1)
        self._reset()

    def _hN(self, title: str):
        self.ln(1)
        self.set_font("Helvetica", "B", 10)
        self.multi_cell(0, 5.5, _safe(_soft_wrap(title)))
        self._reset()

    # ---- table -----------------------------------------------------------

    def _table(self, headers, rows):
        if not headers:
            return
        col_count = max(len(headers), max((len(r) for r in rows), default=0))
        if col_count == 0:
            return

        self.ln(2)
        try:
            with self.table(text_align="LEFT") as ftable:
                # header row
                self.set_font("Helvetica", "B", 10)
                self.set_fill_color(*self.NAVY)
                self.set_text_color(255, 255, 255)
                header_row = ftable.row()
                for i in range(col_count):
                    v = _safe(headers[i]) if i < len(headers) else ""
                    header_row.cell(v)

                # data rows
                self.set_font("Helvetica", size=9)
                self.set_text_color(0, 0, 0)
                for idx, row in enumerate(rows):
                    data_row = ftable.row()
                    for i in range(col_count):
                        v = _safe(row[i]) if i < len(row) else ""
                        data_row.cell(v)
        except Exception as e:
            print(f"TABLE ERROR: {e}")
        self.ln(3)
        self._reset()

    # ---- code block ------------------------------------------------------

    def _code(self, lines_in, lang: str):
        if lang == "mermaid" and lines_in:
            self.ln(2)
            try:
                # Attempt to render mermaid via Kroki API
                data = "\n".join(lines_in).encode("utf-8")
                compressed = zlib.compress(data, 9)
                encoded = base64.urlsafe_b64encode(compressed).decode("ascii")
                url = f"https://kroki.io/mermaid/png/{encoded}"

                req = urllib.request.Request(
                    url, headers={"User-Agent": "AutoDocx/1.0"}
                )
                res = urllib.request.urlopen(req, timeout=10)
                img_data = res.read()

                avail_w = self.w - self.l_margin - self.r_margin
                self.image(io.BytesIO(img_data), w=avail_w)
            except Exception as e:
                print(f"MERMAID ERROR: {e}")
                self.set_fill_color(*self.MERMAID_BG)
                self.set_text_color(*self.NAVY)
                self.set_font("Helvetica", "I", 10)
                self.multi_cell(
                    0,
                    7,
                    "[ Diagram (Mermaid) - Failed to load from Kroki API. Open Markdown to view. ]",
                    fill=True,
                    align="C",
                )
            self.ln(2)
            self._reset()
            return

        self.ln(2)
        self.set_fill_color(*self.CODE_BG)
        self.set_font("Courier", size=8)
        self.set_text_color(30, 30, 30)
        for raw_line in lines_in:
            safe_line = _safe(raw_line.rstrip())
            # chunk very long lines
            while len(safe_line) > 95:
                chunk, safe_line = safe_line[:95], safe_line[95:]
                if self.get_y() + 4.5 > self.h - self.b_margin:
                    self.add_page()
                self.multi_cell(0, 4.5, chunk, fill=True, border=0)
            if self.get_y() + 4.5 > self.h - self.b_margin:
                self.add_page()
            self.multi_cell(0, 4.5, safe_line, fill=True, border=0)
        self.ln(2)
        self._reset()

    # ---- main renderer ---------------------------------------------------

    def add_markdown(self, text: str):
        """Parse markdown and render it into the PDF."""
        # normalise line endings
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        lines = text.split("\n")
        in_code = False
        code_lang = ""
        code_lines = []
        idx = 0

        while idx < len(lines):
            raw = lines[idx]
            stripped = raw.strip()

            # ---- fenced code block ---
            if stripped.startswith("```"):
                if not in_code:
                    in_code = True
                    code_lang = stripped[3:].strip().lower()
                    code_lines = []
                else:
                    try:
                        self._code(code_lines, code_lang)
                    except Exception:
                        pass
                    in_code = False
                    code_lang = ""
                    code_lines = []
                idx += 1
                continue

            if in_code:
                code_lines.append(raw)
                idx += 1
                continue

            # ---- blank line ---
            if not stripped:
                self.ln(3)
                idx += 1
                continue

            # ---- heading ---
            hm = re.match(r"^(#{1,6})\s+(.+)$", stripped)
            if hm:
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
                except Exception:
                    pass
                idx += 1
                continue

            # ---- horizontal rule ---
            if re.fullmatch(r"[-_*]{3,}", stripped.replace(" ", "")):
                try:
                    y = self.get_y()
                    self.set_draw_color(180, 180, 180)
                    self.line(self.l_margin, y, self.w - self.r_margin, y)
                    self.ln(4)
                except Exception:
                    pass
                idx += 1
                continue

            # ---- table ---
            if (
                stripped.startswith("|")
                and idx + 1 < len(lines)
                and _is_separator(lines[idx + 1])
            ):
                try:
                    headers = _split_row(stripped)
                    idx += 2
                    data_rows = []
                    while idx < len(lines) and lines[idx].strip().startswith("|"):
                        data_rows.append(_split_row(lines[idx]))
                        idx += 1
                    self._table(headers, data_rows)
                except Exception:
                    pass
                continue

            # ---- unordered list ---
            ul = re.match(r"^(\s*)[-*+]\s+(.+)$", raw)
            if ul:
                try:
                    indent = min(len(ul.group(1)), 16)
                    item = ul.group(2)
                    if self.get_y() + 5.5 > self.h - self.b_margin:
                        self.add_page()
                    # Use hyphen - safe in all Latin-1 fonts
                    self.set_x(self.l_margin + indent)
                    self.set_font("Helvetica", "B", 11)
                    self.cell(5, 5.5, "-")
                    self.set_font("Helvetica", size=11)
                    self._write_inline(item, 5.5)
                    self.ln(5.5)
                except Exception:
                    pass
                idx += 1
                continue

            # ---- ordered list ---
            ol = re.match(r"^(\s*)(\d+)\.\s+(.+)$", raw)
            if ol:
                try:
                    indent = min(len(ol.group(1)), 16)
                    num = ol.group(2)
                    item = ol.group(3)
                    if self.get_y() + 5.5 > self.h - self.b_margin:
                        self.add_page()
                    self.set_x(self.l_margin + indent)
                    self.set_font("Helvetica", "B", 11)
                    self.cell(7, 5.5, f"{num}.")
                    self.set_font("Helvetica", size=11)
                    self._write_inline(item, 5.5)
                    self.ln(5.5)
                except Exception:
                    pass
                idx += 1
                continue

            # ---- blockquote ---
            bq = re.match(r"^\s*>\s?(.*)$", raw)
            if bq:
                try:
                    self.set_fill_color(240, 244, 255)
                    self.set_text_color(60, 60, 60)
                    self.set_font("Helvetica", "I", 10)
                    self.set_x(self.l_margin + 4)
                    self.multi_cell(
                        0, 5.5, _safe(_soft_wrap(_strip_md(bq.group(1)))), fill=True
                    )
                    self._reset()
                except Exception:
                    pass
                idx += 1
                continue

            # ---- plain paragraph ---
            try:
                if self.get_y() + 6 > self.h - self.b_margin:
                    self.add_page()
                self._write_inline(stripped, 5.5)
                self.ln(5.5)
            except Exception:
                pass
            idx += 1


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def markdown_to_pdf_bytes(markdown_text: str, title: Optional[str] = None) -> bytes:
    """Convert markdown string to PDF bytes."""

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
        if title:
            pdf.report_title = title
            pdf.set_title(title)
            # title banner
            pdf.set_fill_color(30, 58, 138)
            pdf.set_text_color(255, 255, 255)
            pdf.set_font("Helvetica", "B", 16)
            pdf.multi_cell(0, 10, _safe(title), fill=True, align="C")
            pdf.ln(2)
            pdf.set_font("Helvetica", "I", 9)
            pdf.set_text_color(100, 100, 100)
            pdf.cell(
                0,
                6,
                f"Generated by AutoDocx  |  {datetime.now().strftime('%Y-%m-%d %H:%M')}",
                align="C",
            )
            pdf.ln(8)
            pdf.set_text_color(0, 0, 0)

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
