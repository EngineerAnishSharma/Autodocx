# File: app/utils/github_utils.py
"""
GitHub Integration Utilities
----------------------------
Clone and manage GitHub repositories without requiring zip uploads.
Supports public and private repos (with auth tokens).
"""
import subprocess
import shutil
from pathlib import Path
import re
from urllib.parse import urlparse
import sys

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.logger import logger
from config import MAX_EXTRACT_BYTES


def validate_github_url(url: str) -> tuple[bool, str]:
    """
    Validate if URL is a valid GitHub repository URL.
    Returns: (is_valid, error_message)
    """
    try:
        # Common GitHub URL patterns
        patterns = [
            r'^https?://github\.com/[\w-]+/[\w.-]+/?$',
            r'^https?://github\.com/[\w-]+/[\w.-]+\.git$',
            r'^git@github\.com:[\w-]+/[\w.-]+\.git$',
        ]
        
        cleaned_url = url.strip()
        
        for pattern in patterns:
            if re.match(pattern, cleaned_url, re.IGNORECASE):
                return True, ""
        
        return False, "Invalid GitHub URL format. Expected: https://github.com/username/repo"
    except Exception as e:
        logger.error(f"Error validating GitHub URL: {e}")
        return False, str(e)


def extract_repo_name(url: str) -> str:
    """
    Extract repository name from GitHub URL.
    Example: https://github.com/user/my-repo -> my-repo
    """
    try:
        # Remove trailing slashes and .git extension
        url = url.strip().rstrip('/').replace('.git', '')
        
        # Parse URL
        if url.startswith('git@'):
            # SSH format: git@github.com:user/repo
            parts = url.split(':')[-1].split('/')
        else:
            # HTTPS format: https://github.com/user/repo
            parsed = urlparse(url)
            parts = parsed.path.strip('/').split('/')
        
        if len(parts) >= 2:
            return parts[-1]
        
        return "repo"
    except Exception as e:
        logger.error(f"Error extracting repo name: {e}")
        return "repo"


def check_git_installed() -> tuple[bool, str]:
    """
    Check if git is installed and available.
    Returns: (is_installed, version_or_error)
    """
    try:
        result = subprocess.run(
            ["git", "--version"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            return True, result.stdout.strip()
        return False, "Git command failed"
    except FileNotFoundError:
        return False, "Git is not installed. Please install Git from https://git-scm.com/"
    except Exception as e:
        return False, f"Error checking Git: {str(e)}"


def get_repo_size(repo_path: Path) -> int:
    """
    Calculate total size of repository in bytes.
    """
    total_size = 0
    try:
        for file_path in repo_path.rglob('*'):
            if file_path.is_file():
                total_size += file_path.stat().st_size
    except Exception as e:
        logger.error(f"Error calculating repo size: {e}")
    return total_size


def clone_github_repo(url: str, target_dir: Path, branch: str | None = None, depth: int = 1) -> tuple[str, Path]:
    """
    Clone a GitHub repository to the specified directory.
    
    Args:
        url: GitHub repository URL
        target_dir: Directory where repo will be cloned
        branch: Specific branch to clone (optional)
        depth: Clone depth (1 for shallow clone, None for full history)
    
    Returns:
        tuple: (repo_name, repo_path)
    
    Raises:
        ValueError: If validation fails or clone operation fails
    """
    clone_path = None
    try:
        # Validate URL
        is_valid, error_msg = validate_github_url(url)
        if not is_valid:
            raise ValueError(error_msg)
        
        # Check if git is installed
        git_installed, git_info = check_git_installed()
        if not git_installed:
            raise ValueError(git_info)
        
        logger.info(f"Git version: {git_info}")
        logger.info(f"Cloning repository: {url}")
        
        # Extract repo name
        repo_name = extract_repo_name(url)
        
        # Ensure unique directory name
        clone_path = target_dir / repo_name
        counter = 1
        original_name = repo_name
        while clone_path.exists():
            repo_name = f"{original_name}_{counter}"
            clone_path = target_dir / repo_name
            counter += 1
        
        if counter > 1:
            logger.info(f"Directory exists, using new name: {repo_name}")
        
        # Prepare git clone command
        cmd = ["git", "clone"]
        
        # Add depth for shallow clone (faster, smaller)
        if depth:
            cmd.extend(["--depth", str(depth)])
        
        # Add branch if specified
        if branch:
            cmd.extend(["--branch", branch])
        
        # Add URL and target path
        cmd.extend([url, str(clone_path)])
        
        logger.info(f"Running command: {' '.join(cmd)}")
        
        # Execute clone command
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300  # 5 minute timeout
        )
        
        if result.returncode != 0:
            error_msg = result.stderr or result.stdout or "Unknown error during clone"
            logger.error(f"Git clone failed: {error_msg}")
            raise ValueError(f"Failed to clone repository: {error_msg}")
        
        logger.info(f"Successfully cloned repository to: {clone_path}")
        
        # Check repository size
        repo_size = get_repo_size(clone_path)
        logger.info(f"Repository size: {repo_size / (1024*1024):.2f} MB")
        
        if repo_size > MAX_EXTRACT_BYTES:
            # Clean up
            shutil.rmtree(clone_path, ignore_errors=True)
            raise ValueError(
                f"Repository too large: {repo_size / (1024*1024):.2f} MB. "
                f"Maximum allowed: {MAX_EXTRACT_BYTES / (1024*1024):.2f} MB."
            )
        
        # Remove .git directory to save space (optional)
        git_dir = clone_path / ".git"
        if git_dir.exists():
            logger.info("Removing .git directory to save space")
            shutil.rmtree(git_dir, ignore_errors=True)
        
        return repo_name, clone_path
        
    except subprocess.TimeoutExpired:
        error_msg = "Repository clone timed out (>5 minutes). Repository may be too large."
        logger.error(error_msg)
        # Clean up partial clone
        if clone_path and clone_path.exists():
            shutil.rmtree(clone_path, ignore_errors=True)
        raise ValueError(error_msg)
    except Exception as e:
        logger.error(f"Error cloning repository: {e}", exc_info=True)
        # Clean up on error
        if clone_path and clone_path.exists():
            shutil.rmtree(clone_path, ignore_errors=True)
        raise


def get_github_branches(url: str) -> list[str]:
    """
    Get list of available branches for a GitHub repository.
    This is a simplified version that returns empty list.
    Full implementation would require GitHub API.
    """
    # This would require GitHub API integration
    # For now, return empty list and use default branch
    return []
