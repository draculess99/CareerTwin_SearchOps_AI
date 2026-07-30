from __future__ import annotations

import os
import webbrowser
from datetime import date
from pathlib import Path

import pandas as pd
import requests
import streamlit as st
import streamlit.components.v1 as components

API_URL = os.getenv("API_URL", "http://localhost:5050")
BASE_DIR = Path(__file__).resolve().parents[1]
TRACK_LABELS = {
    "supply_chain": "Supply Chain",
    "applied_ai": "Applied AI",
    "healthcare_ai": "Healthcare AI",
}
TRACK_ICONS = {"supply_chain": "📦", "applied_ai": "🤖", "healthcare_ai": "🏥"}

st.set_page_config(page_title="CareerTwin SearchOps AI", page_icon="🎯", layout="wide")

st.markdown("""
<style>
.block-container {padding-top: 1.3rem; padding-bottom: 2rem;}
.small-muted {color:#7b8794;font-size:.9rem;}
.metric-card {border:1px solid rgba(128,128,128,.25); border-radius:12px; padding:14px;}
</style>
""", unsafe_allow_html=True)


def api_get(path: str, **params):
    r = requests.get(f"{API_URL}{path}", params=params, timeout=10)
    r.raise_for_status()
    return r.json()


def api_post(path: str, payload: dict):
    r = requests.post(f"{API_URL}{path}", json=payload, timeout=15)
    r.raise_for_status()
    return r.json()


def api_patch(path: str, payload: dict):
    r = requests.patch(f"{API_URL}{path}", json=payload, timeout=10)
    r.raise_for_status()
    return r.json()


def api_delete(path: str):
    r = requests.delete(f"{API_URL}{path}", timeout=10)
    r.raise_for_status()
    return r.json()


def check_api() -> bool:
    try:
        api_get("/api/health")
        return True
    except Exception:
        return False


st.title("🎯 CareerTwin SearchOps AI")
st.caption("A human-in-the-loop job search command center for Supply Chain, Applied AI, and Healthcare AI roles.")
st.warning("At present, the app parses the named Boolean searches, but settings such as Past 24 hours, Mid-Senior level, and Full-time are not all guaranteed to be pushed into every platform’s generated URL. Those may still need to be selected on LinkedIn or Indeed after the results page opens.")

if not check_api():
    st.error("The Flask API is not running. Start it with: `python backend/app.py`, then refresh this page.")
    st.stop()

tracks = api_get("/api/tracks")
queries = api_get("/api/queries")
last_runs = api_get("/api/search-runs/latest")
applications = api_get("/api/applications")

with st.sidebar:
    st.header("Daily setup")
    selected_location = st.selectbox("Location", ["Greater Boston, Massachusetts", "Massachusetts", "United States"])
    remote = st.toggle("Remote search")
    st.info("This app launches official search pages. It does not scrape LinkedIn or Indeed and does not auto-apply.")
    st.subheader("Recommended daily load")
    st.write("3 Supply Chain · 3 Applied AI · 2 Healthcare AI")

main_tabs = st.tabs(["Daily Search", "Job Analyzer", "Application Tracker", "Resumes", "About"])

