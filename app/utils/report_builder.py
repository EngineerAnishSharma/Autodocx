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
    prompt_parts.append("You are an expert software documentation writer. Your task is to create comprehensive, "
                       "professional documentation for a software project that will help new developers understand "
                       "and contribute to the project quickly.")
    
    prompt_parts.append("\n## Instructions:")
    prompt_parts.append("Generate a detailed project documentation report in Markdown format with the following sections:")
    prompt_parts.append("1. **Project Overview** - Brief description of what the project does")
    prompt_parts.append("2. **Key Features** - Main functionalities and capabilities")
    prompt_parts.append("3. **Project Structure** - High-level architecture and organization")
    prompt_parts.append("4. **Technology Stack** - Languages, frameworks, and tools used")
    prompt_parts.append("5. **Dependencies** - Key libraries and packages")
    prompt_parts.append("6. **Important Files** - Critical files and their purposes")
    prompt_parts.append("7. **Setup & Installation** - How to set up and run the project")
    prompt_parts.append("8. **Usage Guide** - How to use the project")
    prompt_parts.append("9. **Development Guidelines** - For contributors")
    prompt_parts.append("10. **Known Issues & Future Improvements** - Current limitations and planned features")
    
    prompt_parts.append("\nKeep the documentation clear, concise, and actionable. Use proper Markdown formatting.")
    
    prompt_parts.append("\n---\n## Repository Statistics:")
    prompt_parts.append(summarize_stats(stats))
    
    prompt_parts.append("\n---\n## Code Structure Analysis:")
    prompt_parts.append(summarize_files(files, limit=30))
    
    if readme:
        prompt_parts.append("\n---\n## Existing README Content:")
        prompt_parts.append("\n".join(readme.splitlines()[:100]))
    
    if package_json:
        prompt_parts.append("\n---\n## Package.json Information:")
        prompt_parts.append(f"Name: {package_json.get('name', 'N/A')}")
        prompt_parts.append(f"Version: {package_json.get('version', 'N/A')}")
        prompt_parts.append(f"Description: {package_json.get('description', 'N/A')}")
        if package_json.get('dependencies'):
            prompt_parts.append(f"Dependencies: {', '.join(list(package_json.get('dependencies', {}).keys())[:20])}")
    
    if requirements:
        prompt_parts.append("\n---\n## Python Dependencies:")
        prompt_parts.append("\n".join(requirements[:30]))
    
    if pom_xml:
        prompt_parts.append("\n---\n## Maven Configuration (pom.xml excerpt):")
        prompt_parts.append(pom_xml[:500])
    
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
                {"role": "system", "content": "You are an expert technical documentation writer. Create comprehensive, "
                 "well-structured documentation that helps developers understand and work with the project effectively."},
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