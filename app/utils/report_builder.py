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
- Section 2 always has prose content before diagrams (never blank page)
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
        # Asset / screenshot folders are omitted entirely to keep the tree tight.
        "img",
        "image",
        "images",
        "assets",
        "static",
        "media",
        "screen",
        "screens",
        "screenshots",
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
                lines.append(
                    f"{prefix}    ... (tree truncated for brevity — see repository for full structure)"
                )
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
        r"^#{1,3}\s+(?:\d+[.)]\s+)?(?:System Design|Architecture Design|Design Overview|Technical Design|Application Design|Design Details)",
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

    for canonical_num in range(1, 14):
        # Use the canonical section numbers 1–13 directly so the report
        # always shows the full list of points, including a dedicated
        # Non-Functional Requirements section and a References section.
        display_num = canonical_num
        title = _SECTION_TITLES.get(canonical_num, f"Section {canonical_num}")
        body = sections.get(canonical_num, "")
        lines.append(f"## {display_num}. {title}")
        lines.append("")
        if body:
            lines.append(body)
        else:
            # Friendly, styled fallbacks that render as info cards in the PDF.
            if canonical_num == 5:
                lines.append(
                    "> **Info:** System design details could not be confidently inferred from this repository. "
                    "Review the architecture and code structure sections for implementation insights."
                )
            else:
                lines.append(
                    f"> **Info:** Section {display_num} ({title}) — information not available for this repository."
                )
        lines.append("")
        lines.append("---")
        lines.append("")

    return "\n".join(lines)


# ── Diagram generation ────────────────────────────────────────────────────────


def _infer_actors(files_ctx: str, readme_ctx: str) -> List[str]:
    """
    Infer likely actors from repository context instead of hard-coding User/Admin.
    Returns a short list of canonical actor labels.
    """
    actors: List[str] = []
    combined = (files_ctx + readme_ctx).lower()

    candidate_actors = {
        "User": ["user", "member", "customer", "client", "subscriber"],
        "Admin": ["admin", "administrator", "superuser", "manager"],
        "Guest": ["guest", "visitor", "anonymous", "public"],
        "Operator": ["operator", "staff", "agent", "moderator"],
        "System": ["cron", "scheduler", "daemon", "worker", "job"],
        "API Client": ["api", "webhook", "external", "third-party", "oauth"],
    }

    for actor, keywords in candidate_actors.items():
        if any(kw in combined for kw in keywords):
            actors.append(actor)

    if not actors:
        return ["Client", "System"]
    return actors[:3]


def _select_diagram_types(
    files_ctx: str, readme_ctx: str, deps_ctx: str
) -> List[Dict[str, str]]:
    """
    Return three fixed diagram specs used for all repositories. Their _type_
    and high-level intent are stable so the PDF layout is predictable; the
    actual nodes/labels still depend on repo context.
    """
    return [
        {
            "title": "Architecture Layers",
            "description": "Show the high-level architecture layers (UI, Logic, Data) and their connections.",
            "mermaid_type": "flowchart TD",
            "style": "layers",
        },
        {
            "title": "Core Interaction Flow",
            "description": "Show the sequence of a core interaction through the system (e.g., Request -> Response).",
            "mermaid_type": "sequenceDiagram",
            "style": "sequence",
        },
        {
            "title": "Use Case Diagram",
            "description": "Show key actors and the main functional actions they perform.",
            "mermaid_type": "flowchart LR",
            "style": "use_case",
        },
        {
            "title": "Entity Relationship Diagram",
            "description": "Show the main data entities, attributes, and relationships.",
            "mermaid_type": "erDiagram",
            "style": "er",
        },
    ]


