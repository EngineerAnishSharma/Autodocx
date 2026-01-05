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

# Custom CSS for better styling
st.markdown("""
    <style>
    .main-header {
        text-align: center;
        padding: 2rem 0;
    }
    .feature-box {
        padding: 1rem;
        border-radius: 0.5rem;
        background-color: #f0f2f6;
        margin: 0.5rem 0;
    }
    </style>
""", unsafe_allow_html=True)

# Header
st.markdown('<div class="main-header">', unsafe_allow_html=True)
st.title("📚 AutoDocx — Intelligent Code Documentation Generator")
st.caption("**Bridging the gap between developers and documentation in fast-paced MNC environments**")
st.markdown('</div>', unsafe_allow_html=True)

# Features section
with st.expander("✨ What AutoDocx Does", expanded=False):
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown("""
        **📦 Repository Analysis**
        - Upload ZIP files from GitHub/Bitbucket
        - Automatic code structure detection
        - Multi-language support
        """)
    with col2:
        st.markdown("""
        **🔍 Intelligent Parsing**
        - AST-based code analysis
        - Function and class extraction
        - Dependency detection
        """)
    with col3:
        st.markdown("""
        **📝 Documentation Generation**
        - Structured reports
        - AI-powered documentation (optional)
        - Multiple export formats
        """)

# Import and show Upload Page directly
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
