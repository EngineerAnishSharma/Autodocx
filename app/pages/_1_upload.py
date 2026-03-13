"""
Streamlit Upload & Preprocessing Page for AutoDocx
--------------------------------------------------
"""

import streamlit as st
from pathlib import Path
import time

from components.uploader import handle_uploaded_zip, handle_github_url
from utils.file_utils import list_repo_tree
from utils.ast_parser import parse_repo_ast, parse_repo_ast_structured
from utils.report_builder import build_prompt, generate_llm_report
from utils.pdf_utils import markdown_to_pdf_bytes
from utils.github_utils import check_git_installed, validate_github_url

PAGE_TITLE = "📦 Upload Repository"

_CSS = """
<style>
:root {
    --text-fallback: #0f172a;
    --muted-fallback: #475569;
    --surface-fallback: #ffffff;
    --surface-alt-fallback: #f8fafc;
    --border-fallback: rgba(15, 23, 42, 0.14);
}

/* Keep labels and helper text readable even when global theme variables are unavailable. */
[data-testid="stWidgetLabel"] p,
[data-testid="stWidgetLabel"] span,
[data-testid="stMarkdownContainer"] p,
[data-testid="stMarkdownContainer"] span,
label {
    color: var(--text, var(--text-fallback)) !important;
}

/* Input contrast guard against white-on-white text/background combinations. */
.stTextInput > div > div > input,
.stTextArea > div > div > textarea,
[data-testid="stNumberInput"] input,
[data-testid="stFileUploaderDropzone"] {
    background: var(--surface, var(--surface-fallback)) !important;
    color: var(--text, var(--text-fallback)) !important;
    border: 1px solid var(--border, var(--border-fallback)) !important;
}

.stTextInput > div > div > input::placeholder,
.stTextArea > div > div > textarea::placeholder {
    color: var(--muted2, var(--muted-fallback)) !important;
    opacity: 0.85 !important;
}

[data-baseweb="popover"],
[data-baseweb="popover"] ul,
[role="listbox"] {
    background: var(--surface, var(--surface-fallback)) !important;
}

[data-baseweb="popover"] *,
[role="listbox"] * {
    color: var(--text, var(--text-fallback)) !important;
}

/* ── Result section label ── */
.result-header {
    font-family: 'Outfit', sans-serif;
    font-size: 0.72rem;
    font-weight: 700;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: var(--accent);
    margin: 1.8rem 0 0.8rem;
}

/* ── Empty state ── */
.empty-state {
    text-align: center;
    padding: 4rem 1rem;
    border: 1.5px dashed var(--border);
    border-radius: 16px;
    margin: 1.5rem 0;
    background: rgba(16,185,129,0.02);
}
.empty-state .ei { font-size: 2.8rem; display: block; margin-bottom: 0.8rem; }
.empty-state .et {
    font-family: 'Outfit', sans-serif;
    font-weight: 700;
    font-size: 1.05rem;
    color: var(--muted2, var(--muted-fallback));
    margin-bottom: 0.35rem;
}
.empty-state .eh { font-size: 0.84rem; color: var(--muted, var(--muted-fallback)); }
</style>
"""


def _step(num: str, title: str, sub: str = ""):
    st.markdown(
        f"""
        <div class="step-container">
            <hr class="section-rule"/>
            <div class="step-row">
                <span class="step-badge">{num}</span>
                <p class="step-title">{title}</p>
            </div>
            {"" if not sub else f'<p class="step-sub">{sub}</p>'}
        </div>
        """,
        unsafe_allow_html=True,
    )