def generate_gemini_diagrams(readme_ctx: str, files_ctx: str, deps_ctx: str) -> str:
    """
    Generate up to 3 context-aware Mermaid diagrams using Gemini.
    Diagram types are chosen based on what the repo actually contains.
    Returns a markdown string with labelled mermaid blocks.
    """
    if not os.getenv("GEMINI_API_KEY"):
        return ""

    actors = _infer_actors(files_ctx, readme_ctx)
    diagram_specs = _select_diagram_types(files_ctx, readme_ctx, deps_ctx)
    actors_str = ", ".join(actors)

    diagram_instructions = []
    for i, spec in enumerate(diagram_specs, 1):
        diagram_instructions.append(
            f"DIAGRAM {i}: \"{spec['title']}\"\n"
            f"  - Type: `{spec['mermaid_type']}`\n"
            f"  - Goal: {spec['description']}\n"
            f"  - Inferred actors/participants (use ONLY if relevant): {actors_str}\n"
            f"  - Max nodes/steps: 10\n"
        )

    diagrams_block = "\n".join(diagram_instructions)

    prompt = (
        "You are an expert software architect. Analyze the project context below and "
        "generate exactly 4 high-quality Mermaid diagrams.\n\n"
        "DIAGRAM SPECIFICATIONS:\n"
        f"{diagrams_block}\n"
        "STRICT RULES:\n"
        "1. Output ONLY the 4 mermaid code blocks with their labels. No prose, no explanation.\n"
        "2. Before each ```mermaid block, write the label line exactly like: ### <diagram title>\n"
        "3. Use ONLY actors/entities that are ACTUALLY present in the codebase below.\n"
        "4. No parentheses inside flowchart node labels — use square brackets [ ].\n"
        "5. Keep labels short: max 4 words per node.\n"
        "6. For sequenceDiagram: max 8 messages.\n"
        "7. For flowchart: max 12 nodes.\n"
        "8. Every diagram must render valid Mermaid syntax.\n\n"
        "EXPECTED OUTPUT FORMAT (follow exactly):\n"
        "### <diagram title>\n```mermaid\n...\n```\n(repeated 4 times)\n\n"
        f"PROJECT CONTEXT:\nREADME:\n{readme_ctx[:2000]}\n\n"
        f"FILES SUMMARY:\n{files_ctx[:2500]}\n\n"
        f"DEPENDENCIES:\n{deps_ctx[:1000]}\n"
    )

    try:
        try:
            model = genai.GenerativeModel("gemini-2.5-flash")
        except Exception:
            model = genai.GenerativeModel("gemini-1.5-flash")
        response = model.generate_content(
            prompt,
            generation_config={"temperature": 0.05},
        )
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
    """
    Fallback: generate up to 3 context-aware Mermaid diagrams via Ollama when
    Gemini is not available.
    """
    actors = _infer_actors(files_ctx, readme_ctx)
    diagram_specs = _select_diagram_types(files_ctx, readme_ctx, "")
    actors_str = ", ".join(actors)

    specs_text = "\n".join(
        [
            f"Diagram {i}: \"{s['title']}\" — {s['description']} — Use `{s['mermaid_type']}`"
            for i, s in enumerate(diagram_specs, 1)
        ]
    )

    prompt = (
        "Generate 4 Mermaid diagrams for this project.\n\n"
        "Diagrams needed:\n"
        f"{specs_text}\n\n"
        f"Inferred actors (use only what is actually present): {actors_str}\n\n"
        "Rules:\n"
        "- Label each diagram with ### <title> before its code block.\n"
        "- No parentheses in flowchart labels — square brackets only.\n"
        "- Max 10 nodes per diagram.\n"
        "- Output ONLY the 4 labelled mermaid blocks. Nothing else.\n\n"
        f"README:\n{readme_ctx[:1200]}\n\n"
        f"FILES:\n{files_ctx[:1200]}\n"
    )
    system = (
        "You are a software architect. Output ONLY labelled Mermaid code blocks. No prose."
    )
    # Use a very low temperature here to keep diagrams stable across runs.
    return _chat_completion(client, model, system, prompt, temperature=0.05, max_tokens=1200)


