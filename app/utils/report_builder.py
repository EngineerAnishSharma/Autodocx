"""
Report builder that prepares prompts and generates LLM summaries for a repository.
Uses structured output from ast_parser.parse_repo_ast_structured.

Improvements over v1:
- Correct sequential section ordering (1–13)
- Use case diagram embedded inside Section 2
- Final assembly pass re-orders and deduplicates sections
- Better context feeding per agent (README → PM, AST → Arch, deps → QA)
- Gemini diagrams injected into Section 2, not appended at the end
- Folder structure sent as full tree string to prevent truncation
- Generation metadata (timestamp, model, repo) added to output header
"""

from pathlib import Path
import json
import os
import re
import sys
from typing import Dict, List, Optional
from dotenv import load_dotenv
from datetime import datetime
import google.generativeai as genai

sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.logger import logger

load_dotenv()

gemini_key = os.getenv("GEMINI_API_KEY")
if gemini_key:
    genai.configure(api_key=gemini_key)


# ── LLM client ────────────────────────────────────────────────────────────────


def _create_ollama_client():
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise RuntimeError(
            "openai package not installed. Run: pip install openai"
        ) from exc
    base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")
    api_key = os.getenv("OLLAMA_API_KEY", "ollama")
    return OpenAI(base_url=base_url, api_key=api_key)


def _chat_completion(
    client,
    model: str,
    system_content: str,
    user_content: str,
    temperature: float,
    max_tokens: int,
) -> str:
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


# ── File loaders ──────────────────────────────────────────────────────────────


def load_readme(repo_path: Path) -> str:
    for name in [
        "README.md",
        "README.MD",
        "README.txt",
        "README",
        "readme.md",
        "readme.txt",
    ]:
        candidate = repo_path / name
        if candidate.exists() and candidate.is_file():
            try:
                return candidate.read_text(encoding="utf-8", errors="ignore")
            except Exception as e:
                logger.warning(f"Error reading README {candidate}: {e}")
    return ""


def load_package_json(repo_path: Path) -> Optional[Dict]:
    candidate = repo_path / "package.json"
    if candidate.exists():
        try:
            return json.loads(candidate.read_text(encoding="utf-8", errors="ignore"))
        except Exception:
            return None
    return None


def load_requirements_txt(repo_path: Path) -> List[str]:
    for name in ["requirements.txt", "requirements-dev.txt"]:
        candidate = repo_path / name
        if candidate.exists():
            try:
                content = candidate.read_text(encoding="utf-8", errors="ignore")
                return [
                    l.strip()
                    for l in content.splitlines()
                    if l.strip() and not l.startswith("#")
                ]
            except Exception:
                return []
    return []


def load_pom_xml(repo_path: Path) -> Optional[str]:
    candidate = repo_path / "pom.xml"
    if candidate.exists():
        try:
            return candidate.read_text(encoding="utf-8", errors="ignore")[:4000]
        except Exception:
            return None
    return None


def load_folder_tree(repo_path: Path, max_lines: int = 120) -> str:
    """
    Build a text tree of the repo for the Folder Structure section.
    Uses pathlib — no shell commands needed. Skips hidden dirs and
    common noise folders (node_modules, __pycache__, .git, target, build).
    """
    SKIP = {
        ".git",
        "node_modules",
        "__pycache__",
        ".idea",
        ".vscode",
        "target",
        "build",
        "dist",
        ".gradle",
        ".mvn",
        "venv",
        ".venv",
    }

    lines: List[str] = [str(repo_path.name) + "/"]

    def _walk(path: Path, prefix: str, depth: int):
        if depth > 6:
            return
        try:
            entries = sorted(
                path.iterdir(), key=lambda p: (p.is_file(), p.name.lower())
            )
        except PermissionError:
            return

        entries = [e for e in entries if e.name not in SKIP]
        for i, entry in enumerate(entries):
            if len(lines) >= max_lines:
                lines.append(f"{prefix}    ... (truncated)")
                return
            connector = "└── " if i == len(entries) - 1 else "├── "
            lines.append(
                f"{prefix}{connector}{entry.name}{'/' if entry.is_dir() else ''}"
            )
            if entry.is_dir():
                extension = "    " if i == len(entries) - 1 else "│   "
                _walk(entry, prefix + extension, depth + 1)

    _walk(repo_path, "", 0)
    return "\n".join(lines)


