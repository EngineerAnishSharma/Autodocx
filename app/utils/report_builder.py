"""
Report builder that prepares prompts and generates LLM summaries for a repository.
Uses structured output from ast_parser.parse_repo_ast_structured.

Features:
- Comprehensive prompt generation
- Multiple export formats (Markdown, HTML, plain text)
- Better report structure and formatting
- Dependency analysis
"""
from pathlib import Path
import json
import os
import re
import sys
from typing import Dict, List, Optional
from dotenv import load_dotenv
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.logger import logger

load_dotenv()


def _create_ollama_client():
    """Create an OpenAI-compatible client configured for local Ollama."""
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise RuntimeError("openai package not installed. Run: pip install openai") from exc

    base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")
    # Ollama accepts any non-empty API key with the OpenAI-compatible endpoint.
    api_key = os.getenv("OLLAMA_API_KEY", "ollama")
    return OpenAI(base_url=base_url, api_key=api_key)

def load_readme(repo_path: Path) -> str:
    """Return README contents if present."""
    for name in ["README.md", "README.MD", "README.txt", "README", "readme.md", "readme.txt"]:
        candidate = repo_path / name
        if candidate.exists() and candidate.is_file():
            try:
                content = candidate.read_text(encoding="utf-8", errors="ignore")
                logger.debug(f"Loaded README from {candidate}")
                return content
            except Exception as e:
                logger.warning(f"Error reading README {candidate}: {e}")
                return ""
    logger.debug("No README found")
    return ""


def load_package_json(repo_path: Path) -> Optional[Dict]:
    """Load package.json for Node.js projects."""
    for name in ["package.json"]:
        candidate = repo_path / name
        if candidate.exists() and candidate.is_file():
            try:
                return json.loads(candidate.read_text(encoding="utf-8", errors="ignore"))
            except Exception:
                return None
    return None


def load_requirements_txt(repo_path: Path) -> List[str]:
    """Load requirements.txt for Python projects."""
    for name in ["requirements.txt", "requirements-dev.txt"]:
        candidate = repo_path / name
        if candidate.exists() and candidate.is_file():
            try:
                content = candidate.read_text(encoding="utf-8", errors="ignore")
                return [line.strip() for line in content.splitlines() if line.strip() and not line.startswith("#")]
            except Exception:
                return []
    return []


def load_pom_xml(repo_path: Path) -> Optional[str]:
    """Load pom.xml for Java Maven projects."""
    candidate = repo_path / "pom.xml"
    if candidate.exists() and candidate.is_file():
        try:
            return candidate.read_text(encoding="utf-8", errors="ignore")[:2000]  # First 2000 chars
        except Exception:
            return None
    return None


def summarize_files(files: List[Dict], limit: int = 20) -> str:
    lines = []
    for f in files[:limit]:
        badge = "(skipped)" if f.get("skipped") else "(error)" if f.get("error") else ""
        funcs = ", ".join(f.get("functions", [])[:6])
        classes = ", ".join(f.get("classes", [])[:6])
        imports = ", ".join(f.get("imports", [])[:6])
        lines.append(f"- {f.get('path')} [{f.get('language')}] {badge}")
        if funcs:
            lines.append(f"  - functions: {funcs}")
        if classes:
            lines.append(f"  - classes: {classes}")
        if imports:
            lines.append(f"  - imports: {imports}")
    if len(files) > limit:
        lines.append(f"... and {len(files) - limit} more files")
    return "\n".join(lines) if lines else "(no files parsed)"


def summarize_stats(stats: Dict) -> str:
    lines = []
    lines.append(f"total_considered: {stats.get('total_considered', 0)}")
    lines.append(f"scanned: {stats.get('scanned', 0)}")
    lines.append(f"skipped: {stats.get('skipped', 0)}")
    if stats.get("by_language"):
        pairs = ", ".join([f"{k}:{v}" for k, v in stats["by_language"].items()])
        lines.append(f"by_language: {pairs}")
    if stats.get("largest_files"):
        lines.append("largest_files:")
        for path, size in stats["largest_files"]:
            kb = round(size / 1024, 1)
            lines.append(f"  - {path} ({kb} KB)")
    return "\n".join(lines)


