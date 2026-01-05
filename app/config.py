"""
Configuration management for AutoDocx.
Centralized settings and configuration.
"""
import os
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Base paths
BASE_DIR = Path(__file__).parent.parent
APP_DIR = BASE_DIR / "app"
DATA_DIR = APP_DIR / "data"
UPLOADS_DIR = DATA_DIR / "uploads"

# Ensure directories exist
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

# File size limits
MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_BYTES", 100 * 1024 * 1024))  # 100 MB
MAX_EXTRACT_BYTES = int(os.getenv("MAX_EXTRACT_BYTES", 200 * 1024 * 1024))  # 200 MB
MAX_FILE_BYTES = int(os.getenv("MAX_FILE_BYTES", 1 * 1024 * 1024))  # 1 MB

# Parsing limits
DEFAULT_MAX_FILES = int(os.getenv("DEFAULT_MAX_FILES", 200))
MAX_FILES_LIMIT = int(os.getenv("MAX_FILES_LIMIT", 500))

# OpenAI Configuration
OPENAI_API_KEY: Optional[str] = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
OPENAI_MAX_TOKENS = int(os.getenv("OPENAI_MAX_TOKENS", 4000))
OPENAI_TEMPERATURE = float(os.getenv("OPENAI_TEMPERATURE", 0.3))

# Supported file extensions
SUPPORTED_CODE_EXTENSIONS = [
    ".py", ".js", ".jsx", ".ts", ".tsx",
    ".java", ".go", ".rs", ".cpp", ".c", ".cs"
]

# Language detection map
LANGUAGE_MAP = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".java": "java",
    ".go": "go",
    ".rs": "rust",
    ".cpp": "cpp",
    ".c": "c",
    ".cs": "csharp",
}

# Streamlit configuration
STREAMLIT_PAGE_TITLE = "AutoDocx - Intelligent Documentation Generator"
STREAMLIT_PAGE_ICON = "📚"

# Logging configuration
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_DIR = BASE_DIR / "logs"

