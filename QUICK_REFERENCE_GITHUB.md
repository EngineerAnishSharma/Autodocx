# 🚀 Quick Reference: GitHub Integration

## Basic Usage

### Clone a Repository
```
1. Open AutoDocx
2. Go to "🔗 GitHub URL" tab
3. Paste: https://github.com/username/repo
4. Click "Clone"
5. Done!
```

### With Custom Branch
```
1. Click "Advanced Options"
2. Enter branch name (e.g., "develop")
3. Click "Clone"
```

## Example Commands

### Test with Small Repo
```
URL: https://github.com/octocat/Hello-World
Expected: Clones in ~2-5 seconds
```

### Test with Medium Repo
```
URL: https://github.com/pallets/flask
Expected: Clones in ~10-30 seconds
```

## Common Issues & Quick Fixes

| Issue | Quick Fix |
|-------|-----------|
| "Git is not installed" | Install from https://git-scm.com/ |
| "Invalid GitHub URL format" | Use: `https://github.com/user/repo` |
| "Repository too large" | Try smaller repo or use ZIP upload |
| "Clone timed out" | Repository >100MB, use ZIP instead |
| Tab not responding | Refresh page, check Git installation |

## Requirements Checklist

- [x] Python 3.8+
- [x] Streamlit installed
- [x] Git installed (download: https://git-scm.com/)
- [x] Internet connection
- [x] GitHub repository URL

## URL Format Examples

✅ **Correct:**
```
https://github.com/microsoft/vscode
https://github.com/facebook/react
https://github.com/torvalds/linux
```

❌ **Incorrect:**
```
github.com/user/repo          (missing https://)
www.github.com/user/repo      (wrong domain)
https://github.com/user/      (missing repo)
```

## Features at a Glance

| Feature | Status |
|---------|--------|
| Public repos | ✅ Supported |
| Private repos | ❌ Not yet (use ZIP) |
| Custom branches | ✅ Supported |
| Size limit | ✅ 100 MB default |
| Timeout | ✅ 5 minutes max |
| GitLab/Bitbucket | ❌ Not yet (use ZIP) |

## Performance Tips

1. **Use shallow clone** (default) - Much faster!
2. **Specify branch** if not using main/master
3. **Check repo size** on GitHub before cloning
4. **Use ZIP upload** for very large repos (>100MB)
5. **Stable internet** required for cloning

## Testing Your Setup

Run this test:
```
1. Paste: https://github.com/github/gitignore
2. Click "Clone"
3. Should complete in ~5 seconds
4. If successful, Git integration is working!
```

## Need Help?

1. Check [GITHUB_INTEGRATION.md](GITHUB_INTEGRATION.md) for detailed docs
2. See [IMPLEMENTATION_SUMMARY.md](IMPLEMENTATION_SUMMARY.md) for technical details
3. Review logs in console for error messages
4. Verify Git installation: `git --version` in terminal

---

**Happy Cloning! 🎉**
