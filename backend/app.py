from __future__ import annotations

import json
import os
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from docx import Document
from pydantic import BaseModel

BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"
RESUME_DIR = BASE_DIR / "resumes"
DB_PATH = DATA_DIR / "searchops.db"
QUERY_FILE = DATA_DIR / "job_queries.txt"

TRACKS = {
    "supply_chain": {
        "label": "Supply Chain, Forecasting & Operations",
        "resume": "William_Low_Supply_Chain_Data_Scientist_ATS_Resume.docx",
        "keywords": [
            "supply chain", "logistics", "warehouse", "fulfillment", "forecasting",
            "demand planning", "capacity planning", "workforce planning", "inventory",
            "transportation", "routing", "optimization", "operations research", "xgboost",
            "time series", "sql", "tableau", "python", "simulation", "vet", "vto"
        ],
    },
    "applied_ai": {
        "label": "Applied AI & Machine Learning",
        "resume": "William_Low_Applied_AI_ML_Engineer_ATS_Resume.docx",
        "keywords": [
            "machine learning", "applied ai", "artificial intelligence", "llm", "large language model",
            "rag", "agentic", "multi-agent", "langgraph", "crewai", "prompt engineering",
            "scikit-learn", "xgboost", "python", "docker", "flask", "api", "aws", "azure",
            "mlops", "human in the loop", "decision intelligence", "generative ai"
        ],
    },
    "healthcare_ai": {
        "label": "Healthcare AI & Operations",
        "resume": "William_Low_Healthcare_AI_Engineer_ATS_Resume.docx",
        "keywords": [
            "healthcare", "hospital", "clinical operations", "patient flow", "bed management",
            "triage", "emergency department", "staffing", "discharge", "readmission",
            "prior authorization", "utilization management", "revenue cycle", "medical supply",
            "healthtech", "medical device", "decision support", "audit trail", "human oversight",
            "python", "sql", "machine learning", "rag", "llm"
        ],
    },
}

