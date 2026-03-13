# File: app/main.py
"""
Streamlit entry point for AutoDocx.
"""

import streamlit as st
from pathlib import Path

st.set_page_config(
    page_title="AutoDocx - Intelligent Documentation Generator",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800&family=DM+Sans:ital,wght@0,300;0,400;0,500;0,700;1,400&display=swap');

    :root {
        --bg: #080d16;
        --surface: #0e1420;
        --surface2: #141c2e;
        --surface3: #1a2438;
        --border: rgba(255,255,255,0.07);
        --border-accent: rgba(16,185,129,0.25);
        --accent: #10b981;
        --accent-dim: rgba(16,185,129,0.12);
        --accent2: #38bdf8;
        --accent2-dim: rgba(56,189,248,0.1);
        --accent3: #a78bfa;
        --text: #f1f5f9;
        --muted: #64748b;
        --muted2: #94a3b8;
    }

    html, body, [class*="st-"] {
        font-family: 'DM Sans', sans-serif;
        color: var(--text);
    }

    .stApp {
        background-color: var(--bg);
        background-image:
            linear-gradient(rgba(255,255,255,0.012) 1px, transparent 1px),
            linear-gradient(90deg, rgba(255,255,255,0.012) 1px, transparent 1px),
            radial-gradient(ellipse 70% 50% at 50% 0%, rgba(16,185,129,0.07) 0%, transparent 55%),
            radial-gradient(ellipse 50% 40% at 90% 90%, rgba(56,189,248,0.04) 0%, transparent 50%);
        background-size: 40px 40px, 40px 40px, 100% 100%, 100% 100%;
    }

    #MainMenu, footer, header { visibility: hidden; }
    .block-container {
        padding-top: 0 !important;
        padding-bottom: 5rem !important;
        max-width: 1080px !important;
    }

    /* ── Hero ── */
    .hero-wrap {
        text-align: center;
        padding: 5rem 1rem 3rem;
    }
    .hero-eyebrow {
        display: inline-flex;
        align-items: center;
        gap: 0.55rem;
        background: var(--accent-dim);
        border: 1px solid var(--border-accent);
        border-radius: 999px;
        padding: 0.38rem 1.1rem;
        font-size: 0.72rem;
        font-family: 'Outfit', sans-serif;
        font-weight: 700;
        color: var(--accent);
        letter-spacing: 0.1em;
        text-transform: uppercase;
        margin-bottom: 1.8rem;
    }
    .hero-eyebrow .dot {
        width: 7px; height: 7px;
        background: var(--accent);
        border-radius: 50%;
        flex-shrink: 0;
        animation: blink 2.2s ease-in-out infinite;
    }
    @keyframes blink {
        0%, 100% { opacity: 1; box-shadow: 0 0 0 0 rgba(16,185,129,0.5); }
        50% { opacity: 0.5; box-shadow: 0 0 0 6px rgba(16,185,129,0); }
    }
    .hero-title {
        font-family: 'Outfit', sans-serif;
        font-size: clamp(3rem, 7vw, 5rem);
        font-weight: 800;
        letter-spacing: -0.04em;
        line-height: 1.0;
        margin: 0 0 1.4rem 0;
        background: linear-gradient(160deg, #ffffff 0%, #c7f7e5 40%, var(--accent) 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
    }
    .hero-sub {
        font-size: 1.08rem;
        color: var(--muted2);
        margin: 0 auto;
        line-height: 1.7;
        font-weight: 400;
    }

    /* ── Section label ── */
    .section-label {
        font-family: 'Outfit', sans-serif;
        font-size: 0.72rem;
        font-weight: 700;
        letter-spacing: 0.18em;
        text-transform: uppercase;
        color: var(--accent);
        margin: 0.5rem 0 1.2rem;
        display: flex;
        align-items: center;
        gap: 0.6rem;
    }
    .section-label::after {
        content: '';
        flex: 1;
        height: 1px;
        background: var(--border);
        max-width: 80px;
    }

    /* ── Step Headers (Global) ── */
    .step-container {
        margin: 2.2rem 0 1rem;
    }
    .step-row {
        display: flex;
        align-items: center;
        gap: 0.85rem;
        margin-bottom: 0.45rem;
    }
    .step-badge {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        min-width: 28px;
        width: 28px;
        height: 28px;
        border-radius: 50%;
        background: linear-gradient(135deg, var(--accent), var(--accent2));
        color: #080d16;
        font-family: 'Outfit', sans-serif;
        font-weight: 800;
        font-size: 0.82rem;
        flex-shrink: 0;
        line-height: 1;
    }
    .step-title {
        font-family: 'Outfit', sans-serif;
        font-size: 1.15rem;
        font-weight: 700;
        color: var(--text);
        margin: 0;
        line-height: 1.3;
    }
    .step-sub {
        font-size: 0.86rem;
        color: var(--muted2);
        margin: 0.25rem 0 0.5rem 2.85rem;
    }
    .section-rule {
        border: none;
        border-top: 1px solid var(--border) !important;
        margin: 2rem 0 0 !important;
        opacity: 0.6;
    }

    /* ── Stats strip ── */
    .stats-strip {
        display: grid;
        grid-template-columns: repeat(4, 1fr);
        background: var(--surface);
        border: 1px solid var(--border);
        border-radius: 20px;
        margin: 2.5rem 0 0;
        overflow: hidden;
        position: relative;
    }
    .stats-strip::before {
        content: '';
        position: absolute;
        top: 0; left: 0; right: 0;
        height: 1px;
        background: linear-gradient(90deg, transparent, var(--accent), var(--accent2), transparent);
    }
    .stat-item {
        text-align: center;
        padding: 2rem 1rem 1.8rem;
        border-right: 1px solid var(--border);
    }
    .stat-item:last-child { border-right: none; }
    .stat-num {
        font-family: 'Outfit', sans-serif;
        font-size: 2rem;
        font-weight: 800;
        color: var(--accent);
        line-height: 1;
        display: block;
    }
    .stat-lbl {
        font-size: 0.72rem;
        color: var(--muted);
        margin-top: 0.5rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.07em;
        display: block;
    }

    /* ── Feature cards ── */
    .cards-grid {
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        gap: 1.5rem;
        margin: 1.5rem 0 3rem;
    }
    .feat-card {
        background: var(--surface);
        border: 1px solid var(--border);
        border-radius: 20px;
        padding: 1.8rem;
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        position: relative;
        overflow: hidden;
    }
    .feat-card:hover {
        border-color: var(--border-accent);
        transform: translateY(-4px);
        background: var(--surface2);
    }
    .feat-icon-wrap {
        width: 44px; height: 44px;
        border-radius: 12px;
        display: flex; align-items: center; justify-content: center;
        font-size: 1.4rem;
        margin-bottom: 1.1rem;
    }
    .feat-icon-wrap.green { background: var(--accent-dim); }
    .feat-icon-wrap.blue  { background: var(--accent2-dim); }
    .feat-icon-wrap.purple{ background: rgba(167,139,250,0.1); }
    .feat-pill {
        display: inline-block;
        padding: 0.18rem 0.7rem;
        border-radius: 999px;
        font-size: 0.66rem;
        font-weight: 800;
        font-family: 'Outfit', sans-serif;
        text-transform: uppercase;
        letter-spacing: 0.06em;
        margin-bottom: 0.7rem;
    }
    .feat-pill.green  { background: var(--accent-dim);  color: var(--accent); }
    .feat-pill.blue   { background: var(--accent2-dim); color: var(--accent2); }
    .feat-pill.purple { background: rgba(167,139,250,0.1); color: var(--accent3); }
    .feat-title {
        font-family: 'Outfit', sans-serif;
        font-size: 1.05rem;
        font-weight: 700;
        color: var(--text);
        margin: 0 0 0.5rem;
        display: block;
    }
    .feat-desc {
        font-size: 0.88rem;
        color: var(--muted2);
        line-height: 1.65;
        margin: 0;
        display: block;
    }

    /* ── Divider ── */
    hr {
        border: none !important;
        border-top: 1px solid var(--border) !important;
        margin: 3.5rem 0 2rem !important;
    }

    /* ── Footer ── */
    .footer-wrap {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 0.5rem 0 1rem;
        flex-wrap: wrap;
        gap: 0.8rem;
    }
    .footer-brand {
        font-family: 'Outfit', sans-serif;
        font-weight: 800;
        font-size: 0.92rem;
        color: var(--text);
    }
    .footer-brand .acc { color: var(--accent); }
    .footer-brand .ver { color: var(--muted); font-weight: 400; font-size: 0.8rem; margin-left: 0.3rem; }
    .footer-center { font-size: 0.8rem; color: var(--muted); }
    .footer-badge {
        background: rgba(167,139,250,0.08);
        border: 1px solid rgba(167,139,250,0.18);
        border-radius: 999px;
        padding: 0.25rem 0.9rem;
        font-size: 0.72rem;
        color: var(--accent3);
        font-family: 'Outfit', sans-serif;
        font-weight: 700;
    }

    /* ── Global Streamlit overrides ── */
    .stButton > button {
        background: var(--accent) !important;
        color: #080d16 !important;
        border: none !important;
        border-radius: 10px !important;
        font-family: 'Outfit', sans-serif !important;
        font-weight: 800 !important;
        font-size: 0.9rem !important;
        padding: 0.65rem 1.8rem !important;
        box-shadow: 0 2px 16px rgba(16,185,129,0.18) !important;
        transition: all 0.2s !important;
    }
    .stButton > button:hover {
        background: #0ea572 !important;
        transform: translateY(-2px) !important;
        box-shadow: 0 6px 24px rgba(16,185,129,0.28) !important;
    }

    [data-testid="stFileUploader"] {
        background: var(--surface) !important;
        border: 1px solid var(--border) !important;
        border-radius: 16px !important;
        padding: 0.75rem !important;
    }
    [data-testid="stFileUploaderDropzone"] {
        background: rgba(255,255,255,0.015) !important;
        border: 1.5px dashed var(--border) !important;
        border-radius: 12px !important;
    }
    [data-testid="stFileUploaderDropzone"] button {
        background: var(--surface2) !important;
        color: var(--text) !important;
        border: 1px solid var(--border) !important;
        border-radius: 8px !important;
    }
    [data-testid="stFileUploaderDropzone"] button span,
    [data-testid="stFileUploaderDropzone"] button p,
    [data-testid="stFileUploaderDropzone"] small,
    [data-testid="stFileUploaderDropzone"] [data-testid="stMarkdownContainer"] p {
        color: var(--text) !important;
    }
    [data-testid="stFileUploaderDropzone"]:hover {
        border-color: var(--border-accent) !important;
    }
    [data-testid="stFileUploaderDropzone"] button:hover {
        background: var(--surface3) !important;
        color: var(--text) !important;
        border-color: var(--border-accent) !important;
    }

    .stTabs [data-baseweb="tab-list"] {
        background: var(--surface) !important;
        border-radius: 12px !important;
        padding: 0.3rem !important;
        border: 1px solid var(--border) !important;
        gap: 0.15rem !important;
    }
    .stTabs [data-baseweb="tab"] {
        border-radius: 9px !important;
        color: var(--muted2) !important;
        font-family: 'Outfit', sans-serif !important;
        font-weight: 600 !important;
        font-size: 0.86rem !important;
        transition: all 0.2s !important;
        padding : 10px;
    }
    .stTabs [aria-selected="true"] {
        background: var(--surface3) !important;
        color: var(--accent) !important;
    }

    .stTextInput > div > div > input,
    .stTextArea > div > div > textarea,
    [data-testid="stNumberInput"] input {
        background: var(--surface) !important;
        border: 1px solid var(--border) !important;
        border-radius: 10px !important;
        color: var(--text) !important;
    }
    [data-testid="stNumberInput"] div[role="button"] {
        background: var(--surface2) !important;
        color: var(--text) !important;
    }
    [data-testid="stNumberInput"] svg {
        color: var(--accent) !important;
        fill: var(--accent) !important;
    }
    ::placeholder {
        color: var(--muted2) !important;
        opacity: 0.7 !important;
    }

    div[data-testid="stSelectbox"] > div > div {
        background: var(--surface) !important;
        border: 1px solid var(--border) !important;
        border-radius: 10px !important;
    }
    div[data-testid="stSelectbox"] [data-testid="stMarkdownContainer"] p {
        color: var(--text) !important;
    }
    /* Fix for dropdown items contrast */
    [data-baseweb="popover"] div, [data-baseweb="popover"] li {
        color: var(--text) !important;
    }

    div[data-testid="metric-container"] {
        background: var(--surface) !important;
        border: 1px solid var(--border) !important;
        border-radius: 14px !important;
        padding: 1rem 1.2rem !important;
    }
    div[data-testid="stMetricValue"] > div {
        font-family: 'Outfit', sans-serif !important;
        font-weight: 800 !important;
        font-size: 1.4rem !important;
        color: var(--accent) !important;
    }
    div[data-testid="stMetricLabel"] > div {
        font-size: 0.72rem !important;
        color: var(--muted) !important;
        text-transform: uppercase;
        letter-spacing: 0.07em;
    }

    div[data-testid="stAlert"] {
        background: var(--surface2) !important;
        border: 1px solid var(--border) !important;
        border-radius: 12px !important;
    }
    div[data-testid="stAlert"] p,
    div[data-testid="stAlert"] span {
        color: var(--text) !important;
    }

    /* ── EXPANDER FIX (global) ── */
    [data-testid="stExpander"] {
        border: 1px solid var(--border) !important;
        border-radius: 10px !important;
        overflow: hidden !important;
        background: var(--surface) !important;
    }
    [data-testid="stExpander"] details {
        background: var(--surface) !important;
    }
    [data-testid="stExpander"] details > summary {
        display: block !important;
        background: var(--surface) !important;
        border-radius: 10px !important;
        color: var(--text) !important;
        padding: 0.75rem 1.2rem !important;
        font-family: 'Outfit', sans-serif !important;
        font-weight: 600 !important;
        font-size: 0.95rem !important;
        cursor: pointer !important;
        list-style: none !important;
        position: relative !important;
    }
    /* Hide the default arrow if it's being problematic or leaking text */
    [data-testid="stExpander"] details > summary [data-testid="stIconMaterial"] {
        display: none !important;
    }
    /* Add a custom arrow via pseudo-element for consistency */
    [data-testid="stExpander"] details > summary::after {
        content: '⌄';
        position: absolute;
        right: 1.2rem;
        top: 50%;
        transform: translateY(-50%);
        font-size: 1.2rem;
        color: var(--muted);
        transition: transform 0.2s;
    }
    [data-testid="stExpander"] details[open] > summary::after {
        transform: translateY(-50%) rotate(180deg);
    }
    [data-testid="stExpander"] details > summary:hover {
        background: var(--surface2) !important;
    }
    [data-testid="stExpander"] details[open] > summary {
        border-radius: 10px 10px 0 0 !important;
        border-bottom: 1px solid var(--border) !important;
    }
    [data-testid="stExpander"] details > summary p,
    [data-testid="stExpander"] details > summary span {
        color: var(--text) !important;
        display: inline !important;
        margin: 0 !important;
    }
    [data-testid="stExpander"] details > div {
        background: #0b1220 !important;
        color: #dbeafe !important;
        padding: 0.75rem 1rem 1rem !important;
    }
    [data-testid="stExpanderDetails"],
    [data-testid="stExpanderDetails"] > div,
    [data-testid="stExpanderDetails"] [data-testid="stVerticalBlock"],
    [data-testid="stExpanderDetails"] [data-testid="stVerticalBlock"] > div {
        background: #0b1220 !important;
        color: #dbeafe !important;
    }
    [data-testid="stExpander"] details > div * {
        color: #dbeafe !important;
    }
    [data-testid="stExpander"] details > div pre,
    [data-testid="stExpander"] details > div code,
    [data-testid="stExpander"] details > div [class*="stCode"],
    [data-testid="stExpander"] details > div [class*="code"] {
        background: #0b1220 !important;
        color: #dbeafe !important;
    }

    /* Keep file-tree/code text readable inside expander content. */
    [data-testid="stExpander"] [data-testid="stCodeBlock"],
    [data-testid="stExpander"] [data-testid="stCodeBlock"] > div,
    [data-testid="stExpander"] [data-testid="stCodeBlock"] pre {
        background: #0b1220 !important;
        border: 1px solid var(--border) !important;
        border-radius: 10px !important;
    }
    [data-testid="stExpander"] [data-testid="stCodeBlock"] code,
    [data-testid="stExpander"] [data-testid="stCodeBlock"] code *,
    [data-testid="stExpander"] [data-testid="stCodeBlock"] span {
        color: #dbeafe !important;
        background: transparent !important;
    }

    /* ── CODE BLOCK dark fix ── */
    [data-testid="stCodeBlock"],
    [data-testid="stCodeBlock"] pre,
    [data-testid="stCodeBlock"] > div {
        background: #060b14 !important;
        border-radius: 10px !important;
    }
    [data-testid="stCodeBlock"] code {
        background: transparent !important;
        color: #cbd5e1 !important;
    }
    [data-testid="stCodeBlock"] * {
        background-color: transparent !important;
    }
    [data-testid="stCodeBlock"] > div:first-child {
        background: #060b14 !important;
        border: 1px solid var(--border) !important;
        border-radius: 10px !important;
    }

    div[data-testid="stNumberInput"] input {
        background: var(--surface) !important;
        border: 1px solid var(--border) !important;
        border-radius: 10px !important;
        color: var(--text) !important;
    }

    div[data-testid="stProgressBar"] > div > div {
        background: linear-gradient(90deg, var(--accent), var(--accent2)) !important;
        border-radius: 999px !important;
    }

    .stDownloadButton > button {
        background: rgba(16,185,129,0.08) !important;
        border: 1px solid rgba(16,185,129,0.25) !important;
        color: var(--accent) !important;
        border-radius: 10px !important;
        font-family: 'Outfit', sans-serif !important;
        font-weight: 700 !important;
        font-size: 0.86rem !important;
        transition: all 0.2s !important;
    }
    .stDownloadButton > button:hover {
        background: rgba(16,185,129,0.14) !important;
        border-color: rgba(16,185,129,0.45) !important;
        transform: translateY(-1px) !important;
    }
    .stDownloadButton > button:disabled { opacity: 0.3 !important; }

    ::-webkit-scrollbar { width: 6px; height: 6px; }
    ::-webkit-scrollbar-track { background: var(--bg); }
    ::-webkit-scrollbar-thumb { background: var(--surface3); border-radius: 999px; }
    ::-webkit-scrollbar-thumb:hover { background: var(--accent); }
    </style>
    """,
    unsafe_allow_html=True,
)

# ── Hero ──────────────────────────────────────────────────────────────────────
st.markdown(
    """
    <div class="hero-wrap">
        <h1 class="hero-title">AutoDocx</h1>
        <p class="hero-sub">
            Generate clean, structured documentation from any repository —
            in minutes, not days.
        </p>
    </div>
    """,
    unsafe_allow_html=True,
)


# ── Feature Cards ─────────────────────────────────────────────────────────────
st.markdown(
    '<p class="section-label">✦ Why teams use AutoDocx</p>',
    unsafe_allow_html=True,
)

st.markdown(
    """
    <div class="cards-grid">
        <div class="feat-card">
            <div class="feat-icon-wrap green">🗂️</div>
            <span class="feat-pill green">Multi-language</span>
            <span class="feat-title">Repository Analysis</span>
            <span class="feat-desc">Upload a ZIP or link a GitHub repo. Safely extract and instantly preview your project structure.</span>
        </div>
        <div class="feat-card">
            <div class="feat-icon-wrap blue">🔬</div>
            <span class="feat-pill blue">AST Parsing</span>
            <span class="feat-title">Deep Code Insights</span>
            <span class="feat-desc">Detect functions, classes, imports, and language patterns with intelligent, sensible limits.</span>
        </div>
        <div class="feat-card">
            <div class="feat-icon-wrap purple">📄</div>
            <span class="feat-pill purple">Markdown & PDF</span>
            <span class="feat-title">Instant Documentation</span>
            <span class="feat-desc">Export clean offline reports, or generate AI-powered docs with rich, structured results.</span>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)


# ── Main workflow ─────────────────────────────────────────────────────────────
st.markdown(
    '<p class="section-label" style="margin-top:0.5rem">✦ Get started</p>',
    unsafe_allow_html=True,
)


from pages import _1_upload as upload_page

upload_page.show()

# ── Footer ────────────────────────────────────────────────────────────────────
st.markdown("<hr>", unsafe_allow_html=True)
st.markdown(
    """
    <div class="footer-wrap">
        <span class="footer-brand">Auto<span class="acc">Docx</span><span class="ver">v1.0</span></span>
        <span class="footer-center">Built with ❤️ using Streamlit</span>
        <span class="footer-badge">© 2025 AutoDocx</span>
    </div>
    """,
    unsafe_allow_html=True,
)