# ── Section 2 prose fallback ──────────────────────────────────────────────────

def _sec2_prose_fallback(files_ctx: str, deps_ctx: str, readme_ctx: str) -> str:
    """
    Build a minimal but meaningful Section 2 prose body when the LLM either
    produced nothing or the content was fully stripped during post-processing.

    This guarantees the PDF never shows a blank page between the
    '2. System Architecture' heading and the first diagram page.
    """
    # Try to detect the rough tech stack from deps/files context for a
    # slightly personalised fallback rather than pure boilerplate.
    combined = (files_ctx + deps_ctx + readme_ctx).lower()

    frontend = []
    backend = []
    database = []

    if "react" in combined:
        frontend.append("React")
    if "vue" in combined:
        frontend.append("Vue.js")
    if "angular" in combined:
        frontend.append("Angular")
    if "html" in combined or "css" in combined:
        frontend.append("HTML / CSS")
    if "bootstrap" in combined:
        frontend.append("Bootstrap")

    if "spring" in combined:
        backend.append("Spring / Spring Boot")
    if "django" in combined or "flask" in combined or "fastapi" in combined:
        backend.append("Python web framework")
    if "express" in combined or "node" in combined:
        backend.append("Node.js / Express")
    if "java" in combined and "spring" not in combined:
        backend.append("Java (Servlets / JSP)")
    if "servlet" in combined:
        backend.append("Java Servlets")
    if "jsp" in combined:
        backend.append("JSP")

    if "mysql" in combined:
        database.append("MySQL")
    if "postgresql" in combined or "postgres" in combined:
        database.append("PostgreSQL")
    if "mongodb" in combined:
        database.append("MongoDB")
    if "sqlserver" in combined or "mssql" in combined or "sqljdbc" in combined:
        database.append("SQL Server")
    if "sqlite" in combined:
        database.append("SQLite")

    lines = [
        "### High-Level Architecture",
        "",
        "The system follows a layered architecture separating presentation, "
        "business logic, and data access concerns. Each layer communicates "
        "through well-defined interfaces to promote maintainability and testability.",
        "",
        "### Components",
        "",
    ]

    if frontend:
        lines.append(f"- **Presentation Layer:** {', '.join(frontend)}")
    else:
        lines.append("- **Presentation Layer:** User interface components")

    if backend:
        lines.append(f"- **Business Logic Layer:** {', '.join(backend)}")
    else:
        lines.append("- **Business Logic Layer:** Application controllers and services")

    if database:
        lines.append(f"- **Data Access Layer:** {', '.join(database)}")
    else:
        lines.append("- **Data Access Layer:** Persistent data storage")

    lines += [
        "",
        "### Technology Stack",
        "",
    ]

    if frontend:
        lines.append(f"- **Front-End:** {', '.join(frontend)}")
    if backend:
        lines.append(f"- **Back-End:** {', '.join(backend)}")
    if database:
        lines.append(f"- **Database:** {', '.join(database)}")

    if not (frontend or backend or database):
        lines.append(
            "> **Info:** Technology stack details are inferred from file extensions "
            "and dependency files present in the repository."
        )

    return "\n".join(lines)


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
    folder_tree = load_folder_tree(repo_path, max_lines=100)
    repo_name = repo_path.name

    general_system = (
        "Return well-formatted Markdown only. No introductory chatter. "
        "Ground output in repository evidence. When information is missing, "
        "state reasonable assumptions and label them as [Assumption]. "
        "CRITICAL: Every item in a list or bullet point MUST start on a completely new line. "
        "Do NOT cluster multiple points into a single paragraph."
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
        "Bullet points. Ensure each feature starts on a new line.\n\n"
        "## 8. User Guide\n"
        "Step-by-step numbered list. Ensure each step starts on a new line.\n"
        "Keep this section concise (no more than ~20 numbered steps).\n"
        "Do NOT paste full README templates or very long multi-page code blocks.\n"
        "If you include code, limit it to at most one short bash snippet (<= 10 lines).\n\n"
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

    # ── Agent 2: Architect (split into Architecture and System Design passes) ─
    arch_system = "You are a senior System Architect. " + general_system

    _notify(
        "Agent 2a: System Architect — System Architecture & Folder Structure…", 73
    )

    arch_prompt_a = (
        "You are an expert System Architect.\n"
        "Write ONLY these two sections:\n\n"
        "## 2. System Architecture\n"
        "### High-Level Architecture\n"
        "Describe the overall structure (layers, modules, services) in 2–4 short paragraphs.\n"
        "Focus on what runs in the browser/client, what runs on the server, and what persists data.\n"
        "Do NOT include any Mermaid, diagrams, or code blocks here — only prose and bullet lists.\n"
        "### Components\n"
        "List and describe the main technical components as bullet points.\n"
        "### Technology Stack\n"
        "List languages, frameworks, and libraries used. Use ONLY what is actually present in the\n"
        "dependencies and file extensions below. Group them under Front-End, Back-End, Database, and Tooling.\n"
        "Again, do NOT use Mermaid or code blocks — just bullets or simple lists.\n\n"
        "## 6. Folder Structure\n"
        "Use EXACTLY the folder tree below — copy it verbatim, do not modify:\n"
        f"```\n{folder_tree}\n```\n\n"
        f"--- CONTEXT ---\n"
        f"FILES: {files_ctx}\n\n"
        f"DEPS: {deps_ctx}\n\n"
        f"README: {readme_ctx[:1500]}\n"
    )
    part_arch_a = _chat_completion(
        client,
        model,
        arch_system,
        arch_prompt_a,
        temperature,
        max_tokens,
    )

    _notify("Agent 2b: System Architect — System Design…", 77)

    arch_prompt_b = (
        "You are an expert System Architect writing a technical design document.\n"
        "Write ONLY the section below. Be specific — use actual class names, package names, and\n"
        "file names from the context.\n\n"
        "## 5. System Design\n\n"
        "### Database Design\n"
        "Describe the database tables and key fields. Infer from entity classes, DAO classes, and SQL files.\n"
        "Include a simple table like:\n"
        "| Table | Key Fields | Description |\n"
        "|-------|-----------|-------------|\n"
        "If you cannot confirm exact schema, describe it conceptually and add [Assumption].\n\n"
        "### Application Layers & Request Flow\n"
        "Explain how a typical request flows through the system. Use actual class names.\n"
        "Example format:\n"
        "1. Request hits a servlet/controller (e.g., Login servlet)\n"
        "2. Servlet calls a DAO or repository\n"
        "3. DAO queries database via a connection helper (e.g., DBContext)\n"
        "4. Result mapped to an entity and returned\n\n"
        "### Endpoints / Entry Points\n"
        "| Action | Class / File | HTTP Method | Description |\n"
        "|--------|-------------|-------------|-------------|\n"
        "List the main servlet actions or API endpoints found in the codebase. If no HTTP API exists,\n"
        "list the main controller/servlet classes and what they handle.\n\n"
        "--- CONTEXT ---\n"
        "FILES SUMMARY (contains class names, methods, packages):\n"
        f"{files_ctx}\n\n"
        "FOLDER STRUCTURE (excerpt):\n"
        f"{folder_tree[:2000]}\n\n"
        "DEPENDENCIES:\n"
        f"{deps_ctx}\n\n"
        "README:\n"
        f"{readme_ctx[:1000]}\n\n"
        "IMPORTANT: You MUST write a non-empty '## 5. System Design' section with at least the\n"
        "Database Design and Application Layers subsections. Base everything on the actual files and\n"
        "classes listed above.\n"
    )
    part_arch_b = _chat_completion(
        client,
        model,
        arch_system,
        arch_prompt_b,
        temperature,
        max_tokens,
    )

    part_arch = part_arch_a + "\n\n" + part_arch_b

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
        "Provide EXACTLY 5 high-level test cases (not file-level). Do NOT assume execution results:\n"
        "| Test Case ID | Test Scenario | Expected Result |\n"
        "|--------------|---------------|-----------------|\n\n"
        "## 10. Deployment\n"
        "Describe how this project is or could realistically be deployed based on the actual repository evidence.\n"
        "- First, state what you can see directly in the repo (e.g., app server type, build tooling, any Docker / CI / cloud configs).\n"
        "- ONLY mention specific tools such as Docker, Kubernetes, Jenkins, GitHub Actions, or cloud providers if they appear in dependencies, filenames, or README.\n"
        "- If no deployment artefacts are present, propose a simple recommended deployment approach and clearly prefix it with [Assumption].\n\n"
        "## 11. Security Considerations\n"
        "Cover: Authentication, SQL injection prevention, XSS, session management, data protection.\n"
        "- Clearly separate what the codebase appears to implement from best-practice recommendations.\n"
        "- When you cannot confirm a practice from the code (e.g., HTTPS, password hashing, secure cookies), describe it as a recommendation and label with [Assumption].\n\n"
        "## 12. Future Improvements\n"
        "5-8 bullet points.\n\n"
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

    # ── Light cleanup & de-duplication across sections ─────────────────────────
    def _clean_section_text(num: int, text: str) -> str:
        if not text:
            return text
        cleaned = text.strip()
        # Drop standalone "Conclusion" headings that sometimes leak into sections
        if num not in (1, 8):
            cleaned = re.sub(
                r"^#+\s*Conclusion\s*\n+", "", cleaned, flags=re.IGNORECASE | re.MULTILINE
            )
        return cleaned.strip()

    # Compute a simple architecture signature from section 2 to help remove
    # obvious duplicates that sometimes show up in later sections.
    arch_sig = ""
    if 2 in sections:
        arch_body = sections[2]
        m = re.search(
            r"Front-?End:.*?\n.*?Back-?End:.*?\n.*?Database Management.*?\n?",
            arch_body,
            flags=re.IGNORECASE | re.DOTALL,
        )
        if m:
            arch_sig = m.group(0).strip()

    for num, txt in list(sections.items()):
        txt = _clean_section_text(num, txt)
        # Never aggressively de-duplicate System Design (§5); it legitimately
        # echoes some architecture terminology.
        if arch_sig and num not in (2, 5):
            txt = txt.replace(arch_sig, "").strip()
        sections[num] = txt

    # ── Post-process Section 2: guarantee prose + embed diagrams ─────────────
    #
    # RULE: Section 2 MUST always have readable prose content BEFORE the first
    # mermaid block.  Without this, the PDF shows a blank page between the
    # '2. System Architecture' heading and the first diagram page because
    # _render_mermaid() immediately calls add_page().
    #
    sec2 = sections.get(2, "")

    # Step 1 — strip any mermaid blocks the LLM put inside sec2; we replace
    # them with our structured, properly-labelled diagram_md below.
    if "```mermaid" in sec2:
        sec2 = re.sub(r"```mermaid.*?```", "", sec2, flags=re.DOTALL).strip()

    # Step 2 — strip stray diagram headings that would conflict with our labels.
    sec2 = re.sub(
        r"###\s+(Use Case Diagram|Core.*?Flow|Architecture.*?|System Diagrams)\s*\n",
        "",
        sec2,
        flags=re.IGNORECASE,
    ).strip()

    # Step 3 — if sec2 is still empty after stripping, inject a meaningful
    # prose fallback so the page is never blank.
    if not sec2:
        sec2 = _sec2_prose_fallback(files_ctx, deps_ctx, readme_ctx)

    # Step 4 — append diagrams after the prose (if any were generated).
    if diagram_md and diagram_md.strip():
        sections[2] = sec2 + "\n\n" + diagram_md.strip()
    else:
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