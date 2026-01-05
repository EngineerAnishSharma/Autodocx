# 📚 AutoDocx - Intelligent Code Documentation Generator

**Bridging the gap between developers and documentation in fast-paced MNC environments**

AutoDocx is an intelligent code documentation generator that automatically analyzes code repositories and generates comprehensive documentation. It helps solve the critical problem of missing or outdated documentation in large organizations where multiple simultaneous projects make manual documentation challenging.

## 🎯 Problem Statement

In MNC (Multinational Corporation) environments:
- Multiple simultaneous projects make manual documentation time-consuming
- Developers prioritize coding over documentation
- New team members struggle to understand existing projects
- Knowledge transfer becomes difficult without proper documentation
- Project handovers are inefficient

**AutoDocx solves this by automatically generating professional documentation from code repositories.**

## ✨ Features

### 📦 Repository Analysis
- **Upload Support**: Accept ZIP files from GitHub, Bitbucket, or any Git repository
- **Multi-Language Support**: Python, JavaScript, TypeScript, Java, Go, Rust, C/C++, C#
- **Automatic Structure Detection**: Identifies project organization and key files
- **Dependency Analysis**: Extracts dependencies from package.json, requirements.txt, pom.xml

### 🔍 Intelligent Code Parsing
- **AST-Based Analysis**: Deep code structure analysis using Abstract Syntax Trees
- **Function & Class Extraction**: Automatically identifies functions, classes, and methods
- **Import Detection**: Maps dependencies and imports
- **Language Detection**: Automatically detects programming languages

### 📝 Documentation Generation
- **Structured Reports**: Generate documentation without external APIs
- **AI-Powered Reports**: Enhanced documentation using OpenAI GPT models (optional)
- **Multiple Formats**: Export as Markdown, ready for conversion to PDF/HTML/DOCX
- **Comprehensive Sections**: 
  - Project Overview
  - Key Features
  - Architecture & Structure
  - Technology Stack
  - Dependencies
  - Setup Instructions
  - Usage Guide
  - Development Guidelines

## 🚀 Quick Start

### Prerequisites
- Python 3.8 or higher
- pip (Python package manager)

### Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd Autodocx
   ```

2. **Create a virtual environment** (recommended)
   ```bash
   python -m venv venv
   
   # On Windows
   venv\Scripts\activate
   
   # On macOS/Linux
   source venv/bin/activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables** (optional, for AI-powered reports)
   Create a `.env` file in the project root:
   ```
   OPENAI_API_KEY=your_api_key_here
   ```

5. **Run the application**
   ```bash
   streamlit run app/main.py
   ```

6. **Access the application**
   Open your browser and navigate to `http://localhost:8501`

## 📖 Usage Guide

### Step 1: Upload Repository
1. Download your repository as a ZIP file from GitHub/Bitbucket
2. Click "Upload repository (.zip)" in the AutoDocx interface
3. Select your ZIP file (max 100 MB)
4. Wait for extraction and validation

### Step 2: Explore Code Files
1. Browse the repository structure
2. Select any code file to view its contents
3. Review file metadata (size, language, etc.)

### Step 3: Run Code Analysis
1. Click "Start AST Parsing"
2. Set the maximum number of files to analyze (default: 200)
3. Review the analysis summary
4. Explore parsed files and their structure

### Step 4: Generate Documentation
Choose one of two options:

**Option A: Structured Report (No API Required)**
- Click "Generate Structured Report"
- Get instant documentation based on code analysis
- Download as Markdown file

**Option B: AI-Powered Report (Requires API Key)**
- Ensure OPENAI_API_KEY is set in your environment
- Click "Generate AI-Powered Report"
- Get enhanced documentation with AI insights
- Download as Markdown file

## 🏗️ Project Structure

