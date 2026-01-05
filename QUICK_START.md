# AutoDocx Quick Start Guide

Get up and running with AutoDocx in 5 minutes!

## 🚀 Quick Setup

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Run the Application
```bash
streamlit run app/main.py
```

### 3. Open Your Browser
Navigate to `http://localhost:8501`

## 📦 Using AutoDocx

### Step 1: Upload a Repository
1. Download any GitHub/Bitbucket repository as a ZIP file
2. Click "Upload repository (.zip)" in AutoDocx
3. Select your ZIP file

### Step 2: Explore Code
- Browse repository structure
- View code files
- Check file metadata

### Step 3: Analyze Code
1. Click "Start AST Parsing"
2. Review analysis results
3. See language distribution

### Step 4: Generate Documentation
Choose one:
- **Structured Report** - Instant, no API needed
- **AI-Powered Report** - Enhanced with AI (requires API key)

## ⚙️ Optional: AI Reports

To enable AI-powered reports:

1. Get an OpenAI API key from https://platform.openai.com/api-keys
2. Create a `.env` file:
   ```
   OPENAI_API_KEY=your_key_here
   ```
3. Restart the application

## 📚 Need More Help?

- **Full Documentation:** See [README.md](README.md)
- **Setup Guide:** See [SETUP.md](SETUP.md)
- **Improvements:** See [IMPROVEMENTS.md](IMPROVEMENTS.md)

## ✨ Features

- ✅ Multi-language support (Python, JS, TS, Java, Go, Rust, C/C++, C#)
- ✅ AST-based code analysis
- ✅ Dependency detection
- ✅ Professional documentation generation
- ✅ No API key required for basic reports

---

**Happy Documenting!** 📚