def build_prompt(parsed: Dict) -> str:
    """Build a comprehensive prompt for LLM report generation."""
    repo_path = Path(parsed.get("repo_path", "."))
    readme = load_readme(repo_path)
    files = parsed.get("files", [])
    stats = parsed.get("stats", {})
    
    # Load dependency information
    package_json = load_package_json(repo_path)
    requirements = load_requirements_txt(repo_path)
    pom_xml = load_pom_xml(repo_path)
    
    prompt_parts = []
    prompt_parts.append(
        "You are a senior software architect and technical writer. "
        "Generate professional, concise, and structured project documentation in Markdown."
    )

    prompt_parts.append(
        "\nFollow these rules strictly:\n"
        "1. Use clear headings with Markdown formatting.\n"
        "2. Provide structured sections.\n"
        "3. Use bullet points and tables where necessary.\n"
        "4. Maintain a professional technical documentation style.\n"
        "5. Do NOT skip any section.\n"
        "6. If information is missing, make reasonable assumptions and label them clearly as assumptions."
    )

    prompt_parts.append(
        "\nReturn documentation in the exact format below and keep section numbering unchanged:\n\n"
        "# Project Documentation\n\n"
        "## 1. Project Overview\n"
        "Include: Project Name: Description: Problem Statement: Objectives: Scope of the Project:\n\n"
        "## 2. System Architecture\n"
        "Include: High-Level Architecture(detailed), Components of the System, Technology Stack.\n"
        "Also include a subsection named '### Use Case Diagram' with a Mermaid `flowchart` code block.\n"
        "Make the use case diagram user-friendly: use simple actor names (e.g., User, Admin, System), short action labels, and clear left-to-right flow.\n"
        "After the diagram, add 4-6 bullet points explaining the use cases in plain language for non-technical readers.\n"
        "Use this table for technology stack:\n"
        "| Layer | Technology |\n"
        "|------|-------------|\n"
        "| Frontend | |\n"
        "| Backend | |\n"
        "| Database | |\n"
        "| Deployment | |\n\n"
        "## 3. Functional Requirements\n"
        "Use a table:\n"
        "| ID | Requirement |\n"
        "|----|-------------|\n"
        "| FR1 | |\n"
        "| FR2 | |\n"
        "| FR3 | |\n\n"
        "## 4. Non-Functional Requirements\n"
        "Include bullet points for: Performance, Scalability, Security, Reliability, Usability.\n\n"
        "## 5. System Design\n"
        "### Database Design\n"
        "Describe tables, key fields, and relationships.\n"
        "### API Design\n"
        "Use a table:\n"
        "| Endpoint | Method | Description |\n"
        "|---------|--------|-------------|\n"
        "| | | |\n\n"
        "## 6. Folder Structure\n"
        "Provide the project directory structure using a code block tree.\n\n"
        "## 7. Features\n"
        "List all major features using bullet points.\n\n"
        "## 8. User Guide\n"
        "Explain how users interact with the system step-by-step using a numbered list.\n\n"
        "## 9. Testing\n"
        "Include:\n"
        "### Testing Types\n"
        "- Unit Testing\n"
        "- Integration Testing\n"
        "- System Testing\n"
        "### Test Cases\n"
        "Use a table:\n"
        "| Test Case | Expected Result |\n"
        "|-----------|----------------|\n"
        "| | |\n\n"
        "## 10. Deployment\n"
        "Include deployment architecture and tools used (Docker, Cloud, etc.).\n\n"
        "## 11. Security Considerations\n"
        "Explain authentication, API security, and data protection.\n\n"
        "## 12. Future Improvements\n"
        "List potential future enhancements.\n\n"
        "## 13. References\n"
        "Include libraries used, tools, and external resources."
    )

    prompt_parts.append(
        "\nOutput requirements:\n"
        "- Return well-formatted Markdown only.\n"
        "- Use tables wherever appropriate.\n"
        "- Keep explanations concise but clear.\n"
        "- Include one Mermaid use case diagram in section 2 using actors and system interactions inferred from the repository.\n"
        "- Keep the use case diagram easy to understand for end users (minimal jargon, readable labels, clear interactions).\n"
        "- Ground output in repository evidence first; use explicit assumptions only when evidence is missing."
    )
    
    prompt_parts.append("\n---\n## Repository Statistics:")
    prompt_parts.append(summarize_stats(stats))
    
    prompt_parts.append("\n---\n## Code Structure Analysis:")
    prompt_parts.append(summarize_files(files, limit=50))  # Increased from 30 to 50 for more context
    
    if readme:
        prompt_parts.append("\n---\n## Existing README Content (Full):")
        prompt_parts.append("\n".join(readme.splitlines()[:200]))  # Increased from 100 to 200 lines
    
    if package_json:
        prompt_parts.append("\n---\n## Package.json Information (Full Details):")
        prompt_parts.append(f"Name: {package_json.get('name', 'N/A')}")
        prompt_parts.append(f"Version: {package_json.get('version', 'N/A')}")
        prompt_parts.append(f"Description: {package_json.get('description', 'N/A')}")
        if package_json.get('dependencies'):
            deps = package_json.get('dependencies', {})
            prompt_parts.append(f"\nDependencies with versions ({len(deps)} total):")
            for dep_name, dep_version in list(deps.items())[:50]:  # Show up to 50 with versions
                prompt_parts.append(f"  - {dep_name}: {dep_version}")
        if package_json.get('devDependencies'):
            dev_deps = package_json.get('devDependencies', {})
            prompt_parts.append(f"\nDev Dependencies with versions ({len(dev_deps)} total):")
            for dep_name, dep_version in list(dev_deps.items())[:30]:
                prompt_parts.append(f"  - {dep_name}: {dep_version}")
        if package_json.get('engines'):
            prompt_parts.append(f"\nRequired Engine Versions: {package_json.get('engines')}")
    
    if requirements:
        prompt_parts.append("\n---\n## Python Dependencies (Full List with Versions):")
        prompt_parts.append(f"Total dependencies: {len(requirements)}")
        prompt_parts.append("\n".join(requirements[:50]))  # Show more dependencies
    
    if pom_xml:
        prompt_parts.append("\n---\n## Maven Configuration (pom.xml - Full Content):")
        prompt_parts.append(pom_xml[:3000])  # Increased from 500 to 3000 chars for more context
    
    prompt_parts.append("\n---\n## Generate the documentation report now.")
    
    return "\n".join(prompt_parts)


