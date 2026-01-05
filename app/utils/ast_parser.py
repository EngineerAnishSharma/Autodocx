"""
AST Parser Utility
------------------
Parses uploaded repositories to extract structure and metadata.
Supports Python, JavaScript, TypeScript, Java, and other source files.

Features:
- Detects functions, classes, and imports for Python
- Detects functions and classes for JavaScript/TypeScript
- Supports multiple languages with extensible architecture
- Skips binary and large files safely
- Better error handling and reporting
"""

import ast
import re
import sys
from pathlib import Path
from typing import Union, Dict, List, Optional

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.logger import logger
from config import MAX_FILE_BYTES, SUPPORTED_CODE_EXTENSIONS, LANGUAGE_MAP

def parse_python_ast(file_path: str) -> dict:
    """Parse a Python file using the built-in AST module."""
    try:
        with open(file_path, "rb") as f:
            data = f.read()
        if len(data) > MAX_FILE_BYTES:
            return {"language": "python", "file": file_path, "skipped": "file too large (>1MB)"}
        source = data.decode("utf-8", errors="ignore")
        tree = ast.parse(source)
        functions = [node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]
        classes = [node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)]
        imports = [node.names[0].name for node in ast.walk(tree) if isinstance(node, ast.Import)]
        return {"language": "python", "file": file_path, "functions": functions, "classes": classes, "imports": imports}
    except Exception as e:
        return {"language": "python", "file": file_path, "error": str(e)}

def parse_javascript_ast(file_path: str) -> dict:
    """Enhanced JavaScript/TypeScript parser using regex patterns."""
    try:
        with open(file_path, "rb") as f:
            data = f.read()
        if len(data) > MAX_FILE_BYTES:
            return {"language": "javascript", "file": file_path, "skipped": "file too large (>1MB)"}
        source = data.decode("utf-8", errors="ignore")
        
        # Function patterns: function name(), const name = () => {}, const name = function()
        functions = []
        functions.extend(re.findall(r'function\s+(\w+)\s*\(', source))
        functions.extend(re.findall(r'const\s+(\w+)\s*=\s*(?:\([^)]*\)\s*=>|function)', source))
        functions.extend(re.findall(r'(\w+)\s*:\s*(?:\([^)]*\)\s*=>|function)', source))
        functions = list(set(functions))  # Remove duplicates
        
        # Class patterns: class Name, export class Name
        classes = []
        classes.extend(re.findall(r'(?:export\s+)?class\s+(\w+)', source))
        classes = list(set(classes))
        
        # Import patterns: import ... from "...", require("...")
        imports = []
        imports.extend(re.findall(r'import\s+.*?\s+from\s+["\']([^"\']+)["\']', source))
        imports.extend(re.findall(r'require\s*\(["\']([^"\']+)["\']', source))
        imports = list(set(imports))
        
        return {
            "language": "javascript",
            "file": file_path,
            "functions": functions,
            "classes": classes,
            "imports": imports
        }
    except Exception as e:
        return {"language": "javascript", "file": file_path, "error": str(e)}


def parse_typescript_ast(file_path: str) -> dict:
    """Parse TypeScript files (similar to JavaScript but with TS-specific patterns)."""
    # TypeScript parsing is similar to JavaScript, but we can add TS-specific features
    result = parse_javascript_ast(file_path)
    result["language"] = "typescript"
    return result


def parse_java_ast(file_path: str) -> dict:
    """Basic Java parser using regex patterns."""
    try:
        with open(file_path, "rb") as f:
            data = f.read()
        if len(data) > MAX_FILE_BYTES:
            return {"language": "java", "file": file_path, "skipped": "file too large (>1MB)"}
        source = data.decode("utf-8", errors="ignore")
        
        # Java class pattern: public class Name, class Name
        classes = re.findall(r'(?:public\s+)?class\s+(\w+)', source)
        classes = list(set(classes))
        
        # Java method pattern: public/private ReturnType methodName(...)
        functions = re.findall(r'(?:public|private|protected)?\s*\w+\s+(\w+)\s*\([^)]*\)\s*\{', source)
        functions = list(set(functions))
        
        # Java import pattern: import package.name;
        imports = re.findall(r'import\s+([\w.]+)', source)
        imports = list(set(imports))
        
        return {
            "language": "java",
            "file": file_path,
            "functions": functions,
            "classes": classes,
            "imports": imports
        }
    except Exception as e:
        return {"language": "java", "file": file_path, "error": str(e)}

def detect_language(file_path: str) -> str:
    """Detect programming language from file extension."""
    ext = Path(file_path).suffix.lower()
    return LANGUAGE_MAP.get(ext, "unknown")


def _summarize_file(parsed: dict, root: Path, file_size: int) -> dict:
    rel_path = str(Path(parsed.get("file", "")).relative_to(root)) if parsed.get("file") else ""
    return {
        "path": rel_path,
        "language": parsed.get("language", "unknown"),
        "functions": parsed.get("functions", []) or [],
        "classes": parsed.get("classes", []) or [],
        "imports": parsed.get("imports", []) or [],
        "error": parsed.get("error"),
        "skipped": parsed.get("skipped"),
        "bytes": file_size,
    }