# ── Summarizers ───────────────────────────────────────────────────────────────


def summarize_files(files: List[Dict], limit: int = 60) -> str:
    lines = []
    for f in files[:limit]:
        badge = "(skipped)" if f.get("skipped") else "(error)" if f.get("error") else ""
        funcs = ", ".join(f.get("functions", [])[:8])
        classes = ", ".join(f.get("classes", [])[:6])
        imports = ", ".join(f.get("imports", [])[:6])
        lines.append(f"- {f.get('path')} [{f.get('language')}] {badge}")
        if classes:
            lines.append(f"  classes: {classes}")
        if funcs:
            lines.append(f"  functions: {funcs}")
        if imports:
            lines.append(f"  imports: {imports}")
    if len(files) > limit:
        lines.append(f"... and {len(files) - limit} more files")
    return "\n".join(lines) if lines else "(no files parsed)"


def summarize_stats(stats: Dict) -> str:
    lines = [
        f"total_considered: {stats.get('total_considered', 0)}",
        f"scanned: {stats.get('scanned', 0)}",
        f"skipped: {stats.get('skipped', 0)}",
    ]
    if stats.get("by_language"):
        pairs = ", ".join([f"{k}:{v}" for k, v in stats["by_language"].items()])
        lines.append(f"by_language: {pairs}")
    if stats.get("largest_files"):
        lines.append("largest_files:")
        for path, size in stats["largest_files"]:
            lines.append(f"  - {path} ({round(size/1024, 1)} KB)")
    return "\n".join(lines)


def build_deps_context(
    repo_path: Path,
    package_json: Optional[Dict],
    requirements: List[str],
    pom_xml: Optional[str],
) -> str:
    """Build a rich dependency context string."""
    parts = []
    if package_json:
        deps = package_json.get("dependencies", {})
        dev_deps = package_json.get("devDependencies", {})
        parts.append(
            f"package.json name: {package_json.get('name','N/A')}, version: {package_json.get('version','N/A')}"
        )
        if deps:
            parts.append(
                "dependencies: "
                + ", ".join(f"{k}@{v}" for k, v in list(deps.items())[:40])
            )
        if dev_deps:
            parts.append(
                "devDependencies: "
                + ", ".join(f"{k}@{v}" for k, v in list(dev_deps.items())[:20])
            )
    if requirements:
        parts.append("requirements.txt: " + ", ".join(requirements[:40]))
    if pom_xml:
        parts.append("pom.xml (excerpt):\n" + pom_xml[:3000])
    return "\n".join(parts) if parts else "No dependency files found."


# ── Section extractor ─────────────────────────────────────────────────────────

# Maps canonical section numbers to all heading variants they might appear as.
_SECTION_PATTERNS = {
    1: re.compile(
        r"^#{1,3}\s+(?:\d+[.)]\s+)?Project Overview", re.IGNORECASE | re.MULTILINE
    ),
    2: re.compile(
        r"^#{1,3}\s+(?:\d+[.)]\s+)?System Architecture", re.IGNORECASE | re.MULTILINE
    ),
    3: re.compile(
        r"^#{1,3}\s+(?:\d+[.)]\s+)?Functional Requirements",
        re.IGNORECASE | re.MULTILINE,
    ),
    4: re.compile(
        r"^#{1,3}\s+(?:\d+[.)]\s+)?Non.Functional Requirements",
        re.IGNORECASE | re.MULTILINE,
    ),
    5: re.compile(
        r"^#{1,3}\s+(?:\d+[.)]\s+)?(?:System Design|Architecture Design|Design Overview)",
        re.IGNORECASE | re.MULTILINE,
    ),
    6: re.compile(
        r"^#{1,3}\s+(?:\d+[.)]\s+)?Folder Structure", re.IGNORECASE | re.MULTILINE
    ),
    7: re.compile(r"^#{1,3}\s+(?:\d+[.)]\s+)?Features", re.IGNORECASE | re.MULTILINE),
    8: re.compile(r"^#{1,3}\s+(?:\d+[.)]\s+)?User Guide", re.IGNORECASE | re.MULTILINE),
    9: re.compile(r"^#{1,3}\s+(?:\d+[.)]\s+)?Testing", re.IGNORECASE | re.MULTILINE),
    10: re.compile(
        r"^#{1,3}\s+(?:\d+[.)]\s+)?Deployment", re.IGNORECASE | re.MULTILINE
    ),
    11: re.compile(r"^#{1,3}\s+(?:\d+[.)]\s+)?Security", re.IGNORECASE | re.MULTILINE),
    12: re.compile(
        r"^#{1,3}\s+(?:\d+[.)]\s+)?Future Improvements", re.IGNORECASE | re.MULTILINE
    ),
    13: re.compile(
        r"^#{1,3}\s+(?:\d+[.)]\s+)?References", re.IGNORECASE | re.MULTILINE
    ),
}