with main_tabs[0]:
    st.subheader("Today's search launcher")
    tab_labels = [f"{TRACK_ICONS[k]} {TRACK_LABELS[k]}" for k in TRACK_LABELS] + ["✏️ Custom"]
    track_tabs = st.tabs(tab_labels)
    for tab, track_key in zip(track_tabs[:-1], TRACK_LABELS):
        with tab:
            track_queries = [q for q in queries if q["track"] == track_key]
            priority = st.radio(
                "Show",
                ["Daily", "Rotation", "All"],
                horizontal=True,
                key=f"priority_{track_key}",
            )
            if priority != "All":
                shown = [q for q in track_queries if q["priority"] == priority]
            else:
                shown = track_queries

            st.caption(f"Recommended resume: {tracks[track_key]['resume']}")
            for q in shown:
                with st.container(border=True):
                    c1, c2 = st.columns([3, 1])
                    with c2:
                        platform = st.selectbox("Platform", ["gemini", "linkedin", "indeed", "google"], key=f"platform_{q['id']}")
                    with c1:
                        st.markdown(f"**{q['name']}**")
                        
                        if platform == "gemini":
                            loc_str = "Remote" if remote else selected_location
                            gemini_prompt = f"Search for jobs matching this query: {q['query']} in {loc_str}. Return the results in a table with the following columns: Company Name, Job Description, URL (where to apply), Date Published, Expiry Date, Location, and Chances of success on application. Give me a table for the last 24 hours, a table for the last week, a table for the last 2 weeks."
                            st.caption("Please modify the prompt if necessary:")
                            final_query = st.text_area("Gemini prompt", value=gemini_prompt, height=120, label_visibility="collapsed", key=f"query_input_{q['id']}")
                        else:
                            final_query = st.text_area("Boolean query", value=q["query"], height=100, label_visibility="collapsed", key=f"query_input_{q['id']}")
                            
                        last = last_runs.get(q["id"])
                        st.caption(f"Last run: {last[:16].replace('T', ' ') if last else 'Never'}")
                    with c2:
                        button_label = "Prepare Gemini Search" if platform == "gemini" else "Open search"
                        if st.button(button_label, key=f"open_{q['id']}", use_container_width=True):
                            query_to_send = st.session_state.get(f"query_input_{q['id']}", final_query)
                                
                            result = api_post("/api/search-url", {
                                "platform": platform,
                                "query": query_to_send,
                                "location": selected_location,
                                "remote": remote,
                            })
                            api_post("/api/search-runs", {
                                "query_id": q["id"], "track": track_key, "platform": platform,
                                "location": "Remote" if remote else selected_location,
                            })
                            
                            if platform == "gemini":
                                js_safe = query_to_send.replace('\\', '\\\\').replace('`', '\\`').replace('${', '\\${')
                                html_code = f"""
                                <div style="display: flex; flex-direction: column; gap: 10px; font-family: sans-serif; margin: 0; padding: 2px;">
                                    <button id="copyBtn" style="padding: 0.5rem 1rem; border-radius: 0.5rem; border: 1px solid #dcdde1; cursor: pointer; background: white; font-size: 1rem; transition: all 0.2s;">
                                        📋 Click to Copy Prompt
                                    </button>
                                    <a id="geminiLink" href="https://gemini.google.com/app" target="_blank" 
                                       style="display: none; padding: 0.5rem 1rem; border-radius: 0.5rem; border: 1px solid #dcdde1; cursor: pointer; background: #f8f9fa; text-align: center; text-decoration: none; color: #31333F; font-size: 1rem;">
                                        Go to Gemini
                                    </a>
                                </div>
                                <script>
                                document.getElementById('copyBtn').addEventListener('click', function() {{
                                    navigator.clipboard.writeText(`{js_safe}`).then(() => {{
                                        this.innerText = '✅ Copied!';
                                        this.style.backgroundColor = '#4CAF50';
                                        this.style.color = 'white';
                                        document.getElementById('geminiLink').style.display = 'block';
                                    }}).catch(err => {{
                                        this.innerText = '❌ Failed to copy. Copy manually.';
                                        this.style.backgroundColor = '#ff4b4b';
                                        this.style.color = 'white';
                                        document.getElementById('geminiLink').style.display = 'block';
                                    }});
                                }});
                                </script>
                                """
                                components.html(html_code, height=110)
                            else:
                                st.link_button(f"Continue to {platform.title()}", result["url"], use_container_width=True)
                        st.download_button(
                            "Copy via text file",
                            data=q["query"],
                            file_name=f"{q['id']}.txt",
                            mime="text/plain",
                            key=f"dl_{q['id']}",
                            use_container_width=True,
                        )
                        
    with track_tabs[-1]:
        st.caption("Run your own custom Boolean queries")
        with st.container(border=True):
            c1, c2 = st.columns([3, 1])
            with c2:
                platform = st.selectbox("Platform", ["gemini", "linkedin", "indeed", "google"], key="platform_custom")
            with c1:
                st.markdown("**Custom Application**")
                if platform == "gemini":
                    st.caption("Please modify the prompt if necessary:")
                custom_query = st.text_area("Enter your Boolean query", key="custom_query_input", height=100)

            with c2:
                button_label = "Prepare Gemini Search" if platform == "gemini" else "Open search"
                if st.button(button_label, key="open_custom", use_container_width=True):
                    if custom_query.strip():
                        query_to_send = custom_query
                        if platform == "gemini" and not custom_query.startswith("Search for jobs"):
                            loc_str = "Remote" if remote else selected_location
                            query_to_send = f"Search for jobs matching this query: {custom_query} in {loc_str}. Return the results in a table with the following columns: Company Name, Job Description, URL (where to apply), Date Published, Expiry Date, Location, and Chances of success on application. Give me a table for the last 24 hours, a table for the last week, a table for the last 2 weeks."
                            
                        result = api_post("/api/search-url", {
                            "platform": platform,
                            "query": query_to_send,
                            "location": selected_location,
                            "remote": remote,
                        })
                        api_post("/api/search-runs", {
                            "query_id": "custom", "track": "custom", "platform": platform,
                            "location": "Remote" if remote else selected_location,
                        })
                        
                        if platform == "gemini":
                            js_safe = query_to_send.replace('\\', '\\\\').replace('`', '\\`').replace('${', '\\${')
                            html_code = f"""
                            <div style="display: flex; flex-direction: column; gap: 10px; font-family: sans-serif; margin: 0; padding: 2px;">
                                <button id="copyBtn" style="padding: 0.5rem 1rem; border-radius: 0.5rem; border: 1px solid #dcdde1; cursor: pointer; background: white; font-size: 1rem; transition: all 0.2s;">
                                    📋 Click to Copy Prompt
                                </button>
                                <a id="geminiLink" href="https://gemini.google.com/app" target="_blank" 
                                   style="display: none; padding: 0.5rem 1rem; border-radius: 0.5rem; border: 1px solid #dcdde1; cursor: pointer; background: #f8f9fa; text-align: center; text-decoration: none; color: #31333F; font-size: 1rem;">
                                    Go to Gemini
                                </a>
                            </div>
                            <script>
                            document.getElementById('copyBtn').addEventListener('click', function() {{
                                navigator.clipboard.writeText(`{js_safe}`).then(() => {{
                                    this.innerText = '✅ Copied!';
                                    this.style.backgroundColor = '#4CAF50';
                                    this.style.color = 'white';
                                    document.getElementById('geminiLink').style.display = 'block';
                                }}).catch(err => {{
                                    this.innerText = '❌ Failed to copy. Copy manually.';
                                    this.style.backgroundColor = '#ff4b4b';
                                    this.style.color = 'white';
                                    document.getElementById('geminiLink').style.display = 'block';
                                }});
                            }});
                            </script>
                            """
                            components.html(html_code, height=110)
                        else:
                            st.link_button(f"Continue to {platform.title()}", result["url"], use_container_width=True)
                    else:
                        st.warning("Please enter a query first.")
                
                if custom_query.strip():
                    st.download_button(
                        "Copy via text file",
                        data=custom_query,
                        file_name="custom_query.txt",
                        mime="text/plain",
                        key="dl_custom",
                        use_container_width=True,
                    )