app = Flask(__name__)
CORS(app)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_conn() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with get_conn() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS applications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                company TEXT,
                location TEXT,
                source TEXT,
                url TEXT,
                track TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'Saved',
                fit_score INTEGER,
                resume_name TEXT,
                notes TEXT,
                follow_up_date TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS search_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                query_id TEXT NOT NULL,
                track TEXT NOT NULL,
                platform TEXT NOT NULL,
                location TEXT,
                run_at TEXT NOT NULL
            );
            """
        )


def parse_query_file() -> list[dict[str, Any]]:
    text = QUERY_FILE.read_text(encoding="utf-8")
    lines = [line.rstrip() for line in text.splitlines()]
    sections = {
        "1. SUPPLY CHAIN": "supply_chain",
        "2. APPLIED AI": "applied_ai",
        "3. HEALTHCARE AI": "healthcare_ai",
    }
    current_track: str | None = None
    results: list[dict[str, Any]] = []
    i = 0
    counters = {key: 0 for key in TRACKS}
    while i < len(lines):
        line = lines[i].strip()
        for marker, key in sections.items():
            if marker in line:
                current_track = key
                break
        if current_track and line and not line.startswith(("=", "Target jobs", "Use:", "WILLIAM", "Recommended", "-", "Optional", "HOW", "FAST", "GOOGLE")):
            next_line = lines[i + 1].strip() if i + 1 < len(lines) else ""
            if next_line.startswith("(") or next_line.startswith('"'):
                counters[current_track] += 1
                qid = f"{current_track}_{counters[current_track]}"
                results.append({
                    "id": qid,
                    "track": current_track,
                    "name": line,
                    "query": next_line,
                    "priority": "Daily" if counters[current_track] <= 3 else "Rotation",
                })
                i += 1
        i += 1
    return results


def extract_resume_text(filename: str) -> str:
    path = RESUME_DIR / filename
    if not path.exists():
        return ""
    try:
        from unstructured.partition.docx import partition_docx
        elements = partition_docx(filename=str(path))
        return "\n".join([str(e) for e in elements])
    except ImportError:
        doc = Document(path)
        return "\n".join(p.text for p in doc.paragraphs if p.text.strip())


def normalize_tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-zA-Z][a-zA-Z0-9+.#/-]{1,}", text.lower()))


class JobAnalysis(BaseModel):
    recommended_track: str
    recommended_track_label: str
    fit_score: int
    matched_domain_keywords: list[str]
    matched_resume_terms: list[str]
    missing_terms: list[str]
    red_flags: list[str]
    verdict: str

def analyze_job(description: str) -> dict[str, Any]:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return {
            "recommended_track": "supply_chain",
            "recommended_track_label": "Supply Chain, Forecasting & Operations",
            "recommended_resume": TRACKS["supply_chain"]["resume"],
            "fit_score": 0,
            "track_scores": {},
            "matched_domain_keywords": [],
            "matched_resume_terms": [],
            "missing_terms": [],
            "seniority_signals": [],
            "red_flags": ["GEMINI_API_KEY is not set in .env. LLM grading disabled."],
            "verdict": "Error"
        }
    
    try:
        from google import genai
        client = genai.Client(api_key=api_key)
        
        resumes_text = ""
        for key, cfg in TRACKS.items():
            rtext = extract_resume_text(cfg["resume"])
            resumes_text += f"\n--- RESUME TRACK: {key} ({cfg['label']}) ---\n{rtext}\n"
            
        portfolio_url = os.getenv("PORTFOLIO_URL", "")
        
        # If not in .env, try to extract a portfolio URL from the resume text
        if not portfolio_url:
            import re
            lines = resumes_text.splitlines()
            for line in lines:
                if 'portfolio' in line.lower() or 'website' in line.lower():
                    match = re.search(r'(https?://[^\s]+)', line)
                    if match:
                        portfolio_url = match.group(1)
                        break
            
            # Fallback to the first non-LinkedIn URL in the resume
            if not portfolio_url:
                match = re.search(r'(https?://(?:www\.)?(?!linkedin\.com)[^\s]+)', resumes_text)
                if match:
                    portfolio_url = match.group(1)

        portfolio_text = ""
        if portfolio_url:
            try:
                import requests
                from bs4 import BeautifulSoup
                r = requests.get(portfolio_url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=5)
                if r.status_code == 200:
                    soup = BeautifulSoup(r.text, "html.parser")
                    for script in soup(["script", "style"]):
                        script.extract()
                    portfolio_text = soup.get_text(separator="\n", strip=True)
            except Exception as e:
                print(f"Portfolio scrape error: {e}")
            
        prompt = f"""
        You are an expert technical recruiter analyzing a job description against three possible resumes.
        
        Job Description:
        {description}
        
        Available Tracks/Resumes:
        {resumes_text}
        
        Candidate's Live Portfolio Data:
        {portfolio_text if portfolio_text else "Not provided"}
        
        Select the best resume track for this job (must be 'supply_chain', 'applied_ai', or 'healthcare_ai'). 
        Then calculate a fit score (0-100) based on how well the job requirements match the selected resume.
        Identify matched domain keywords, matched resume terms, missing skills, and any red flags (e.g. requires medical license, clearance, or 10+ years experience).
        Verdict should be 'Strong match', 'Worth reviewing', or 'Stretch / weak match'.
        """
        
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config={
                'response_mime_type': 'application/json',
                'response_schema': JobAnalysis,
                'temperature': 0.1,
            },
        )
        
        data = json.loads(response.text)
        track_key = data.get("recommended_track", "supply_chain")
        if track_key not in TRACKS:
            track_key = "supply_chain"
            
        data["recommended_resume"] = TRACKS[track_key]["resume"]
        return data
        
    except Exception as e:
        print(f"LLM Error: {e}")
        return {
            "recommended_track": "supply_chain",
            "recommended_track_label": "Supply Chain",
            "recommended_resume": TRACKS["supply_chain"]["resume"],
            "fit_score": 0,
            "track_scores": {},
            "matched_domain_keywords": [],
            "matched_resume_terms": [],
            "missing_terms": [],
            "seniority_signals": [],
            "red_flags": [f"LLM Analysis failed: {str(e)}"],
            "verdict": "Error"
        }


LINKEDIN_GEO_IDS = {
    "Greater Boston, Massachusetts": "102380872",
    "Massachusetts": "102047806",
    "United States": "103644278",
    "Remote": "92000000"
}

def build_search_url(platform: str, query: str, location: str, remote: bool = False) -> str:
    q = quote_plus(query)
    loc_str = "Remote" if remote else location
    loc = quote_plus(loc_str)
    
    if platform == "linkedin":
        geo_id = LINKEDIN_GEO_IDS.get(loc_str, "92000000")
        if remote:
            return f"https://www.linkedin.com/jobs/search/?keywords={q}&geoId={geo_id}&f_TPR=r86400&f_WT=2"
        return f"https://www.linkedin.com/jobs/search/?keywords={q}&geoId={geo_id}&f_TPR=r86400"
    if platform == "indeed":
        return f"https://www.indeed.com/jobs?q={q}&l={loc}&fromage=1"
    if platform == "google":
        gq = quote_plus(f"{query} jobs {loc_str}")
        return f"https://www.google.com/search?q={gq}"
    if platform == "gemini":
        return f"https://www.google.com/search?q={quote_plus(query)}"
    raise ValueError("Unsupported platform")


@app.get("/api/health")
def health():
    return jsonify({"status": "ok", "time": now_iso()})


@app.get("/api/tracks")
def tracks():
    return jsonify({k: {"label": v["label"], "resume": v["resume"]} for k, v in TRACKS.items()})


@app.get("/api/queries")
def queries():
    track = request.args.get("track")
    items = parse_query_file()
    if track:
        items = [x for x in items if x["track"] == track]
    return jsonify(items)


@app.post("/api/search-url")
def search_url():
    payload = request.get_json(force=True)
    url = build_search_url(
        payload.get("platform", "linkedin"),
        payload["query"],
        payload.get("location", "Greater Boston, Massachusetts"),
        bool(payload.get("remote", False)),
    )
    return jsonify({"url": url})


@app.post("/api/search-runs")
def record_search_run():
    p = request.get_json(force=True)
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO search_runs(query_id, track, platform, location, run_at) VALUES(?,?,?,?,?)",
            (p["query_id"], p["track"], p["platform"], p.get("location", ""), now_iso()),
        )
    return jsonify({"ok": True}), 201


@app.post("/api/search-gemini")
def search_gemini():
    p = request.get_json(force=True)
    prompt = p.get("prompt", "")
    api_key = os.getenv("GEMINI_API_KEY")
    
    if not api_key:
        return jsonify({"error": "GEMINI_API_KEY is not set in backend."}), 400
        
    try:
        from google import genai
        client = genai.Client(api_key=api_key)
        
        # Enable Google Search grounding
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config={'tools': [{"googleSearch": {}}]}
        )
        return jsonify({"result": response.text})
    except Exception as e:
        print(f"Gemini API Search Error: {e}")
        return jsonify({"error": str(e)}), 500


@app.get("/api/search-runs/latest")
def latest_search_runs():
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT query_id, MAX(run_at) AS last_run FROM search_runs GROUP BY query_id"
        ).fetchall()
    return jsonify({row["query_id"]: row["last_run"] for row in rows})


@app.post("/api/analyze-job")
def analyze():
    p = request.get_json(force=True)
    return jsonify(analyze_job(p.get("description", "")))

@app.post("/api/scrape-job")
def scrape_job():
    p = request.get_json(force=True)
    url = p.get("url")
    if not url:
        return jsonify({"error": "No URL provided"}), 400
    try:
        import requests
        from bs4 import BeautifulSoup
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        r = requests.get(url, headers=headers, timeout=10)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        for script in soup(["script", "style"]):
            script.extract()
        text = soup.get_text(separator="\n", strip=True)
        return jsonify({"text": text})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.get("/api/applications")
def list_applications():
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM applications ORDER BY updated_at DESC").fetchall()
    return jsonify([dict(row) for row in rows])


@app.post("/api/applications")
def create_application():
    p = request.get_json(force=True)
    created = now_iso()
    with get_conn() as conn:
        cur = conn.execute(
            """
            INSERT INTO applications(title, company, location, source, url, track, status,
                                     fit_score, resume_name, notes, follow_up_date, created_at, updated_at)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                p["title"], p.get("company", ""), p.get("location", ""), p.get("source", ""),
                p.get("url", ""), p["track"], p.get("status", "Saved"), p.get("fit_score"),
                p.get("resume_name", TRACKS[p["track"]]["resume"]), p.get("notes", ""),
                p.get("follow_up_date", ""), created, created,
            ),
        )
        item_id = cur.lastrowid
    return jsonify({"id": item_id}), 201