_SECTION_TITLES = {
    1: "Project Overview",
    2: "System Architecture",
    3: "Functional Requirements",
    4: "Non-Functional Requirements",
    5: "System Design",
    6: "Folder Structure",
    7: "Features",
    8: "User Guide",
    9: "Testing",
    10: "Deployment",
    11: "Security Considerations",
    12: "Future Improvements",
    13: "References",
}


def _extract_section(text: str, section_num: int) -> str:
    """
    Extract the body of a numbered section from LLM output.
    Returns empty string if the section is not found.
    """
    pattern = _SECTION_PATTERNS.get(section_num)
    if not pattern:
        return ""

    match = pattern.search(text)
    if not match:
        return ""

    start = match.end()
    # Find the next top-level section heading (## N. ...) to determine end
    next_section = re.search(r"^#{1,2}\s+\d+[.)]\s+\w", text[start:], re.MULTILINE)
    end = start + next_section.start() if next_section else len(text)
    return text[start:end].strip()


def _assemble_report(
    sections: Dict[int, str],
    repo_name: str,
    model: str,
    generated_at: str,
) -> str:
    """
    Re-assemble all sections in canonical order 1–13.
    Adds a metadata header and ensures every section heading is correctly numbered.
    """
    lines = [
        "# Project Documentation",
        "",
        f"> **Repository:** `{repo_name}`  ",
        f"> **Generated:** {generated_at}  ",
        f"> **Engine:** AutoDocx Multi-Agent · {model}",
        "",
        "---",
        "",
    ]

    for num in range(1, 14):
        title = _SECTION_TITLES[num]
        body = sections.get(num, "")
        lines.append(f"## {num}. {title}")
        lines.append("")
        if body:
            lines.append(body)
        else:
            lines.append(
                f"*Section {num} ({title}) — information not available for this repository.*"
            )
        lines.append("")
        lines.append("---")
        lines.append("")

    return "\n".join(lines)


# ── Diagram generation ────────────────────────────────────────────────────────


def generate_gemini_diagrams(readme_ctx: str, files_ctx: str, deps_ctx: str) -> str:
    """Use Gemini to generate high-quality Mermaid diagrams."""
    if not os.getenv("GEMINI_API_KEY"):
        return ""
    try:
        try:
            model = genai.GenerativeModel("gemini-2.5-flash")
        except Exception:
            model = genai.GenerativeModel("gemini-1.5-flash")
    except Exception as e:
        logger.warning(f"Could not initialize Gemini: {e}")
        return ""

    prompt = (
        "You are an expert software architect. Analyze the project context and generate TWO Mermaid diagrams.\n"
        "1. A 'Use Case Diagram' using `flowchart LR`. Show actors (User, Admin) on the left and system actions on the right. Max 10 nodes. No parentheses in node labels.\n"
        "2. A 'Core System Flow' using `sequenceDiagram`. Max 6 steps.\n"
        "Rules:\n"
        "- Output ONLY the two ```mermaid blocks. No other text whatsoever.\n"
        "- No parentheses inside flowchart node labels — use square brackets only.\n"
        "- Keep labels short (max 5 words).\n\n"
        f"README:\n{readme_ctx[:2000]}\n\nFILES:\n{files_ctx[:2000]}\n\nDEPS:\n{deps_ctx[:1000]}"
    )
    try:
        response = model.generate_content(prompt)
        text = response.text.strip()
        if "```mermaid" in text:
            return text
        return ""
    except Exception as e:
        logger.warning(f"Gemini diagram generation failed: {e}")
        return ""