def parse_repo_ast(repo_path: Union[str, Path], max_files: int = 300) -> list:
    """Parse the given repository and return structured summaries."""
    results = []
    repo_path = Path(repo_path)
    logger.info(f"Starting AST parsing for repository: {repo_path} (max_files: {max_files})")

    for i, file_path in enumerate(repo_path.rglob("*")):
        if i >= max_files:
            logger.warning(f"Reached max_files limit ({max_files}), stopping parsing")
            break
        if file_path.is_file() and file_path.suffix.lower() in SUPPORTED_CODE_EXTENSIONS:
            lang = detect_language(str(file_path))
            parsed = None
            
            if lang == "python":
                parsed = parse_python_ast(str(file_path))
            elif lang == "javascript":
                parsed = parse_javascript_ast(str(file_path))
            elif lang == "typescript":
                parsed = parse_typescript_ast(str(file_path))
            elif lang == "java":
                parsed = parse_java_ast(str(file_path))
            else:
                continue

            if not parsed:
                continue

            try:
                # Handle NoneType in joins or malformed outputs
                parsed_file = parsed.get('file', '')
                if parsed_file:
                    rel_path = Path(parsed_file).relative_to(repo_path)
                else:
                    rel_path = Path('Unknown File')
                
                file_summary = f"{rel_path} | Language: {parsed.get('language', 'unknown')}"
                
                if "skipped" in parsed:
                    file_summary += f"\n  Skipped: {parsed['skipped']}"
                    logger.debug(f"Skipped file: {rel_path} - {parsed['skipped']}")
                elif "error" in parsed:
                    file_summary += f"\n  Error: {parsed['error']}"
                    logger.warning(f"Error parsing file: {rel_path} - {parsed['error']}")
                else:
                    funcs = ", ".join(parsed.get("functions", [])[:10] or [])  # Limit to 10 for readability
                    classes = ", ".join(parsed.get("classes", [])[:10] or [])
                    imports = ", ".join(parsed.get("imports", [])[:10] or [])
                    if funcs:
                        file_summary += f"\n  Functions: {funcs}"
                    if classes:
                        file_summary += f"\n  Classes: {classes}"
                    if imports:
                        file_summary += f"\n  Imports: {imports}"
                    logger.debug(f"Parsed file: {rel_path} - {len(parsed.get('functions', []))} functions, {len(parsed.get('classes', []))} classes")
                
                results.append(file_summary)
            except Exception as e:
                logger.error(f"Error processing parsed result for {file_path}: {e}", exc_info=True)
                continue

    logger.info(f"AST parsing completed: {len(results)} files parsed")
    return results


def parse_repo_ast_structured(repo_path: Union[str, Path], max_files: int = 300) -> dict:
    """Parse the repo and return per-file metadata plus repo-level stats."""
    repo_path = Path(repo_path)
    files = []
    scanned = 0
    skipped = 0
    errors = 0
    by_language = {}
    largest_files = []
    logger.info(f"Starting structured AST parsing for repository: {repo_path} (max_files: {max_files})")

    for i, file_path in enumerate(repo_path.rglob("*")):
        if i >= max_files:
            logger.warning(f"Reached max_files limit ({max_files}), stopping parsing")
            break
        if file_path.is_file() and file_path.suffix.lower() in SUPPORTED_CODE_EXTENSIONS:
            try:
                file_size = file_path.stat().st_size
                largest_files.append((str(file_path.relative_to(repo_path)), file_size))

                lang = detect_language(str(file_path))
                parsed = None
                
                if lang == "python":
                    parsed = parse_python_ast(str(file_path))
                elif lang == "javascript":
                    parsed = parse_javascript_ast(str(file_path))
                elif lang == "typescript":
                    parsed = parse_typescript_ast(str(file_path))
                elif lang == "java":
                    parsed = parse_java_ast(str(file_path))
                else:
                    continue

                if not parsed:
                    continue

                summary = _summarize_file(parsed, repo_path, file_size)
                files.append(summary)

                if summary.get("skipped"):
                    skipped += 1
                    logger.debug(f"Skipped file: {summary.get('path')}")
                elif summary.get("error"):
                    errors += 1
                    logger.warning(f"Error parsing file: {summary.get('path')} - {summary.get('error')}")
                else:
                    scanned += 1

                lang_key = summary.get("language", "unknown")
                by_language[lang_key] = by_language.get(lang_key, 0) + 1
            except Exception as e:
                errors += 1
                logger.error(f"Error processing file {file_path}: {e}", exc_info=True)
                continue

    largest_files = sorted(largest_files, key=lambda t: t[1], reverse=True)[:5]

    result = {
        "repo_path": str(repo_path),
        "files": files,
        "stats": {
            "total_considered": len(files),
            "scanned": scanned,
            "skipped": skipped,
            "errors": errors,
            "by_language": by_language,
            "largest_files": largest_files,
        },
    }
    
    logger.info(f"Structured parsing completed: {scanned} scanned, {skipped} skipped, {errors} errors")
    return result
