# File: app/main.py
"""
Streamlit entry point for AutoDocx.
Single-page layout without sidebar navigation.

AutoDocx is an intelligent code documentation generator that helps bridge the gap
between developers and documentation in fast-paced MNC environments.
"""

import streamlit as st
from pathlib import Path

# Page configuration
st.set_page_config(
    page_title="AutoDocx - Intelligent Documentation Generator",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="collapsed"
)

#
# Minimal, clean styling (lightweight – no clutter)
#
st.markdown(
    """
    <style>
    body {
        background-color: #f7f8fa;
    }
    .hero {
        text-align: center;
        padding: 1.5rem 0 1rem 0;
    }
    .hero h1 {
        margin-bottom: 0.2rem;
    }
    .muted {
        color: #6b7280;
        font-size: 0.95rem;
    }
    .card {
        background: #ffffff;
        border: 1px solid #e5e7eb;
        border-radius: 10px;
        padding: 1rem 1.25rem;
        box-shadow: 0 2px 6px rgba(15, 23, 42, 0.06);
    }
    .pill {
        display: inline-block;
        padding: 0.18rem 0.7rem;
        border-radius: 999px;
        background: #eef2ff;
        color: #3730a3;
        font-size: 0.8rem;
        margin-right: 0.35rem;
        margin-bottom: 0.35rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# Hero
st.markdown('<div class="hero">', unsafe_allow_html=True)
st.title("📚 AutoDocx")
st.markdown(
    '<p class="muted">Generate clean, structured documentation from any repository in minutes.</p>',
    unsafe_allow_html=True,
)
st.markdown("</div>", unsafe_allow_html=True)

# Quick value cards
st.subheader("Why teams use AutoDocx")
c1, c2, c3 = st.columns(3)
with c1:
    st.markdown(
        """
        <div class="card">
            <div class="pill">Multi-language</div>
            <h5>Repository analysis</h5>
            <p class="muted">Upload a ZIP, safely extract, and preview structure instantly.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
with c2:
    st.markdown(
        """
        <div class="card">
            <div class="pill">AST parsing</div>
            <h5>Deep code insights</h5>
            <p class="muted">Detect functions, classes, imports, and languages with sensible limits.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
with c3:
    st.markdown(
        """
        <div class="card">
            <div class="pill">Markdown & PDF</div>
            <h5>Instant documentation</h5>
            <p class="muted">Structured reports offline, or richer AI-powered docs when you have an API key.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

st.markdown("### Get started")
st.markdown(
    """
    <div class="card">
        <strong>Steps:</strong> Upload ZIP → Analyze → Generate docs (Markdown & PDF)  
        <span class="muted">Keep it simple: everything you need is below.</span>
    </div>
    """,
    unsafe_allow_html=True,
)

# Main workflow (upload & docs)
from pages import _1_upload as upload_page
upload_page.show()

# Footer
st.markdown("---")
col1, col2, col3 = st.columns(3)
with col1:
    st.caption("**AutoDocx** v1.0")
with col2:
    st.caption("Built with ❤️ using Streamlit")
with col3:
    st.caption("© 2025 AutoDocx")