def _ollama_use_case_diagram(
    client, model: str, temperature: float, readme_ctx: str, files_ctx: str
) -> str:
    """Fallback: ask Ollama for a use case diagram when Gemini is not available."""
    prompt = (
        "Generate a Mermaid use case diagram for this project using `flowchart LR`.\n"
        "Rules:\n"
        "- Use actors: User, Admin\n"
        "- Show 6-8 system actions as rectangular nodes\n"
        "- No parentheses in node labels — use only square brackets\n"
        "- Output ONLY the ```mermaid code block. Nothing else.\n\n"
        f"README:\n{readme_ctx[:1500]}\nFILES:\n{files_ctx[:1500]}"
    )
    system = "You are an expert software architect. Return ONLY a Mermaid code block. No prose."
    return _chat_completion(client, model, system, prompt, temperature, max_tokens=600)


# ── Main report builder ───────────────────────────────────────────────────────


def build_prompt(parsed: Dict) -> str:
    """Build a comprehensive single-pass prompt (legacy / fallback path)."""
    repo_path = Path(parsed.get("repo_path", "."))
    readme = load_readme(repo_path)
    files = parsed.get("files", [])
    stats = parsed.get("stats", {})
    package_json = load_package_json(repo_path)
    requirements = load_requirements_txt(repo_path)
    pom_xml = load_pom_xml(repo_path)
    folder_tree = load_folder_tree(repo_path)

    deps_ctx = build_deps_context(repo_path, package_json, requirements, pom_xml)

    parts = [
        "You are a senior software architect and technical writer. "
        "Generate professional documentation in Markdown. "
        "Return sections STRICTLY in order 1 through 13. "
        "Do not reorder sections. Do not skip sections.",
        "\nReturn documentation in EXACTLY this format:\n\n"
        "# Project Documentation\n\n"
        "## 1. Project Overview\n"
        "## 2. System Architecture\n"
        "  Include: ### Use Case Diagram (Mermaid flowchart LR — no parentheses in labels)\n"
        "  Include: ### Technology Stack table\n"
        "## 3. Functional Requirements\n"
        "## 4. Non-Functional Requirements\n"
        "## 5. System Design\n"
        "  Include: ### Database Design and ### API Design (endpoint table)\n"
        "## 6. Folder Structure\n"
        "  Use the exact tree provided in context — do not truncate or summarize it.\n"
        "## 7. Features\n"
        "## 8. User Guide\n"
        "## 9. Testing\n"
        "## 10. Deployment\n"
        "## 11. Security Considerations\n"
        "## 12. Future Improvements\n"
        "## 13. References\n",
        f"\n---\n## Repository Statistics:\n{summarize_stats(stats)}",
        f"\n---\n## Code Structure:\n{summarize_files(files, 50)}",
        f"\n---\n## Folder Tree (use verbatim in Section 6):\n```\n{folder_tree}\n```",
        f"\n---\n## Dependencies:\n{deps_ctx}",
    ]
    if readme:
        parts.append(f"\n---\n## README:\n{chr(10).join(readme.splitlines()[:250])}")
    parts.append("\n---\nGenerate the documentation now.")
    return "\n".join(parts)


def generate_llm_report(prompt: str, model: Optional[str] = None) -> str:
    """Single-pass LLM report generation via Ollama."""
    model = model or os.getenv("OLLAMA_MODEL", "qwen2.5:14b")
    temperature = float(os.getenv("OLLAMA_TEMPERATURE", "0.3"))
    max_tokens = int(os.getenv("OLLAMA_MAX_TOKENS", "12000"))

    system_content = (
        "You are a senior software architect. Produce documentation in strict Markdown. "
        "Sections MUST appear in order 1–13. Never reorder or skip sections. "
        "Use the exact folder tree from context in Section 6 — never truncate it. "
        "Embed the use case diagram inside Section 2. "
        "Do not add extra sections outside the 13 defined."
    )
    try:
        client = _create_ollama_client()
        return _chat_completion(
            client, model, system_content, prompt, temperature, max_tokens
        )
    except Exception as e:
        logger.error(f"Ollama error: {e}", exc_info=True)
        raise RuntimeError(
            "Error calling Ollama. Ensure it is running and the model is available."
        ) from e