with main_tabs[1]:
    st.subheader("Analyze a job description")
    st.write("Paste a job description or provide a URL. The app uses an LLM to recommend one of your three resumes and shows match evidence.")
    
    col1, col2 = st.columns([4, 1])
    with col1:
        job_url = st.text_input("Job URL (Optional)", placeholder="https://www.linkedin.com/jobs/view/...")
    with col2:
        st.write("") # spacer
        st.write("") # spacer
        if st.button("Fetch URL", use_container_width=True):
            if job_url.strip():
                with st.spinner("Fetching..."):
                    try:
                        scrape_res = api_post("/api/scrape-job", {"url": job_url})
                        st.session_state["scraped_jd"] = scrape_res.get("text", "")
                    except Exception as e:
                        st.error(f"Failed to scrape: {e}")
            else:
                st.warning("Please enter a URL")
                
    current_jd = st.session_state.get("scraped_jd", "")
    jd = st.text_area("Job description", value=current_jd, height=300, placeholder="Paste the full job description here...")
    
    if st.button("Analyze job", type="primary", disabled=not jd.strip()):
        with st.spinner("Analyzing with LLM (this may take a few seconds)..."):
            result = api_post("/api/analyze-job", {"description": jd})
            st.session_state["analysis_result"] = result
    result = st.session_state.get("analysis_result")
    if result:
        a, b, c = st.columns(3)
        a.metric("Fit score", f"{result['fit_score']}%")
        b.metric("Best track", result["recommended_track_label"])
        c.metric("Verdict", result["verdict"])
        st.success(f"Use resume: **{result['recommended_resume']}**")
        left, right = st.columns(2)
        with left:
            st.markdown("**Matched domain keywords**")
            st.write(", ".join(result["matched_domain_keywords"]) or "No strong domain terms detected")
            st.markdown("**Matched resume terms**")
            st.write(", ".join(result["matched_resume_terms"]) or "No matches detected")
        with right:
            st.markdown("**Potential missing terms**")
            st.write(", ".join(result["missing_terms"]) or "No obvious missing terms")
            if result["red_flags"]:
                st.warning("Check these requirements: " + ", ".join(result["red_flags"]))

        with st.expander("Save this job to the tracker"):
            with st.form("save_job_form"):
                title = st.text_input("Job title")
                company = st.text_input("Company")
                location = st.text_input("Location")
                source = st.selectbox("Source", ["LinkedIn", "Indeed", "Google", "Company site", "Other"])
                url = st.text_input("Job URL")
                notes = st.text_area("Notes")
                submitted = st.form_submit_button("Save job")
                if submitted and title:
                    api_post("/api/applications", {
                        "title": title, "company": company, "location": location, "source": source,
                        "url": url, "track": result["recommended_track"], "status": "Saved",
                        "fit_score": result["fit_score"], "resume_name": result["recommended_resume"],
                        "notes": notes,
                    })
                    st.success("Job saved.")
                    st.rerun()