def show():
    st.markdown(_CSS, unsafe_allow_html=True)

    _step("1", "Upload repository", "Choose a ZIP file or clone directly from GitHub.")

    tab1, tab2 = st.tabs(["📁 Upload ZIP", "🔗 GitHub URL"])

    uploads_dir = Path("app/data/uploads")
    uploads_dir.mkdir(parents=True, exist_ok=True)

    extract_path = None
    repo_name = None

    if "uploaded_repo_path" in st.session_state:
        extract_path = Path(st.session_state["uploaded_repo_path"])
        if extract_path.exists():
            repo_name = st.session_state.get("uploaded_repo_name", extract_path.name)

    with tab1:
        uploaded_file = st.file_uploader(
            "Drop your repository ZIP here",
            type=["zip"],
            accept_multiple_files=False,
            help="Upload your GitHub repo exported as a ZIP file.",
        )

        if uploaded_file:
            file_id = f"{uploaded_file.name}_{uploaded_file.size}"
            last_processed = st.session_state.get("last_processed_zip_file")

            if last_processed != file_id:
                try:
                    with st.spinner("Extracting repository…"):
                        temp_repo_name, temp_extract_path = handle_uploaded_zip(
                            uploaded_file, uploads_dir
                        )
                    temp_extract_path = Path(temp_extract_path)
                    st.session_state["uploaded_repo_path"] = str(temp_extract_path)
                    st.session_state["uploaded_repo_name"] = temp_repo_name
                    st.session_state["last_processed_zip_file"] = file_id
                    st.success(f"Extracted **{temp_repo_name}** successfully.")
                    time.sleep(0.8)
                    st.rerun()
                except Exception as e:
                    st.error(f"Error processing upload: {e}")
            else:
                st.success(
                    f"Loaded: **{st.session_state.get('uploaded_repo_name', 'Unknown')}**"
                )

    with tab2:
        git_installed, git_info = check_git_installed()

        if not git_installed:
            st.error(f"⚠️ {git_info}")
            st.info("Git is required. Install from https://git-scm.com/")
        else:
            st.success(f"✓ {git_info}")

        col1, col2 = st.columns([4, 1])
        with col1:
            github_url = st.text_input(
                "GitHub Repository URL",
                placeholder="https://github.com/username/repository",
                help="Full GitHub URL",
                key="github_url_input",
            )
        with col2:
            st.write("")
            st.write("")
            clone_button = st.button(
                "Clone",
                type="primary",
                disabled=not git_installed,
                use_container_width=True,
            )

        with st.expander("Advanced Options", expanded=False):
            branch_name = st.text_input(
                "Branch (optional)",
                placeholder="main",
                help="Leave empty to use the default branch.",
            )

        if clone_button and github_url:
            is_valid, error_msg = validate_github_url(github_url)
            if not is_valid:
                st.error(f"❌ {error_msg}")
            else:
                with st.spinner("Cloning repository… this may take a moment."):
                    try:
                        branch = (
                            branch_name.strip()
                            if branch_name and branch_name.strip()
                            else None
                        )
                        temp_repo_name, temp_extract_path = handle_github_url(
                            github_url, uploads_dir, branch=branch
                        )
                        temp_extract_path = Path(temp_extract_path)
                        st.session_state["uploaded_repo_path"] = str(temp_extract_path)
                        st.session_state["uploaded_repo_name"] = temp_repo_name
                        st.success(f"✅ Cloned **{temp_repo_name}** successfully.")
                        time.sleep(0.8)
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ Clone failed: {e}")
                        if "git" in str(e).lower():
                            st.info(
                                "Make sure Git is installed and accessible from the command line."
                            )

    # ── Loaded repo banner ────────────────────────────────────────────────────
    if extract_path and extract_path.exists():
        col_info, col_reset = st.columns([5, 1])
        with col_info:
            st.markdown(
                f"""
                <div class="repo-banner">
                    <span>📦</span>
                    <span>Loaded repository:</span>
                    <span class="rname">{repo_name}</span>
                </div>
                """,
                unsafe_allow_html=True,
            )
        with col_reset:
            st.write("")
            if st.button("↺ Reset", use_container_width=True):
                for key in [
                    "uploaded_repo_path",
                    "uploaded_repo_name",
                    "parsed_results",
                    "parsed_structured",
                    "last_processed_zip_file",
                    "report_md",
                    "pdf_bytes",
                ]:
                    st.session_state.pop(key, None)
                st.rerun()

        with st.expander("📂 Repository structure", expanded=False):
            tree = list_repo_tree(extract_path, max_entries=300)
            st.code("\n".join(tree), language="bash")

        # ── Step 2 ────────────────────────────────────────────────────────────
        _step("2", "Explore code files", "Key stats for a selected source file.")

        code_extensions = [
            ".py",
            ".js",
            ".jsx",
            ".ts",
            ".tsx",
            ".java",
            ".go",
            ".rs",
            ".cpp",
            ".c",
            ".cs",
        ]
        code_files = []
        for ext in code_extensions:
            code_files.extend(list(extract_path.rglob(f"*{ext}")))

        if code_files:
            try:
                total_size = sum(f.stat().st_size for f in code_files)
                repo_files_count = len(code_files)

                lang_map = {
                    ".py": "PYTHON",
                    ".js": "JAVASCRIPT",
                    ".jsx": "JAVASCRIPT",
                    ".ts": "TYPESCRIPT",
                    ".tsx": "TYPESCRIPT",
                    ".java": "JAVA",
                    ".go": "GO",
                    ".rs": "RUST",
                    ".cpp": "CPP",
                    ".c": "C",
                    ".cs": "CSHARP",
                }
                lang_counts: dict[str, int] = {}
                for f in code_files:
                    lang = lang_map.get(f.suffix.lower())
                    if lang:
                        lang_counts[lang] = lang_counts.get(lang, 0) + 1

                dominant_lang = max(lang_counts, key=lang_counts.get) if lang_counts else "—"

                m1, m2, m3 = st.columns(3)
                with m1:
                    st.metric("Size", f"{total_size / 1024:.2f} KB")
                with m2:
                    st.metric("Language", dominant_lang)
                with m3:
                    st.metric("Repo files", repo_files_count)
            except Exception as e:
                st.error(f"⚠️ Could not load repository stats: {e}")
        else:
            st.warning("No supported code files found in the repository.")

        # ── Step 3 ────────────────────────────────────────────────────────────
        _step(
            "3",
            "Run code analysis",
            "Extract structure, languages, and dependencies via AST parsing.",
        )

        col_num, col_spacer = st.columns([2, 3])
        with col_num:
            max_files_input = st.number_input(
                "Max files to analyze",
                min_value=50,
                max_value=500,
                value=200,
                step=50,
                help="Limit for performance — increase for larger repos.",
            )

        if st.button("▶ Start AST Parsing", type="primary", use_container_width=True):
            st.session_state.pop("report_md", None)
            st.session_state.pop("pdf_bytes", None)

            progress_bar = st.progress(0)
            status = st.empty()

            try:
                status.info("Scanning repository structure…")
                progress_bar.progress(20)

                results = parse_repo_ast(str(extract_path), max_files=max_files_input)
                progress_bar.progress(65)

                if not results:
                    st.warning("No supported code files found.")
                    progress_bar.progress(100)
                else:
                    status.info("Generating summary…")
                    progress_bar.progress(85)

                    total_files = len(results)
                    progress_bar.progress(100)
                    st.session_state["parsed_results"] = results
                    st.session_state["parsed_structured"] = None
                    st.success(
                        f"✅ Analysis complete — **{total_files} files** parsed."
                    )

                    languages: dict[str, int] = {}
                    for item in results:
                        if "Language:" in item:
                            lang_tok = item.split("Language:")[1].strip().split()[0]
                            languages[lang_tok] = languages.get(lang_tok, 0) + 1

                    with st.expander("Analysis Summary", expanded=True):
                        s1, s2 = st.columns(2)
                        with s1:
                            st.metric("Files Analyzed", total_files)
                        with s2:
                            st.metric("Languages Detected", len(languages))

                        if languages:
                            chips = "".join(
                                f'<span class="lang-chip{"  primary" if i == 0 else ""}">'
                                f'{l}&nbsp;<span style="opacity:.55">{c}</span></span>'
                                for i, (l, c) in enumerate(
                                    sorted(languages.items(), key=lambda x: -x[1])
                                )
                            )
                            st.markdown(
                                f'<div class="lang-row">{chips}</div>',
                                unsafe_allow_html=True,
                            )

            except Exception as e:
                st.error(f"Parsing error: {e}")
                import traceback

                with st.expander("Error details"):
                    st.code(traceback.format_exc())
            finally:
                progress_bar.empty()
                status.empty()

        # ── Step 4 ────────────────────────────────────────────────────────────
        _step(
            "4", "Generate documentation", "AI-powered multi-agent report generation."
        )

        if st.button(
            "✦ Generate AI-Powered Report", type="primary", use_container_width=True
        ):
            progress_bar = st.progress(0)
            status = st.empty()

            try:
                status.info("Collecting repository context…")
                progress_bar.progress(15)

                if (
                    "parsed_structured" not in st.session_state
                    or st.session_state["parsed_structured"] is None
                ):
                    parsed_struct = parse_repo_ast_structured(
                        str(extract_path), max_files=max_files_input
                    )
                    st.session_state["parsed_structured"] = parsed_struct
                else:
                    parsed_struct = st.session_state["parsed_structured"]

                progress_bar.progress(35)
                status.info("Building multi-agent task context…")

                def update_status(msg, prog):
                    status.info(msg)
                    progress_bar.progress(prog)

                if parsed_struct:
                    from utils.report_builder import generate_comprehensive_report

                    report_md = generate_comprehensive_report(
                        parsed_struct, progress_callback=update_status
                    )
                    progress_bar.progress(100)
                    st.session_state["report_md"] = report_md

                    try:
                        st.session_state["pdf_bytes"] = markdown_to_pdf_bytes(
                            report_md,
                            title=f"{extract_path.name} - AutoDocx AI Documentation",
                        )
                    except Exception as pdf_err:
                        st.session_state["pdf_bytes"] = None
                        st.warning(f"PDF generation skipped: {pdf_err}")

                    try:
                        md_path = (
                            uploads_dir / f"{extract_path.name}_autodocx_report.md"
                        )
                        md_path.write_text(report_md, encoding="utf-8")
                        if st.session_state.get("pdf_bytes"):
                            pdf_path = (
                                uploads_dir / f"{extract_path.name}_autodocx_report.pdf"
                            )
                            pdf_path.write_bytes(st.session_state["pdf_bytes"])
                    except Exception as disk_err:
                        print(f"DISK SAVE FAILED: {disk_err}")

                    st.success("✅ Report generated successfully!")
                else:
                    st.error("Failed to prepare report data.")

            except RuntimeError as e:
                st.error(str(e))
                st.info(
                    "Tip: Make sure Ollama is running and the correct model is installed (check OLLAMA_MODEL in .env)."
                )
            except Exception as e:
                st.error(f"Report generation failed: {e}")
                import traceback

                with st.expander("Error details"):
                    st.code(traceback.format_exc())
            finally:
                progress_bar.empty()
                status.empty()

        # ── Load report ───────────────────────────────────────────────────────
        report_md = st.session_state.get("report_md", "")
        pdf_bytes = st.session_state.get("pdf_bytes", None)

        if not report_md:
            md_path = uploads_dir / f"{extract_path.name}_autodocx_report.md"
            if md_path.exists():
                try:
                    report_md = md_path.read_text(encoding="utf-8")
                    st.session_state["report_md"] = report_md
                except Exception:
                    report_md = ""

        if pdf_bytes is None and report_md:
            pdf_path = uploads_dir / f"{extract_path.name}_autodocx_report.pdf"
            if pdf_path.exists():
                try:
                    pdf_bytes = pdf_path.read_bytes()
                    st.session_state["pdf_bytes"] = pdf_bytes
                except Exception:
                    pdf_bytes = None

        if report_md:
            words = len(report_md.split())
            chars = len(report_md)

            st.markdown(
                '<p class="result-header">✦ Documentation result</p>',
                unsafe_allow_html=True,
            )

            r1, r2, r3 = st.columns(3)
            with r1:
                st.metric("Format", "Markdown + PDF")
            with r2:
                st.metric("Words", f"{words:,}")
            with r3:
                st.metric("Characters", f"{chars:,}")

            st.markdown("<br/>", unsafe_allow_html=True)

            dl1, dl2, _ = st.columns([2, 2, 1])
            with dl1:
                st.download_button(
                    label="⬇ Download Markdown",
                    data=report_md,
                    file_name=f"{extract_path.name}_ai_documentation.md",
                    mime="text/markdown",
                    key="download_md_persistent",
                    use_container_width=True,
                )
            with dl2:
                st.download_button(
                    label="⬇ Download PDF",
                    data=pdf_bytes if pdf_bytes is not None else b"",
                    file_name=f"{extract_path.name}_ai_documentation.pdf",
                    mime="application/pdf",
                    key="download_pdf_persistent",
                    use_container_width=True,
                    disabled=pdf_bytes is None,
                )

    else:
        st.markdown(
            """
            <div class="empty-state">
                <span class="ei">🗂️</span>
                <p class="et">No repository loaded</p>
                <p class="eh">Upload a <strong>.zip</strong> file or enter a GitHub URL above to get started.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