def _split_text_batches(text: str, chunk_chars: int, max_batches: int) -> List[str]:
    """Split large text into sentence-aware batches for multi-pass LLM processing."""
    if not text:
        return []
    if len(text) <= chunk_chars:
        return [text]

    lines = text.splitlines(keepends=True)
    batches: List[str] = []
    current: List[str] = []
    current_len = 0

    for line in lines:
        line_len = len(line)
        # If adding this line exceeds chunk size, close the current batch.
        if current and current_len + line_len > chunk_chars:
            batches.append("".join(current))
            current = []
            current_len = 0
        current.append(line)
        current_len += line_len

        if len(batches) >= max_batches:
            break

    if current and len(batches) < max_batches:
        batches.append("".join(current))

    return batches


def _chat_completion(client, model: str, system_content: str, user_content: str, temperature: float, max_tokens: int) -> str:
    """Execute a single chat completion call and return the assistant content."""
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_content},
            {"role": "user", "content": user_content},
        ],
        temperature=temperature,
        max_tokens=max_tokens,
    )
    content = resp.choices[0].message.content
    return content.strip() if content else ""


def generate_llm_report(prompt: str, model: Optional[str] = None) -> str:
    """Generate LLM report via local Ollama with optional batch processing."""
    model = model or os.getenv("OLLAMA_MODEL", "qwen2.5:14b")
    temperature = float(os.getenv("OLLAMA_TEMPERATURE", "0.3"))
    max_tokens = int(os.getenv("OLLAMA_MAX_TOKENS", "12000"))
    batch_enabled = os.getenv("OLLAMA_BATCH_ENABLED", "true").lower() in {"1", "true", "yes"}
    chunk_chars = int(os.getenv("OLLAMA_BATCH_CHUNK_CHARS", "12000"))
    max_batches = int(os.getenv("OLLAMA_BATCH_MAX", "4"))

    system_content = (
        "You are a senior software architect and technical writer. "
        "Strictly follow the user-provided output template and keep section numbering exactly as requested. "
        "Produce professional technical documentation using markdown headings, bullets, and tables. "
        "Do not skip sections. Ground content in repository evidence, and when information is missing, "
        "make reasonable assumptions and label them clearly as assumptions. "
        "For use case diagrams, optimize for readability for non-technical readers."
    )

    try:
        logger.info(f"Generating LLM report using Ollama model: {model}")
        client = _create_ollama_client()

        # Single-pass mode remains available for small prompts or explicit opt-out.
        if not batch_enabled or len(prompt) <= chunk_chars:
            content = _chat_completion(
                client=client,
                model=model,
                system_content=system_content,
                user_content=prompt,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            logger.info("LLM report generated successfully (single-pass)")
            return content

        logger.info(
            f"Batch mode enabled for large prompt (length={len(prompt)}, chunk_chars={chunk_chars}, max_batches={max_batches})"
        )

        # Separate high-level instructions from heavy repository context for better synthesis.
        split_marker = "\n---\n## Repository Statistics:"
        if split_marker in prompt:
            instructions_block, context_block = prompt.split(split_marker, 1)
            context_block = split_marker + context_block
        else:
            instructions_block = prompt
            context_block = ""

        context_batches = _split_text_batches(context_block, chunk_chars=chunk_chars, max_batches=max_batches)

        if not context_batches:
            content = _chat_completion(
                client=client,
                model=model,
                system_content=system_content,
                user_content=prompt,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            logger.info("LLM report generated successfully (fallback single-pass)")
            return content

        batch_summaries: List[str] = []
        for idx, batch in enumerate(context_batches, start=1):
            logger.info(f"Processing batch {idx}/{len(context_batches)}")
            batch_prompt = (
                "Summarize this repository context chunk for technical documentation synthesis.\n"
                "Return concise evidence only using bullet points with these labels where applicable:\n"
                "- Architecture\n- Components\n- Tech Stack\n- Functional Requirements\n"
                "- Non-Functional Requirements\n- Database/API\n- Features\n- User Flow\n"
                "- Testing/Deployment/Security\n- Future Improvements\n- References\n"
                "If data is missing, write: Not clearly inferable from repository.\n\n"
                f"Context chunk {idx}/{len(context_batches)}:\n\n{batch}"
            )
            summary = _chat_completion(
                client=client,
                model=model,
                system_content=system_content,
                user_content=batch_prompt,
                temperature=temperature,
                max_tokens=max(1200, min(max_tokens, 4000)),
            )
            batch_summaries.append(f"### Batch {idx} Summary\n{summary}")

        final_prompt = (
            f"{instructions_block}\n\n"
            "Use the consolidated evidence below to produce the final documentation. "
            "Preserve the exact 14-section format and include the required use case diagram.\n\n"
            "## Consolidated Evidence From Batch Processing\n\n"
            + "\n\n".join(batch_summaries)
        )

        content = _chat_completion(
            client=client,
            model=model,
            system_content=system_content,
            user_content=final_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        logger.info("LLM report generated successfully (batch mode)")
        return content
    except Exception as e:
        logger.error(f"Error calling Ollama API: {e}", exc_info=True)
        raise RuntimeError(
            "Error calling Ollama. Ensure Ollama is running and model 'qwen2.5:14b' is available. "
            "Try: ollama run qwen2.5:14b"
        ) from e


def generate_markdown_report(parsed: Dict, include_llm: bool = False) -> str:
    """Generate a markdown report without LLM (structured from parsed data)."""
    repo_path = Path(parsed.get("repo_path", "."))
    files = parsed.get("files", [])
    stats = parsed.get("stats", {})
    readme = load_readme(repo_path)
    package_json = load_package_json(repo_path)
    requirements = load_requirements_txt(repo_path)
    
    report = []
    report.append(f"# Project Documentation")
    report.append(f"\n*Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*\n")
    
    report.append("## Project Overview")
    if readme:
        report.append("\n" + "\n".join(readme.splitlines()[:50]))
    else:
        report.append("\n*No README found. Documentation generated from code analysis.*")
    
    report.append("\n## Project Statistics")
    report.append(f"- **Total Files Analyzed:** {stats.get('total_considered', 0)}")
    report.append(f"- **Successfully Scanned:** {stats.get('scanned', 0)}")
    report.append(f"- **Skipped:** {stats.get('skipped', 0)}")
    report.append(f"- **Errors:** {stats.get('errors', 0)}")
    
    if stats.get('by_language'):
        report.append("\n### Language Distribution")
        for lang, count in stats.get('by_language', {}).items():
            report.append(f"- **{lang}:** {count} files")
    
    if stats.get('largest_files'):
        report.append("\n### Largest Files")
        for path, size in stats.get('largest_files', []):
            kb = round(size / 1024, 1)
            report.append(f"- `{path}` ({kb} KB)")
    
    report.append("\n## Technology Stack")
    languages = list(stats.get('by_language', {}).keys())
    if languages:
        report.append(f"**Languages:** {', '.join(languages)}")
    
    if package_json:
        report.append("\n### Node.js Dependencies")
        deps = list(package_json.get('dependencies', {}).keys())[:20]
        if deps:
            report.append(", ".join(deps))
    
    if requirements:
        report.append("\n### Python Dependencies")
        report.append("\n".join([f"- {req}" for req in requirements[:30]]))
    
    report.append("\n## Key Files and Structure")
    important_files = [f for f in files if not f.get('skipped') and not f.get('error')][:30]
    for file_info in important_files:
        report.append(f"\n### `{file_info.get('path', 'unknown')}`")
        report.append(f"- **Language:** {file_info.get('language', 'unknown')}")
        if file_info.get('classes'):
            report.append(f"- **Classes:** {', '.join(file_info.get('classes', [])[:5])}")
        if file_info.get('functions'):
            report.append(f"- **Functions:** {', '.join(file_info.get('functions', [])[:5])}")
    
    report.append("\n## Setup Instructions")
    report.append("\n*Setup instructions would be extracted from README or inferred from project structure.*")
    
    report.append("\n---\n*This report was automatically generated by AutoDocx.*")
    
    return "\n".join(report)