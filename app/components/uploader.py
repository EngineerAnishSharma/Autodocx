# File: app/components/uploader.py
"""
Uploader helper: saves uploaded file to disk and extracts zip contents safely.
Adds size limits and zip bomb guardrails.
"""
import zipfile
from pathlib import Path
import shutil
import sys

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.logger import logger
from config import MAX_UPLOAD_BYTES, MAX_EXTRACT_BYTES


def save_uploaded_file(uploaded_file, dest_path: Path):
    """Save a Streamlit UploadedFile object to dest_path."""
    try:
        file_size = getattr(uploaded_file, "size", None)
        if file_size and file_size > MAX_UPLOAD_BYTES:
            error_msg = f"Upload too large: {file_size / (1024*1024):.2f} MB. Maximum allowed: {MAX_UPLOAD_BYTES / (1024*1024):.2f} MB."
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        size_mb = f"{file_size / (1024*1024):.2f}" if file_size else "unknown"
        logger.info(f"Saving uploaded file to {dest_path} (size: {size_mb} MB)")
        with open(dest_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        logger.info(f"File saved successfully: {dest_path}")
    except Exception as e:
        logger.error(f"Error saving uploaded file: {e}", exc_info=True)
        raise


def secure_extract(zip_path: Path, extract_to: Path):
    """Extract zip while preventing path traversal and zip bombs."""
    total_uncompressed = 0
    file_count = 0
    
    try:
        logger.info(f"Extracting ZIP file: {zip_path} to {extract_to}")
        with zipfile.ZipFile(zip_path, "r") as zf:
            for member in zf.infolist():
                member_path = extract_to.joinpath(member.filename)
                
                # Prevent path traversal or absolute paths
                try:
                    resolved_member = member_path.resolve()
                    resolved_extract = extract_to.resolve()
                    if not str(resolved_member).startswith(str(resolved_extract)):
                        error_msg = f"Unsafe zip file detected (path traversal attempt): {member.filename}"
                        logger.error(error_msg)
                        raise ValueError(error_msg)
                except (ValueError, OSError) as e:
                    error_msg = f"Invalid path in ZIP file: {member.filename}"
                    logger.error(error_msg)
                    raise ValueError(error_msg) from e
                
                # Track total extracted size to guard against zip bombs
                file_size = member.file_size or 0
                total_uncompressed += file_size
                file_count += 1
                
                if total_uncompressed > MAX_EXTRACT_BYTES:
                    error_msg = f"Zip too large after extraction: {total_uncompressed / (1024*1024):.2f} MB. Maximum allowed: {MAX_EXTRACT_BYTES / (1024*1024):.2f} MB."
                    logger.error(error_msg)
                    raise ValueError(error_msg)
            
            logger.info(f"Extracting {file_count} files (total size: {total_uncompressed / (1024*1024):.2f} MB)")
            zf.extractall(path=extract_to)
            logger.info(f"Extraction completed successfully to {extract_to}")
            
    except zipfile.BadZipFile as e:
        error_msg = f"Invalid ZIP file: {e}"
        logger.error(error_msg)
        raise ValueError(error_msg) from e
    except Exception as e:
        logger.error(f"Error extracting ZIP file: {e}", exc_info=True)
        raise


def handle_uploaded_zip(uploaded_file, uploads_dir: Path):
    """Handle uploaded ZIP file: save and extract safely."""
    try:
        # Determine filename and target
        filename = uploaded_file.name
        if not filename.lower().endswith(".zip"):
            error_msg = "Only .zip files are supported."
            logger.error(error_msg)
            raise ValueError(error_msg)

        logger.info(f"Processing uploaded file: {filename}")
        
        dest_zip = uploads_dir.joinpath(filename)
        # Ensure unique filename
        counter = 1
        base = dest_zip.stem
        while dest_zip.exists():
            dest_zip = uploads_dir.joinpath(f"{base}_{counter}.zip")
            counter += 1
        
        if counter > 1:
            logger.info(f"File already exists, using new name: {dest_zip.name}")

        save_uploaded_file(uploaded_file, dest_zip)

        # Extract
        extract_folder = uploads_dir.joinpath(dest_zip.stem)
        if extract_folder.exists():
            logger.info(f"Removing existing extraction folder: {extract_folder}")
            shutil.rmtree(extract_folder)
        extract_folder.mkdir(parents=True, exist_ok=True)

        secure_extract(dest_zip, extract_folder)

        logger.info(f"Successfully processed upload: {filename} -> {extract_folder}")
        return dest_zip.name, extract_folder
        
    except Exception as e:
        logger.error(f"Error handling uploaded ZIP: {e}", exc_info=True)
        raise


def handle_github_url(github_url: str, uploads_dir: Path, branch: str | None = None):
    """
    Handle GitHub repository URL: clone and prepare for analysis.
    
    Args:
        github_url: GitHub repository URL
        uploads_dir: Directory where repo will be cloned
        branch: Specific branch to clone (optional)
    
    Returns:
        tuple: (repo_name, extract_path)
    """
    try:
        from utils.github_utils import clone_github_repo
        
        logger.info(f"Processing GitHub URL: {github_url}")
        
        # Clone repository
        repo_name, repo_path = clone_github_repo(
            url=github_url,
            target_dir=uploads_dir,
            branch=branch,
            depth=1  # Shallow clone for faster performance
        )
        
        logger.info(f"Successfully cloned GitHub repository: {repo_name} -> {repo_path}")
        return repo_name, repo_path
        
    except Exception as e:
        logger.error(f"Error handling GitHub URL: {e}", exc_info=True)
        raise

