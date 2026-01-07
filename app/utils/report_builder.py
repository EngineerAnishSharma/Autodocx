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
from config import OPENAI_API_KEY, OPENAI_MODEL, OPENAI_MAX_TOKENS, OPENAI_TEMPERATURE

load_dotenv()

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
        "You are an expert software documentation writer. Your task is to create **comprehensive, detailed, and practical** "
        "documentation for this project. The documentation should be **3-4 pages long** (approximately 2000-3000 words) "
        "and contain ALL essential information a new developer needs to understand, set up, and work with this project."
    )
    
    prompt_parts.append("\n## Instructions:")
    prompt_parts.append(
        "Generate a **comprehensive and detailed** project documentation report in **Markdown** format. "
        "The documentation must be **3-4 pages long** with extensive details. Include the following sections "
        "with thorough explanations (avoid marketing language, be technical and specific):"
    )
    prompt_parts.append("1. **Project Overview** – What the project does, who it is for, and the main problem it solves.")
    prompt_parts.append(
        "2. **Key Features & Use Cases** – Bullet list of main features and typical real-world usage scenarios."
    )
    prompt_parts.append(
        "3. **Architecture & Project Structure** – High-level diagram in text plus explanation of how the "
        "frontend, backend, services, and data stores interact. Summarize important folders and how code is organized."
    )
    prompt_parts.append(
        "4. **Technology Stack** – Languages with **specific version numbers** (e.g., Python 3.9, Node.js 18.x), "
        "frameworks with versions, major libraries with versions, and any external services (APIs, databases, queues). "
        "Include version requirements for all critical technologies."
    )
    prompt_parts.append(
        "5. **Dependencies** – **Complete list** of important Python/Node/Java/etc dependencies from package.json, "
        "requirements.txt, or pom.xml with **exact version numbers** and brief explanations of what each dependency "
        "is used for. Group by category (e.g., web framework, database, testing, utilities)."
    )
    prompt_parts.append(
        "6. **Important Modules & Files** – For the most important files detected, explain their roles, key classes/"
        "functions inside them, and how they fit into the overall flow."
    )
    prompt_parts.append(
        "7. **Configuration & Environment** – Describe expected environment variables, config files, and any secrets "
        "or API keys needed (without revealing real values)."
    )
    prompt_parts.append(
        "8. **Setup & Installation** – Step‑by‑step instructions to run the project locally from a fresh clone. "
        "Include commands to install dependencies, migrations (if any), and how to start each service."
    )
    prompt_parts.append(
        "9. **Usage Guide** – How to interact with the running app (CLI commands, API endpoints, web UI flows). "
        "Mention at least the main entrypoints a developer should try."
    )
    prompt_parts.append(
        "10. **Development Guidelines** – Coding conventions, project layout rules, how to add a new feature, run tests, "
        "and where to put new code."
    )
    prompt_parts.append(
        "11. **Limitations, Risks & Next Steps** – Known issues, technical debt, and sensible next improvements."
    )
    
    prompt_parts.append(
        "\n**Documentation Requirements:**\n"
        "- The documentation must be **comprehensive and detailed** (3-4 pages, approximately 2000-3000 words).\n"
        "- Include **specific version numbers** for all technologies, frameworks, and major dependencies.\n"
        "- Provide **detailed explanations** for each section - don't be brief.\n"
        "- Use clear structure with proper Markdown headings, bullet lists, and code blocks where appropriate.\n"
        "- Include **concrete examples** and **step-by-step instructions** where relevant.\n"
        "- If something is unknown from the code, say \"Not clearly inferable from repository\" instead of guessing.\n"
        "- Be thorough: explain architecture patterns, data flow, key algorithms, API endpoints, database schemas, etc."
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


def generate_llm_report(prompt: str, model: Optional[str] = None) -> str:
    """Call OpenAI-compatible client if available; otherwise raise a clear error."""
    api_key = OPENAI_API_KEY or os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY not set in environment variables. Please set it to use LLM report generation.")
    
    model = model or OPENAI_MODEL
    
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise RuntimeError("openai package not installed. Run: pip install openai") from exc
    
    try:
        logger.info(f"Generating LLM report using model: {model}")
        client = OpenAI(api_key=api_key)
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an expert technical documentation writer. "
                        "Create comprehensive, detailed documentation (3-4 pages, 2000-3000 words) that includes:\n"
                        "- ALL essential information: technology versions, complete dependency lists, architecture details.\n"
                        "- Specific version numbers for all technologies, frameworks, and major dependencies.\n"
                        "- Step-by-step setup instructions with exact commands.\n"
                        "- Detailed explanations of code structure, key files, and their purposes.\n"
                        "- Usage examples, API endpoints, configuration details.\n"
                        "- Development guidelines and contribution instructions.\n"
                        "Be thorough, specific, and technical. Include concrete examples and code snippets where relevant."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            temperature=OPENAI_TEMPERATURE,
            max_tokens=OPENAI_MAX_TOKENS,
        )
        content = resp.choices[0].message.content
        logger.info("LLM report generated successfully")
        return content.strip() if content else ""
    except Exception as e:
        logger.error(f"Error calling OpenAI API: {e}", exc_info=True)
        raise RuntimeError(f"Error calling OpenAI API: {str(e)}") from e


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