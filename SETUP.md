# AutoDocx Setup Guide

This guide will help you set up AutoDocx on your local machine.

## Prerequisites

- **Python 3.8 or higher** - Check your version: `python --version`
- **pip** - Python package manager (usually comes with Python)
- **Git** (optional) - For cloning the repository

## Step-by-Step Setup

### 1. Clone or Download the Project

If you have Git:
```bash
git clone <repository-url>
cd Autodocx
```

Or download and extract the ZIP file.

### 2. Create a Virtual Environment (Recommended)

**Windows:**
```bash
python -m venv venv
venv\Scripts\activate
```

**macOS/Linux:**
```bash
python3 -m venv venv
source venv/bin/activate
```

You should see `(venv)` in your terminal prompt.

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

This will install:
- streamlit (web framework)
- python-dotenv (environment variables)
- openai (for AI-powered reports - optional)

### 4. Configure Environment Variables (Optional)

For AI-powered reports, you need an OpenAI API key:

1. Copy `.env.example` to `.env`:
   ```bash
   copy .env.example .env  # Windows
   cp .env.example .env    # macOS/Linux
   ```

2. Edit `.env` and add your OpenAI API key:
   ```
   OPENAI_API_KEY=sk-your-actual-api-key-here
   ```

3. Get your API key from: https://platform.openai.com/api-keys

**Note:** You can skip this step if you only want to use structured reports (no AI).

### 5. Run the Application

```bash
streamlit run app/main.py
```

The application will start and automatically open in your browser at `http://localhost:8501`

### 6. Test the Application

1. Download a repository from GitHub as a ZIP file
2. Upload it in the AutoDocx interface
3. Run code analysis
4. Generate documentation

## Troubleshooting

### Issue: "Module not found" errors

**Solution:** Make sure your virtual environment is activated and dependencies are installed:
```bash
pip install -r requirements.txt
```

### Issue: "OPENAI_API_KEY not set"

**Solution:** This is only needed for AI-powered reports. You can:
- Set up the `.env` file as described above, OR
- Use "Structured Report" instead of "AI-Powered Report"

### Issue: Port 8501 already in use

**Solution:** Streamlit will automatically use the next available port, or you can specify one:
```bash
streamlit run app/main.py --server.port 8502
```

### Issue: "Permission denied" on Windows

**Solution:** Run your terminal/command prompt as Administrator, or check file permissions.

## Next Steps

- Read the [README.md](README.md) for detailed usage instructions
- Check out the features and capabilities
- Start documenting your repositories!

## Getting Help

If you encounter issues:
1. Check the error message in the application
2. Review the logs in the `logs/` directory
3. Ensure all prerequisites are met
4. Verify your Python version is 3.8+

---

Happy documenting! 📚