```
Autodocx/
├── app/
│   ├── main.py                 # Streamlit entry point
│   ├── components/
│   │   └── uploader.py         # File upload handler
│   ├── pages/
│   │   └── _1_upload.py        # Main upload & analysis page
│   ├── utils/
│   │   ├── ast_parser.py       # AST parsing utilities
│   │   ├── file_utils.py       # File operations
│   │   └── report_builder.py  # Report generation
│   └── data/
│       └── uploads/            # Uploaded repositories (gitignored)
├── venv/                       # Virtual environment (gitignored)
├── requirements.txt            # Python dependencies
├── .gitignore                  # Git ignore rules
└── README.md                   # This file
```

## 🔧 Configuration

### Environment Variables

- `OPENAI_API_KEY`: (Optional) Your OpenAI API key for AI-powered reports
  - Get your API key from: https://platform.openai.com/api-keys
  - Without this, you can still use structured reports

### Settings

You can modify these settings in the code:
- **Max Upload Size**: 100 MB (in `components/uploader.py`)
- **Max Extract Size**: 200 MB (in `components/uploader.py`)
- **Max File Size for Parsing**: 1 MB (in `utils/ast_parser.py`)
- **Default Max Files**: 200 (in UI)

## 🛠️ Supported Languages

| Language | Extensions | Parser Type |
|----------|-----------|-------------|
| Python | `.py` | AST (built-in) |
| JavaScript | `.js`, `.jsx` | Regex-based |
| TypeScript | `.ts`, `.tsx` | Regex-based |
| Java | `.java` | Regex-based |
| Go | `.go` | Basic detection |
| Rust | `.rs` | Basic detection |
| C/C++ | `.c`, `.cpp` | Basic detection |
| C# | `.cs` | Basic detection |

## 📊 Report Sections

Generated documentation includes:

1. **Project Overview** - What the project does
2. **Key Features** - Main functionalities
3. **Project Structure** - Architecture and organization
4. **Technology Stack** - Languages and frameworks used
5. **Dependencies** - Required libraries and packages
6. **Important Files** - Critical files and their purposes
7. **Setup & Installation** - How to set up the project
8. **Usage Guide** - How to use the project
9. **Development Guidelines** - For contributors
10. **Known Issues & Future Improvements** - Current limitations

## 🔒 Security & Privacy

- **Local Processing**: All code analysis happens locally on your machine
- **No Data Transmission**: Code is not sent anywhere unless you use AI-powered reports
- **API Keys**: Stored securely in environment variables
- **Upload Limits**: Built-in protection against zip bombs and large files
- **Path Traversal Protection**: Secure extraction prevents directory traversal attacks

## 🐛 Troubleshooting

### Common Issues

**Issue**: "OPENAI_API_KEY not set"
- **Solution**: Set the environment variable or use structured reports instead

**Issue**: "No supported files found"
- **Solution**: Ensure your repository contains code files in supported languages

**Issue**: "File too large"
- **Solution**: The file exceeds 1 MB limit. Large files are skipped automatically.

**Issue**: "Upload too large"
- **Solution**: Maximum upload size is 100 MB. Consider uploading a smaller subset.

### Getting Help

1. Check the error message in the UI
2. Review the "Error Details" expander if available
3. Check that all dependencies are installed: `pip install -r requirements.txt`
4. Ensure Python version is 3.8 or higher: `python --version`

## 🚧 Future Enhancements

- [ ] Direct GitHub/Bitbucket integration (no ZIP upload needed)
- [ ] PDF export functionality
- [ ] HTML export with styling
- [ ] DOCX export support
- [ ] More language parsers (Ruby, PHP, Swift, Kotlin)
- [ ] Code complexity metrics
- [ ] Dependency vulnerability scanning
- [ ] Multi-repository comparison
- [ ] Custom report templates
- [ ] Batch processing support

## 📝 License

This project is open source. Please check the license file for details.

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## 👥 Authors

AutoDocx Team

## 🙏 Acknowledgments

- Built with [Streamlit](https://streamlit.io/)
- Uses OpenAI API for AI-powered documentation (optional)
- Inspired by the need for better documentation in fast-paced development environments

---

**Made with ❤️ for developers who value good documentation**

