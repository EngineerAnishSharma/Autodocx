# GitHub Integration Guide

## Overview
AutoDocx now supports **direct GitHub repository cloning** in addition to ZIP file uploads. This means you can analyze any public GitHub repository without downloading and uploading ZIP files!

## Features

### 🔗 Direct GitHub Cloning
- Clone repositories directly from GitHub URLs
- No need to download ZIP files
- Faster and more convenient workflow
- Supports both public repositories

### 📁 Dual Input Methods
The upload page now features two tabs:
1. **Upload ZIP** - Traditional ZIP file upload (still available)
2. **GitHub URL** - New direct cloning from GitHub

## How to Use

### Method 1: GitHub URL (Recommended)
1. Navigate to the Upload page
2. Click on the **"🔗 GitHub URL"** tab
3. Paste your GitHub repository URL (e.g., `https://github.com/username/repository`)
4. (Optional) Specify a branch in the Advanced Options
5. Click the **"Clone"** button
6. Wait for the repository to be cloned
7. Proceed with code analysis and documentation generation

### Method 2: ZIP Upload (Traditional)
1. Navigate to the Upload page
2. Stay on the **"📁 Upload ZIP"** tab
3. Upload your repository as a ZIP file
4. Continue with analysis as before

## Example URLs

Here are some example GitHub URLs you can try:

```
https://github.com/openai/whisper
https://github.com/microsoft/vscode
https://github.com/facebook/react
https://github.com/tensorflow/tensorflow
```

## Requirements

### For GitHub URL Cloning:
- **Git must be installed** on your system
- The application automatically checks if Git is available
- Download Git from: https://git-scm.com/

### Supported URL Formats:
- `https://github.com/username/repository`
- `https://github.com/username/repository.git`

## Technical Details

### Size Limits
- Maximum repository size: 100 MB (configurable)
- Shallow clone is used (depth=1) for faster performance
- Large repositories may take a few minutes to clone

### Security Features
- URL validation before cloning
- Size checks after cloning
- Automatic cleanup on errors
- .git directory removed to save space

### Branch Selection
- Default branch is used if not specified
- Can specify custom branch in Advanced Options
- Branch must exist in the repository

## Advantages Over ZIP Upload

1. **Convenience**: No need to download files locally first
2. **Speed**: Direct cloning can be faster for large repos
3. **Freshness**: Always get the latest version
4. **Flexibility**: Easy to clone different branches
5. **Workflow**: Seamless integration with GitHub

## Troubleshooting

### "Git is not installed"
**Solution**: Install Git from https://git-scm.com/ and restart the application

### "Failed to clone repository"
**Possible causes**:
- Invalid URL format
- Repository doesn't exist or is private
- Network connectivity issues
- Repository too large

**Solutions**:
- Verify the URL is correct
- Check your internet connection
- Try a smaller repository
- Use ZIP upload as an alternative

### "Repository too large"
**Solution**: 
- Use a smaller repository
- Contact admin to increase size limits
- Use ZIP upload with selective files

### Clone is taking too long
**Reason**: Large repositories may take several minutes
**Tip**: The progress indicator shows "Cloning repository..." while working

## Configuration

The following settings can be adjusted in [config.py](config.py):

```python
MAX_UPLOAD_BYTES = 100 * 1024 * 1024  # 100 MB
MAX_EXTRACT_BYTES = 100 * 1024 * 1024  # 100 MB
```

## API Reference

### New Functions

#### `validate_github_url(url: str) -> tuple[bool, str]`
Validates if a URL is a valid GitHub repository URL.

#### `clone_github_repo(url: str, target_dir: Path, branch: str = None, depth: int = 1) -> tuple[str, Path]`
Clones a GitHub repository to the specified directory.

#### `handle_github_url(github_url: str, uploads_dir: Path, branch: str = None) -> tuple[str, Path]`
High-level function to handle GitHub URL input from the UI.

### Modified Functions

#### `show()` in `_1_upload.py`
Now includes tab-based interface for both upload methods.

## Future Enhancements

Potential improvements for future versions:
- Support for private repositories (with authentication tokens)
- GitLab and Bitbucket support
- Repository search functionality
- Clone history/favorites
- Webhook integration for auto-updates
- Support for specific commits/tags
- GitHub API integration for branch listing

## FAQ

**Q: Can I clone private repositories?**
A: Currently, only public repositories are supported. Private repository support may be added in future versions.

**Q: Does cloning use my GitHub account?**
A: No, cloning is done anonymously for public repositories.

**Q: What happens to cloned repositories?**
A: They are stored in `app/data/uploads/` just like extracted ZIP files and can be reused for analysis.

**Q: Can I clone from other platforms like GitLab?**
A: Currently, only GitHub is supported. Other platforms may be added in future updates.

**Q: Is there a limit on how many repositories I can clone?**
A: The limit is based on available disk space and the configured size limits.

## Support

If you encounter any issues with GitHub integration:
1. Check that Git is properly installed
2. Verify the GitHub URL is correct
3. Check the application logs for detailed error messages
4. Try using ZIP upload as an alternative
5. Report issues on the project repository

---

**Happy Analyzing! 🚀**
