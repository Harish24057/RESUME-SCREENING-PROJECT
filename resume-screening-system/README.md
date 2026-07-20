# AI Resume Screening System

A Flask-based resume screening app that lets you upload resumes and a job description, then ranks candidates by relevance and highlights likely skill gaps.

## Features
- Flask backend with a simple web UI
- Resume parsing for TXT, PDF, and DOCX files
- Skill matching against a job description
- Ranked results with matched skills and gaps
- Optional Claude API integration when ANTHROPIC_API_KEY is set

## Setup
1. Install Python 3.10+.
2. Open a terminal in this folder.
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Start the app:
   ```bash
   python app.py
   ```
5. Open http://localhost:5000 in your browser.

## Optional Claude API
Set this environment variable before running the app:

```bash
set ANTHROPIC_API_KEY=your_key_here
```

On Linux/macOS, use `export` instead of `set`.