with main_tabs[2]:
    st.subheader("Application tracker")
    if not applications:
        st.info("No jobs saved yet. Analyze a job description and save it here.")
    else:
        df = pd.DataFrame(applications)
        display_cols = ["id", "title", "company", "location", "track", "status", "fit_score", "resume_name", "follow_up_date", "updated_at"]
        st.dataframe(df[display_cols], use_container_width=True, hide_index=True)
        selected_id = st.selectbox("Select application to update", [a["id"] for a in applications], format_func=lambda i: next(f"{x['title']} — {x['company']}" for x in applications if x["id"] == i))
        selected = next(x for x in applications if x["id"] == selected_id)
        with st.form("update_application"):
            status = st.selectbox("Status", ["Saved", "Applied", "Interview", "Offer", "Rejected", "Withdrawn"], index=["Saved", "Applied", "Interview", "Offer", "Rejected", "Withdrawn"].index(selected["status"]) if selected["status"] in ["Saved", "Applied", "Interview", "Offer", "Rejected", "Withdrawn"] else 0)
            notes = st.text_area("Notes", value=selected.get("notes") or "")
            follow = st.date_input("Follow-up date", value=date.fromisoformat(selected["follow_up_date"]) if selected.get("follow_up_date") else None)
            if st.form_submit_button("Update"):
                api_patch(f"/api/applications/{selected_id}", {"status": status, "notes": notes, "follow_up_date": follow.isoformat() if follow else ""})
                st.success("Updated.")
                st.rerun()
        if st.button("Delete selected job", type="secondary"):
            api_delete(f"/api/applications/{selected_id}")
            st.rerun()

with main_tabs[3]:
    st.subheader("Your three ATS resumes")
    for key, item in tracks.items():
        with st.container(border=True):
            st.markdown(f"### {TRACK_ICONS[key]} {item['label']}")
            st.write(item["resume"])
            st.link_button("Download from local API", f"{API_URL}/api/resumes/{item['resume']}")

with main_tabs[4]:
    st.subheader("What this app buys you")
    st.markdown("""
- One dashboard for three career tracks.
- A manageable daily rotation instead of dozens of disconnected Boolean searches.
- One-click launchers for LinkedIn, Indeed, and Google.
- Automatic recommendation of the correct ATS resume for a pasted job description.
- A local job tracker with fit scores, statuses, notes, and follow-up dates.
- Human approval at every important step; the app never auto-applies.

**Privacy:** Job descriptions and application records stay in the local SQLite database unless you deploy the app to a server.
""")