def _split_text_batches(text: str, chunk_chars: int, max_batches: int) -> List[str]:
    if not text or len(text) <= chunk_chars:
        return [text] if text else []
    lines = text.splitlines(keepends=True)
    batches, current, current_len = [], [], 0
    for line in lines:
        if current and current_len + len(line) > chunk_chars:
            batches.append("".join(current))
            current, current_len = [], 0
        current.append(line)
        current_len += len(line)
        if len(batches) >= max_batches:
            break
    if current and len(batches) < max_batches:
        batches.append("".join(current))
    return batches


# ── Multi-agent comprehensive report ─────────────────────────────────────────


def generate_comprehensive_report(
    parsed: Dict,
    progress_callback=None,
    model: Optional[str] = None,
) -> str:
    """
    Multi-agent report generation.

    Agents:
      PM Agent      → Sections 1, 3, 4, 7, 8
      Arch Agent    → Sections 2, 5, 6  (with diagrams embedded in §2)
      QA Agent      → Sections 9, 10, 11, 12, 13

    After all three agents complete, a final assembly pass:
      - Extracts each section from agent outputs via regex
      - Re-orders them 1–13 in strict sequence
      - Injects the folder tree verbatim into Section 6 if the LLM truncated it
      - Injects diagrams into Section 2
      - Adds metadata header
    """
    model = model or os.getenv("OLLAMA_MODEL", "qwen2.5:7b")
    temperature = float(os.getenv("OLLAMA_TEMPERATURE", "0.3"))
    max_tokens = int(os.getenv("OLLAMA_MAX_TOKENS", "4000"))
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    repo_path = Path(parsed.get("repo_path", "."))
    readme = load_readme(repo_path)
    files = parsed.get("files", [])
    stats = parsed.get("stats", {})
    package_json = load_package_json(repo_path)
    requirements = load_requirements_txt(repo_path)
    pom_xml = load_pom_xml(repo_path)

    logger.info(
        f"Generating comprehensive report for {repo_path.name} with model={model}"
    )
    client = _create_ollama_client()

    def _notify(msg, progress):
        logger.info(msg)
        if progress_callback:
            progress_callback(msg, progress)

    # ── Build context blocks ──────────────────────────────────────────────────
    repo_stats_ctx = summarize_stats(stats)
    files_ctx = summarize_files(files, limit=80)
    readme_ctx = "\n".join(readme.splitlines()[:300]) if readme else "No README found."
    deps_ctx = build_deps_context(repo_path, package_json, requirements, pom_xml)
    folder_tree = load_folder_tree(repo_path, max_lines=150)
    repo_name = repo_path.name

    general_system = (
        "Return well-formatted Markdown only. No introductory chatter. "
        "Ground output in repository evidence. When information is missing, "
        "state reasonable assumptions and label them as [Assumption]. "
        "Never invent dependencies not present in the context."
    )

    # ── Agent 1: PM ───────────────────────────────────────────────────────────
    _notify(
        "Agent 1/3: Product Manager — Overview, Requirements, Features, User Guide…", 62
    )

    pm_prompt = (
        "You are an expert Technical Product Manager.\n"
        "Write ONLY these sections (no others):\n\n"
        "## 1. Project Overview\n"
        "Include: Project Name, Description, Problem Statement, Objectives, Scope.\n\n"
        "## 3. Functional Requirements\n"
        "Use a table: | ID | Requirement |\n\n"
        "## 4. Non-Functional Requirements\n"
        "Bullet points for: Performance, Security, Usability, Maintainability, Scalability.\n\n"
        "## 7. Features\n"
        "Grouped bullet points.\n\n"
        "## 8. User Guide\n"
        "Step-by-step numbered list.\n\n"
        f"--- CONTEXT ---\n"
        f"README:\n{readme_ctx}\n\n"
        f"STATS:\n{repo_stats_ctx}\n\n"
        f"FILES SUMMARY:\n{files_ctx[:2000]}"
    )
    part_pm = _chat_completion(
        client,
        model,
        "You are a Technical Product Manager. " + general_system,
        pm_prompt,
        temperature,
        max_tokens,
    )

    # ── Agent 2: Architect ────────────────────────────────────────────────────
    _notify("Agent 2/3: System Architect — Architecture, Design, Folder Structure…", 73)

    arch_prompt = (
        "You are an expert System Architect.\n"
        "Write ONLY these sections (no others):\n\n"
        "## 2. System Architecture\n"
        "Include:\n"
        "### High-Level Architecture\n"
        "(describe the layers)\n"
        "### Components\n"
        "(list each component)\n"
        "### Use Case Diagram\n"
        "(Insert a Mermaid flowchart LR here — IMPORTANT: no parentheses in node labels, use only square brackets)\n"
        "### Use Case Explanations\n"
        "(4-6 bullet points explaining use cases in plain language)\n"
        "### Technology Stack\n"
        "| Layer | Technology |\n"
        "|-------|------------|\n"
        "Use ONLY technologies actually present in the codebase. Do not guess.\n\n"
        "## 5. System Design\n"
        "Provide a technical design overview including:\n"
        "### Database Design\n"
        "(describe tables, fields, and schema relationships based on context)\n"
        "### API Design\n"
        "| Endpoint | Method | Description |\n"
        "|---------|--------|-------------|\n"
        "If no specific API is found, describe the internal module communication interfaces.\n\n"
        "## 6. Folder Structure\n"
        "Use EXACTLY the folder tree below — do not modify, summarize, or truncate it:\n"
        f"```\n{folder_tree}\n```\n\n"
        f"--- CONTEXT ---\n"
        f"FILES SUMMARY:\n{files_ctx}\n\n"
        f"DEPENDENCIES:\n{deps_ctx}\n\n"
        f"STATS:\n{repo_stats_ctx}\n\n"
        f"README (for technology inference):\n{readme_ctx[:1500]}"
    )
    part_arch = _chat_completion(
        client,
        model,
        "You are a senior System Architect. " + general_system,
        arch_prompt,
        temperature,
        max_tokens,
    )

    # ── Gemini diagrams (optional upgrade to §2) ──────────────────────────────
    diagram_md = ""
    if os.getenv("GEMINI_API_KEY"):
        _notify("Agent 2.5: Gemini — Generating high-quality Mermaid diagrams…", 80)
        diagram_md = generate_gemini_diagrams(readme_ctx, files_ctx, deps_ctx)
        if diagram_md:
            logger.info("Gemini diagrams generated — will inject into Section 2.")
    else:
        # Fallback: ask Ollama for the use case diagram
        _notify("Agent 2.5: Generating use case diagram via Ollama…", 80)
        diagram_md = _ollama_use_case_diagram(
            client, model, temperature, readme_ctx, files_ctx
        )

    # ── Agent 3: QA & DevOps ──────────────────────────────────────────────────
    _notify("Agent 3/3: QA & DevOps — Testing, Deployment, Security…", 85)

    qa_prompt = (
        "You are an expert QA & DevOps Engineer.\n"
        "Write ONLY these sections (no others):\n\n"
        "## 9. Testing\n"
        "### Testing Types\n"
        "- Unit Testing\n- Integration Testing\n- System Testing\n\n"
        "### Test Cases\n"
        "Provide EXACTLY 5 high-level test cases (not file-level):\n"
        "| Test Case ID | Test Scenario | Expected Result | Actual Result | Pass/Fail |\n"
        "|--------------|---------------|-----------------|---------------|-----------|\n\n"
        "## 10. Deployment\n"
        "Describe architecture and tools (Docker, Cloud, CI/CD).\n\n"
        "## 11. Security Considerations\n"
        "Cover: Authentication, SQL injection prevention, XSS, session management, data protection.\n\n"
        "## 12. Future Improvements\n"
        "5-8 bullet points.\n\n"
        "## 13. References\n"
        "List libraries, tools, and external resources actually used.\n\n"
        f"--- CONTEXT ---\n"
        f"FILES SUMMARY:\n{files_ctx}\n\n"
        f"DEPENDENCIES:\n{deps_ctx}\n\n"
        f"README:\n{readme_ctx[:1500]}"
    )
    part_qa = _chat_completion(
        client,
        model,
        "You are a senior QA & DevOps Engineer. " + general_system,
        qa_prompt,
        temperature,
        max_tokens,
    )

    # ── Assembly pass ─────────────────────────────────────────────────────────
    _notify("Assembling and ordering final report (sections 1–13)…", 93)

    all_text = f"{part_pm}\n\n{part_arch}\n\n{part_qa}"

    # Extract each section from agent outputs
    sections: Dict[int, str] = {}
    for num in range(1, 14):
        body = _extract_section(all_text, num)
        if body:
            sections[num] = body

    # ── Post-process Section 2: embed diagrams ────────────────────────────────
    if diagram_md:
        sec2 = sections.get(2, "")
        # If the LLM already wrote a use case diagram block, replace it; else append
        if "```mermaid" in sec2:
            # Replace the existing mermaid block(s) with Gemini's version
            sec2 = re.sub(r"```mermaid.*?```", "", sec2, flags=re.DOTALL).strip()
        # Inject diagrams after the "Use Case Diagram" heading if present, else append
        uc_heading = re.search(r"###\s+Use Case Diagram", sec2, re.IGNORECASE)
        if uc_heading:
            insert_pos = uc_heading.end()
            sec2 = sec2[:insert_pos] + "\n\n" + diagram_md + "\n\n" + sec2[insert_pos:]
        else:
            sec2 = sec2 + "\n\n### Use Case Diagram\n\n" + diagram_md
        sections[2] = sec2

    # ── Post-process Section 6: inject full folder tree if LLM truncated ─────
    sec6 = sections.get(6, "")
    # Check if folder tree is present and looks complete
    if folder_tree and ("```" not in sec6 or len(sec6) < len(folder_tree) // 2):
        sections[6] = f"```\n{folder_tree}\n```"

    # ── Final assembly ────────────────────────────────────────────────────────
    report = _assemble_report(sections, repo_name, model, generated_at)

    _notify("Report complete ✓", 100)
    logger.info(f"Report assembled: {len(report)} chars, {len(report.split())} words")
    return report


def generate_markdown_report(parsed: Dict, include_llm: bool = False) -> str:
    """Lightweight structured report without LLM (for offline/fallback use)."""
    repo_path = Path(parsed.get("repo_path", "."))
    files = parsed.get("files", [])
    stats = parsed.get("stats", {})
    readme = load_readme(repo_path)
    package_json = load_package_json(repo_path)
    requirements = load_requirements_txt(repo_path)
    folder_tree = load_folder_tree(repo_path)

    report = [
        "# Project Documentation",
        f"\n*Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*\n",
        "## 1. Project Overview",
    ]
    if readme:
        report.append("\n" + "\n".join(readme.splitlines()[:50]))
    else:
        report.append(
            "\n*No README found. Documentation generated from code analysis.*"
        )

    report += [
        "\n## 2. Project Statistics",
        f"- **Total Files Analyzed:** {stats.get('total_considered', 0)}",
        f"- **Successfully Scanned:** {stats.get('scanned', 0)}",
        f"- **Skipped:** {stats.get('skipped', 0)}",
        f"- **Errors:** {stats.get('errors', 0)}",
    ]
    if stats.get("by_language"):
        report.append("\n### Language Distribution")
        for lang, count in stats["by_language"].items():
            report.append(f"- **{lang}:** {count} files")
    if stats.get("largest_files"):
        report.append("\n### Largest Files")
        for path, size in stats["largest_files"]:
            report.append(f"- `{path}` ({round(size/1024, 1)} KB)")

    report.append("\n## 3. Technology Stack")
    languages = list(stats.get("by_language", {}).keys())
    if languages:
        report.append(f"**Languages:** {', '.join(languages)}")
    if package_json:
        deps = list(package_json.get("dependencies", {}).keys())[:20]
        if deps:
            report.append("\n### Node.js Dependencies\n" + ", ".join(deps))
    if requirements:
        report.append(
            "\n### Python Dependencies\n"
            + "\n".join(f"- {r}" for r in requirements[:30])
        )

    report.append("\n## 4. Folder Structure\n```")
    report.append(folder_tree)
    report.append("```")

    report.append("\n## 5. Key Files and Structure")
    for file_info in [f for f in files if not f.get("skipped") and not f.get("error")][
        :30
    ]:
        report.append(f"\n### `{file_info.get('path', 'unknown')}`")
        report.append(f"- **Language:** {file_info.get('language', 'unknown')}")
        if file_info.get("classes"):
            report.append(f"- **Classes:** {', '.join(file_info['classes'][:5])}")
        if file_info.get("functions"):
            report.append(f"- **Functions:** {', '.join(file_info['functions'][:5])}")

    report.append("\n---\n*This report was automatically generated by AutoDocx.*")
    return "\n".join(report)
