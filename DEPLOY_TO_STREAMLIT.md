# Deploying AutoDocx to Streamlit Cloud

## Prerequisites
1. **GitHub Account** - Required for Streamlit Cloud deployment
2. **Python 3.8+** - Already installed on your machine
3. **Git** - For version control

## Step-by-Step Deployment Guide

### 1. Prepare Your GitHub Repository

```bash
# Navigate to your project directory
cd c:\Users\91720\Documents\Hackathon\Autodocx

# Initialize git (if not already done)
git init

# Add all files
git add .

# Initial commit
git commit -m "Initial AutoDocx commit for Streamlit deployment"

# Create a new repository on GitHub (don't initialize with README)
# Then add the remote (replace YOUR_USERNAME and REPO_NAME)
git remote add origin https://github.com/YOUR_USERNAME/autodocx.git
git branch -M main
git push -u origin main
```

### 2. Structure for Deployment

Your current structure is good! Just ensure:
- ✅ `app/main.py` - Main entry point
- ✅ `app/pages/` - Multi-page structure
- ✅ `requirements.txt` - All dependencies
- ✅ `.streamlit/config.toml` - Configuration file (already created)

### 3. Update `.streamlit/secrets.toml` (Optional but Recommended)

Create `.streamlit/secrets.toml` for environment variables (GitHub tokens, API keys):

```toml
# .streamlit/secrets.toml
github_token = "your_github_token_here"
openai_api_key = "your_openai_api_key_here"
```

**Note:** Never commit `secrets.toml` to GitHub. Add to `.gitignore`:
```
.streamlit/secrets.toml
.env
```

### 4. Deploy on Streamlit Cloud

1. **Visit** [Streamlit Cloud](https://streamlit.io/cloud)
2. **Sign in** with your GitHub account
3. **Click "New app"**
4. **Configure:**
   - Repository: `YOUR_USERNAME/autodocx`
   - Branch: `main`
   - Main file path: `app/main.py`
5. **Click "Deploy"**

### 5. Add Secrets in Streamlit Cloud

After deployment:
1. Go to your app settings (⚙️ icon)
2. Select "Secrets"
3. Paste your secrets in the text area:
```toml
github_token = "your_github_token_here"
openai_api_key = "your_openai_api_key_here"
```
4. Save

### 6. Troubleshooting

#### Issue: "Module not found" errors
- **Solution:** Ensure all imports use relative paths:
  ```python
  from utils.ast_parser import parse_repo_ast
  from components.uploader import handle_uploaded_zip
  ```

#### Issue: File upload size limit exceeded
- **Solution:** Streamlit Cloud has a 200MB limit. The configuration already sets this.

#### Issue: GitHub clone failing
- **Solution:** Ensure git is installed on Streamlit Cloud server and use HTTPS URLs

#### Issue: Slow performance
- **Solution:** 
  - Use `st.cache_data` for expensive operations
  - Optimize large file processing
  - Consider streaming large outputs

### 7. Local Testing Before Deploy

```bash
# Test locally first
streamlit run app/main.py
```

Visit `http://localhost:8501` to verify everything works.

### 8. Key Streamlit Settings

Edit `.streamlit/config.toml`:
```toml
[server]
maxUploadSize = 200  # MB
enableXsrfProtection = true
enableCORS = false

[client]
showErrorDetails = true
```

## Deployment Checklist

- [ ] Git repository created and pushed
- [ ] `requirements.txt` includes all dependencies
- [ ] `.streamlit/config.toml` configured
- [ ] `.streamlit/secrets.toml` created locally (NOT pushed)
- [ ] `.gitignore` includes secrets file
- [ ] All relative imports are correct
- [ ] Local testing passed
- [ ] Streamlit Cloud app created
- [ ] Secrets added in Streamlit Cloud dashboard
- [ ] App deployed and tested live

## Your App URL
Once deployed, your app will be available at:
```
https://autodocx-YOUR_USERNAME.streamlit.app
```

## Additional Resources
- [Streamlit Documentation](https://docs.streamlit.io)
- [Streamlit Cloud Docs](https://docs.streamlit.io/streamlit-cloud)
- [Environment Variables & Secrets](https://docs.streamlit.io/streamlit-cloud/get-started/deploy-an-app/connect-to-data-sources/secrets-management)
