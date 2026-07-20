from flask import Flask, render_template, request, jsonify
import json
import os
import re
from pathlib import Path
from werkzeug.utils import secure_filename
import requests

app = Flask(__name__)
app.config["UPLOAD_FOLDER"] = os.path.join(os.getcwd(), "uploads")
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024
os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

RESUME_SKILLS = [
    "python", "flask", "django", "javascript", "typescript", "react", "node.js",
    "sql", "postgresql", "mysql", "mongodb", "redis", "aws", "docker",
    "kubernetes", "git", "ci/cd", "rest api", "graphql", "machine learning",
    "pandas", "numpy", "scikit-learn", "tensorflow", "pytorch", "java",
    "c++", "c#", "linux", "bash", "azure", "data analysis", "tableau",
    "power bi", "etl", "spark", "airflow"
]


def normalize_text(text: str) -> str:
    return re.sub(r"[^a-z0-9+#.]+", " ", text.lower()).strip()


def extract_skills(text: str):
    normalized = normalize_text(text)
    found = []
    for skill in RESUME_SKILLS:
        if skill.lower() in normalized:
            found.append(skill)
    return found


def extract_text_from_upload(file_storage):
    filename = secure_filename(file_storage.filename or "resume")
    upload_path = Path(app.config["UPLOAD_FOLDER"]) / filename
    file_storage.save(upload_path)

    suffix = Path(filename).suffix.lower()
    if suffix == ".txt":
        return upload_path.read_text(encoding="utf-8", errors="ignore")

    if suffix == ".pdf":
        try:
            from pypdf import PdfReader
            reader = PdfReader(str(upload_path))
            return "\n".join(page.extract_text() or "" for page in reader.pages)
        except Exception:
            return ""

    if suffix == ".docx":
        try:
            import docx
            document = docx.Document(str(upload_path))
            return "\n".join(p.text for p in document.paragraphs)
        except Exception:
            return ""

    return upload_path.read_text(encoding="utf-8", errors="ignore")


def score_resume(resume_text: str, job_description: str):
    resume_normalized = normalize_text(resume_text)
    job_normalized = normalize_text(job_description)

    required_skills = sorted(set(extract_skills(job_description)))
    candidate_skills = sorted(set(extract_skills(resume_text)))
    matched_skills = [skill for skill in required_skills if skill.lower() in resume_normalized]

    if required_skills:
        ratio = len(matched_skills) / len(required_skills)
        score = int(round(ratio * 100))
    else:
        score = 0

    if matched_skills:
        score = min(100, score + 5)

    if any(token in resume_normalized for token in ["experience", "worked", "developed", "built"]):
        score = min(100, score + 3)

    gaps = [skill for skill in required_skills if skill.lower() not in resume_normalized]
    return score, matched_skills, gaps, candidate_skills


def analyze_with_claude(job_description: str, resume_text: str):
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return None

    prompt = f"""You are screening a resume for a job opening.
Return valid JSON with this shape:
{{"summary": "...", "matched_skills": ["..."], "gaps": ["..."], "score": 0}}

Job description:
{job_description}

Resume:
{resume_text[:12000]}
"""

    try:
        response = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": "claude-3-5-sonnet-20241022",
                "max_tokens": 400,
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=40,
        )
        response.raise_for_status()
        data = response.json()
        content = data["content"][0]["text"]
        cleaned = content.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.strip("`json\n")
        return json.loads(cleaned)
    except Exception as exc:
        return {"error": str(exc)}


@app.route("/", methods=["GET"])
def index():
    return render_template("index.html")


@app.route("/analyze", methods=["POST"])
def analyze():
    job_description = request.form.get("job_description", "").strip()
    resumes = request.files.getlist("resumes")

    if not job_description:
        return jsonify({"error": "Please provide a job description."}), 400
    if not resumes or all(file.filename == "" for file in resumes):
        return jsonify({"error": "Please upload at least one resume."}), 400

    results = []
    for file in resumes:
        if file.filename == "":
            continue

        resume_text = extract_text_from_upload(file)
        if not resume_text.strip():
            results.append({
                "name": file.filename,
                "score": 0,
                "matched_skills": [],
                "gaps": [],
                "summary": "Unable to read the uploaded file.",
                "candidate_skills": []
            })
            continue

        score, matched_skills, gaps, candidate_skills = score_resume(resume_text, job_description)
        ai_result = analyze_with_claude(job_description, resume_text)

        if ai_result and isinstance(ai_result, dict) and "score" in ai_result:
            if isinstance(ai_result.get("score"), int):
                score = ai_result["score"]
            if isinstance(ai_result.get("matched_skills"), list):
                matched_skills = ai_result["matched_skills"]
            if isinstance(ai_result.get("gaps"), list):
                gaps = ai_result["gaps"]

        summary = ai_result.get("summary") if ai_result and isinstance(ai_result, dict) else None
        if not summary:
            summary = f"Strong overlap on {', '.join(matched_skills[:5]) if matched_skills else 'core keywords'}"

        results.append({
            "name": file.filename,
            "score": score,
            "matched_skills": matched_skills,
            "gaps": gaps,
            "summary": summary,
            "candidate_skills": candidate_skills
        })

    results.sort(key=lambda item: item["score"], reverse=True)
    return jsonify({"results": results})


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
