# File: app/utils/file_utils.py
"""
Utility functions for file operations and repository preview.
"""
from pathlib import Path
import os


def list_repo_tree(path: Path, max_entries: int = 500):
    """Return a list of pretty-printed repository file paths (limited to max_entries)."""
    out = []
    count = 0
    for root, dirs, files in os.walk(path):
        rel_root = Path(root).relative_to(path)
        indent_level = len(rel_root.parts)
        # show directory
        if rel_root != Path('.'):
            out.append(("  " * (indent_level - 1)) + f"- {rel_root.name}/")
            count += 1
            if count >= max_entries:
                out.append("... (truncated)")
                return out
        for f in files:
            out.append(("  " * indent_level) + f)
            count += 1
            if count >= max_entries:
                out.append("... (truncated)")
                return out
    if not out:
        out.append("(empty or invalid repository)")
    return out