@app.patch("/api/applications/<int:item_id>")
def update_application(item_id: int):
    p = request.get_json(force=True)
    allowed = {"title", "company", "location", "source", "url", "track", "status", "fit_score", "resume_name", "notes", "follow_up_date"}
    fields = [(k, v) for k, v in p.items() if k in allowed]
    if not fields:
        return jsonify({"error": "No editable fields supplied"}), 400
    sql = ", ".join(f"{k}=?" for k, _ in fields) + ", updated_at=?"
    values = [v for _, v in fields] + [now_iso(), item_id]
    with get_conn() as conn:
        conn.execute(f"UPDATE applications SET {sql} WHERE id=?", values)
    return jsonify({"ok": True})


@app.delete("/api/applications/<int:item_id>")
def delete_application(item_id: int):
    with get_conn() as conn:
        conn.execute("DELETE FROM applications WHERE id=?", (item_id,))
    return jsonify({"ok": True})


@app.get("/api/resumes/<path:filename>")
def download_resume(filename: str):
    if filename not in {v["resume"] for v in TRACKS.values()}:
        return jsonify({"error": "Unknown resume"}), 404
    return send_from_directory(RESUME_DIR, filename, as_attachment=True)


if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5050")), debug=os.getenv("FLASK_DEBUG") == "1")
