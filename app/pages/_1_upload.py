"""
Streamlit Upload & Preprocessing Page for AutoDocx
--------------------------------------------------
Modern UI for uploading repos, previewing structure,
running AST-based preprocessing, and viewing code.

Features:
- Upload ZIP files from GitHub/Bitbucket
- Real-time progress indicators
- Code exploration
- AST-based analysis
- LLM-powered documentation generation
"""

import streamlit as st
from pathlib import Path
import time
from components.uploader import handle_uploaded_zip
from utils.file_utils import list_repo_tree
from utils.ast_parser import parse_repo_ast, parse_repo_ast_structured
from utils.report_builder import build_prompt, generate_llm_report, generate_markdown_report

PAGE_TITLE = "📦 Upload Repository"


def show():
    st.divider()
    st.subheader(PAGE_TITLE)
    st.caption(
        "Upload a `.zip` file of your GitHub repo. We'll extract it, analyze its structure, "
        "and prepare it for documentation generation. Max upload size: 100 MB."
    )

    uploaded_file = st.file_uploader(
        "📁 Upload repository (.zip)",
        type=["zip"],
        accept_multiple_files=False,
        help="Drag and drop or click to upload your GitHub repo as a ZIP file.",
    )

    uploads_dir = Path("app/data/uploads")
    uploads_dir.mkdir(parents=True, exist_ok=True)

    if uploaded_file:
        try:
            repo_name, extract_path = handle_uploaded_zip(uploaded_file, uploads_dir)
            extract_path = Path(extract_path)
            st.success(f"✅ Repository uploaded and extracted successfully: `{repo_name}`")

            with st.expander("📂 Repository Structure Preview", expanded=False):
                tree = list_repo_tree((extract_path), max_entries=300)
                st.code("\n".join(tree), language="bash")

            # Store repo path
            st.session_state["uploaded_repo_path"] = str(extract_path)

            # --- File viewer dropdown ---
            st.divider()
            st.subheader("👁️ Step 2: Explore Code Files")

            # Find all supported code files
            code_extensions = [".py", ".js", ".jsx", ".ts", ".tsx", ".java", ".go", ".rs", ".cpp", ".c", ".cs"]
            code_files = []
            for ext in code_extensions:
                code_files.extend(list(extract_path.rglob(f"*{ext}")))
            
            if code_files:
                file_options = [str(f.relative_to(extract_path)) for f in code_files]
                selected_file = st.selectbox(
                    "Select a file to view its code:",
                    file_options,
                    help=f"Found {len(code_files)} code files in the repository"
                )

                if selected_file:
                    try:
                        file_path = extract_path / selected_file
                        file_size = file_path.stat().st_size
                        
                        # Show file metadata
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.metric("File Size", f"{file_size / 1024:.2f} KB")
                        with col2:
                            st.metric("Language", file_path.suffix[1:].upper() if file_path.suffix else "Unknown")
                        with col3:
                            st.metric("Total Files", len(code_files))
                        
                        # Determine language for syntax highlighting
                        lang_map = {
                            ".py": "python", ".js": "javascript", ".jsx": "javascript",
                            ".ts": "typescript", ".tsx": "typescript", ".java": "java",
                            ".go": "go", ".rs": "rust", ".cpp": "cpp", ".c": "c", ".cs": "csharp"
                        }
                        lang = lang_map.get(file_path.suffix.lower(), "text")
                        
                        # Read and display file content
                        max_file_size = 500 * 1024  # 500 KB limit for display
                        if file_size > max_file_size:
                            st.warning(f"File is large ({file_size / 1024:.1f} KB). Showing first 500 KB only.")
                            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                                content = f.read(max_file_size)
                        else:
                            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                                content = f.read()
                        
                        st.code(content, language=lang)
                    except Exception as e:
                        st.error(f"⚠️ Could not load file: {e}")
            else:
                st.warning("No supported code files found in the uploaded repository.")

            # --- Preprocessing section ---
            st.divider()
            st.subheader("⚙️ Step 3: Run Code Analysis")

            col1, col2 = st.columns(2)
            with col1:
                max_files_input = st.number_input(
                    "Max files to analyze",
                    min_value=50,
                    max_value=500,
                    value=200,
                    step=50,
                    help="Limit the number of files to analyze (for performance)"
                )
            
            if st.button("🚀 Start AST Parsing", type="primary", use_container_width=True):
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                status_text.info("🔄 Preprocessing started — running AST parsing and language detection...")
                progress_bar.progress(10)

                try:
                    status_text.info("📊 Scanning repository structure...")
                    progress_bar.progress(30)
                    
                    results = parse_repo_ast(str(extract_path), max_files=max_files_input)
                    progress_bar.progress(60)

                    if not results:
                        st.warning("⚠️ No supported code files found in this repository.")
                        progress_bar.progress(100)
                    else:
                        status_text.info("✅ Parsing complete! Generating summary...")
                        progress_bar.progress(80)
                        
                        total_files = len(results)
                        st.success(f"✅ Analysis complete! {total_files} files analyzed.")
                        progress_bar.progress(100)
                        
                        # Store results in session state
                        st.session_state["parsed_results"] = results
                        st.session_state["parsed_structured"] = None  # Will be generated if needed

                        # Display statistics
                        with st.expander("📊 Analysis Summary", expanded=True):
                            st.metric("Files Analyzed", total_files)
                            
                            # Count languages
                            languages = {}
                            for item in results:
                                if "Language:" in item:
                                    lang = item.split("Language:")[1].strip().split()[0]
                                    languages[lang] = languages.get(lang, 0) + 1
                            
                            if languages:
                                st.write("**Language Distribution:**")
                                for lang, count in sorted(languages.items(), key=lambda x: x[1], reverse=True):
                                    st.write(f"- {lang}: {count} files")

                        with st.expander("🧩 View Parsed Files (Top 15)", expanded=False):
                            for item in results[:15]:
                                st.markdown(f"```\n{item}\n```")
                            if len(results) > 15:
                                st.caption(f"... and {len(results) - 15} more files")

                        status_text.success("✅ Parsed file summary generated successfully — ready for documentation generation!")
                        progress_bar.empty()
                except Exception as e:
                    st.error(f"❌ Error during parsing: {e}")
                    import traceback
                    with st.expander("Error Details"):
                        st.code(traceback.format_exc())
                    progress_bar.empty()

            st.divider()
            st.subheader("📝 Step 4: Generate Documentation")
            
            report_type = st.radio(
                "Select report type:",
                ["Structured Report (No LLM)", "AI-Powered Report (Requires API Key)"],
                help="Structured reports are generated from code analysis. AI-powered reports use LLM for enhanced documentation."
            )

            if report_type == "Structured Report (No LLM)":
                if st.button("📄 Generate Structured Report", type="primary", use_container_width=True):
                    with st.spinner("Generating structured report from code analysis..."):
                        try:
                            if "parsed_structured" not in st.session_state or st.session_state["parsed_structured"] is None:
                                parsed_struct = parse_repo_ast_structured(str(extract_path), max_files=max_files_input)
                                st.session_state["parsed_structured"] = parsed_struct
                            else:
                                parsed_struct = st.session_state["parsed_structured"]
                            
                            report_md = generate_markdown_report(parsed_struct)
                            
                            st.success("✅ Report generated successfully!")
                            st.markdown(report_md)
                            
                            st.download_button(
                                label="📥 Download Report (Markdown)",
                                data=report_md,
                                file_name=f"{extract_path.name}_documentation.md",
                                mime="text/markdown",
                                use_container_width=True
                            )
                        except Exception as e:
                            st.error(f"Report generation failed: {e}")
                            import traceback
                            with st.expander("Error Details"):
                                st.code(traceback.format_exc())
            
            else:  # AI-Powered Report
                st.caption("⚠️ Requires OPENAI_API_KEY environment variable. Set it in your .env file or environment.")
                
                if st.button("🧠 Generate AI-Powered Report", type="primary", use_container_width=True):
                    progress_bar = st.progress(0)
                    status_text = st.empty()
                    
                    status_text.info("🔄 Collecting repository context for LLM...")
                    progress_bar.progress(20)
                    
                    try:
                        if "parsed_structured" not in st.session_state or st.session_state["parsed_structured"] is None:
                            parsed_struct = parse_repo_ast_structured(str(extract_path), max_files=max_files_input)
                            st.session_state["parsed_structured"] = parsed_struct
                        else:
                            parsed_struct = st.session_state["parsed_structured"]
                        
                        progress_bar.progress(40)
                        status_text.info("📝 Building comprehensive prompt...")
                        prompt = build_prompt(parsed_struct)
                        progress_bar.progress(60)

                        if parsed_struct and prompt:
                            status_text.info("🤖 Calling LLM to generate documentation...")
                            progress_bar.progress(80)
                            
                            report_md = generate_llm_report(prompt)
                            progress_bar.progress(100)
                            
                            st.success("✅ AI-powered report generated successfully!")
                            st.markdown(report_md)
                            
                            col1, col2 = st.columns(2)
                            with col1:
                                st.download_button(
                                    label="📥 Download Report (Markdown)",
                                    data=report_md,
                                    file_name=f"{extract_path.name}_ai_documentation.md",
                                    mime="text/markdown",
                                    use_container_width=True
                                )
                            with col2:
                                # Option to view prompt (for debugging)
                                with st.expander("🔍 View Prompt"):
                                    st.code(prompt[:2000] + "..." if len(prompt) > 2000 else prompt)
                            
                            progress_bar.empty()
                            status_text.empty()
                        else:
                            st.error("Failed to prepare report data.")
                    except RuntimeError as e:
                        st.error(f"❌ {str(e)}")
                        st.info("💡 Tip: Make sure you have set OPENAI_API_KEY in your environment variables.")
                    except Exception as e:
                        st.error(f"LLM report generation failed: {e}")
                        import traceback
                        with st.expander("Error Details"):
                            st.code(traceback.format_exc())
                    finally:
                        progress_bar.empty()
                        status_text.empty()

        except Exception as e:
            st.error(f"❌ Error processing upload: {e}")

    else:
        st.info("📥 Please upload a `.zip` of your repository to get started.")
