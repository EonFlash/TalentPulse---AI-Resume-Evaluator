import streamlit as st
from streamlit_option_menu import option_menu
import hashlib, uuid, time, json, traceback, sqlite3, glob
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from evaluator.workflows import *
from evaluator.evaluate_resume import evaluate_resume_file
from database.db import *   # keeps your existing DB helpers (init_db, create_batch, add_file, set_file_done, set_file_error, get_batch_progress)

# --- filesystem setup ---
UPLOAD_DIR = Path("uploads")
RESULTS_DIR = Path("results")
UPLOAD_DIR.mkdir(exist_ok=True)
RESULTS_DIR.mkdir(exist_ok=True)
init_db()  # idempotent

# --- helper DB utilities (robust) ---
def find_any_db_file():
    # Prefer common names, otherwise pick first .db in cwd
    candidates = ["resume_simple.db", "resume_batches.db", "resume.db", "resume_simple.sqlite", "database.db"]
    for c in candidates:
        p = Path(c)
        if p.exists():
            return str(p)
    # fallback: pick first .db file in cwd
    dbs = glob.glob("*.db") + glob.glob("*.sqlite") + glob.glob("*.sqlite3")
    return dbs[0] if dbs else None

DB_PATH = find_any_db_file()

def query_batches_from_db(limit=200):
    """Return list of batches as dicts. If no DB found, return empty list."""
    if not DB_PATH:
        return []
    try:
        con = sqlite3.connect(DB_PATH)
        cur = con.cursor()
        # adapt to possible column names created by your DB schema
        cur.execute("SELECT id, created_at, status, total_files, completed_files FROM batches ORDER BY created_at DESC LIMIT ?", (limit,))
        rows = cur.fetchall()
        con.close()
        result = []
        for r in rows:
            result.append({
                "id": r[0],
                "created_at": r[1],
                "status": r[2],
                "total_files": r[3],
                "completed_files": r[4]
            })
        return result
    except Exception:
        return []

def query_files_for_batch(batch_id):
    """Return files rows for a batch. Will attempt to return useful columns."""
    if not DB_PATH:
        return []
    try:
        con = sqlite3.connect(DB_PATH)
        cur = con.cursor()
        cur.execute("SELECT id, filename, path, checksum, status, result_path, error FROM files WHERE batch_id=? ORDER BY rowid", (batch_id,))
        rows = cur.fetchall()
        con.close()
        files = []
        for r in rows:
            files.append({
                "id": r[0],
                "filename": r[1],
                "path": r[2],
                "checksum": r[3],
                "status": r[4],
                "result_path": r[5],
                "error": r[6]
            })
        return files
    except Exception:
        return []

def read_result_json_for_file(file_id):
    # Prefer result file saved in DB (if available), else results/<file_id>.json
    # Try common names
    try:
        # Try DB lookup for result_path
        if DB_PATH:
            con = sqlite3.connect(DB_PATH)
            cur = con.cursor()
            cur.execute("SELECT result_path FROM files WHERE id=?", (file_id,))
            r = cur.fetchone()
            con.close()
            if r and r[0]:
                p = Path(r[0])
                if p.exists():
                    return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        pass

    # fallback to results folder file
    p = RESULTS_DIR / f"{file_id}.json"
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return {"_raw": p.read_text(encoding="utf-8")}
    # if error json exists
    p2 = RESULTS_DIR / f"{file_id}_error.json"
    if p2.exists():
        try:
            return json.loads(p2.read_text(encoding="utf-8"))
        except Exception:
            return {"_raw_error": p2.read_text(encoding="utf-8")}
    return None

# --- Streamlit pages selection (sidebar) ---
st.set_page_config(page_title="Talent Pulse - Evaluate your resume", layout="wide")
st.sidebar.title("Talent Pulse")
page = st.sidebar.radio("Go to", ["Evaluate", "Results"], index=0)


# --- EVALUATE PAGE (keeps your spinner + stages + logic unchanged) ---
if page == "Evaluate":
    st.title(":blue[_Talent Pulse_] - Evaluate your resume")
    st.divider()

    st.info("UPLOAD THE CANDIDATE RESUME", icon="🔹")
    with st.form("Upload form"):

        uploaded_files = st.file_uploader("Upload resumes (multiple)", accept_multiple_files=True, type=["pdf","docx"])
        job_description = st.text_area("Paste your Job Description Here:")
        max_workers = st.number_input("Concurrent workers", min_value=1, max_value=8, value=3, step=1)
        submitted = st.form_submit_button("Start Batch")

        if submitted:
            if not job_description:
                st.warning("Please paste the job description")
            if not uploaded_files:
                st.warning("Please upload a resume first.")
            else:
                # create batch
                batch_id = str(uuid.uuid4())
                total = len(uploaded_files)
                create_batch(batch_id, total)

                # Save files & add to DB
                file_entries = []
                for f in uploaded_files:
                    data = f.read()
                    checksum = hashlib.sha256(data).hexdigest()
                    file_id = str(uuid.uuid4())
                    dest_dir = UPLOAD_DIR / batch_id
                    dest_dir.mkdir(parents=True, exist_ok=True)
                    path = dest_dir / f"{file_id}_{f.name}"
                    path.write_bytes(data)
                    add_file(file_id, batch_id, f.name, str(path), checksum)
                    file_entries.append((file_id, str(path)))

                
                st.toast(f"Enqueued batch {batch_id} with {total} files.")
                # placeholders we can update
                status_txt = st.empty()       # will show dynamic status text
                progress_bar = st.progress(0) # progress bar

                # --- Keep your spinner and stage flow exactly as before ---
                with st.spinner("Processing..."):
                    # Stage 1
                    status_txt.markdown("⏳ **Extracting info...**")
                    time.sleep(1.2)
                    progress_bar.progress(20)
                    # small sleep to allow UI render
                    time.sleep(0.05)

                    # Stage 2
                    status_txt.markdown("🔍 **Parsing sections & scoring...**")
                    # show the pre-batch progress mark
                    progress_bar.progress(55)
                    time.sleep(0.05)

                    # --- Batch processing using ThreadPoolExecutor ---
                    def worker(file_id, file_path):
                        try:
                            # Call your evaluator (synchronous). It should return a JSON-serializable dict
                            result = evaluate_resume_file(file_path, job_description)

                            # Save per-file JSON result immediately
                            result_path = RESULTS_DIR / f"{file_id}.json"
                            with open(result_path, "w", encoding="utf-8") as fh:
                                json.dump(result, fh, ensure_ascii=False, indent=2)

                            # mark DB (if function available)
                            try:
                                set_file_done(file_id, str(result_path))
                            except Exception:
                                pass

                            return {"file_id": file_id, "status": "DONE", "result_path": str(result_path)}
                        except Exception as e:
                            err = traceback.format_exc()
                            err_path = RESULTS_DIR / f"{file_id}_error.json"
                            with open(err_path, "w", encoding="utf-8") as ef:
                                json.dump({"error": str(e), "trace": err}, ef, ensure_ascii=False, indent=2)
                            try:
                                set_file_error(file_id, str(e))
                            except Exception:
                                pass
                            return {"file_id": file_id, "status": "ERROR", "error": str(e)}

                    # run tasks concurrently and update progress between 55 -> 90
                    results_summary = []
                    completed = 0
                    total_files = len(file_entries)
                    start_pct = 55
                    end_pct = 90
                    with ThreadPoolExecutor(max_workers=int(max_workers)) as exe:
                        future_to_file = {exe.submit(worker, fid, fpath): (fid, fpath) for fid, fpath in file_entries}

                        for fut in as_completed(future_to_file):
                            res = fut.result()
                            results_summary.append(res)
                            completed += 1

                            # map completed/total to progress range
                            pct = start_pct + int((completed / total_files) * (end_pct - start_pct))
                            progress_bar.progress(pct)
                            # update status text
                            info = get_batch_progress(batch_id) or {"status": "RUNNING"}
                            status_txt.markdown(f"🔍 **Parsing sections & scoring...** — processed {completed} / {total_files} — status: **{info['status']}**")

                            # tiny sleep so Streamlit renders updates smoothly
                            time.sleep(0.05)

                    # ensure we hit the expected Stage 2 -> pre-Stage 3 progress mark
                    progress_bar.progress(90)
                    time.sleep(0.05)

                    # Stage 3
                    status_txt.markdown("⚙️ **Applying scoring rules & finalizing**")
                    time.sleep(1.5)
                    progress_bar.progress(90)

                    # Finalize
                    status_txt.markdown("✅ **Finalizing results**")
                    time.sleep(0.8)
                    progress_bar.progress(100)

                # done with spinner
                time.sleep(0.5)
                progress_bar.empty()
                status_txt.success("✅ Resume evaluated successfully!")

                # show compact feedback (same style you used before)
                # feedback = {
                #     "batch_id": batch_id,
                #     "total_files": total,
                #     "results": results_summary
                # }
                # status_txt.write(feedback)

                # Show result links (unchanged)
                st.write("Results folder: `results/` — one JSON per file.")
                for file_id, _ in file_entries:
                    p = RESULTS_DIR / f"{file_id}.json"
                    if p.exists():
                        st.markdown(f"- `{p.name}`")

# --- RESULTS PAGE ---
else:
    # ------------------ REPLACE THE "RESULTS PAGE" BLOCK WITH THIS ------------------
    import re
    from datetime import datetime

    # helper: best-effort preview extractor from result JSON (keeps your existing function)
    def extract_preview_from_json(data):
        if data is None:
            return {"name": None, "match": None, "summary": None, "skills": None, "experience": None}
        top = {k.lower(): v for k, v in (data.items() if isinstance(data, dict) else [])}
        name_candidates = ["name", "candidate_name", "full_name", "person_name"]
        name = None
        for k in name_candidates:
            if k in top and top[k]:
                name = top[k] if isinstance(top[k], str) else str(top[k])
                break
        match = None
        score_candidates = ["match_percentage", "match_pct", "match", "score", "overall_score", "percent"]
        for k in score_candidates:
            if k in top and top[k] is not None:
                v = top[k]
                try:
                    fv = float(v)
                    if fv <= 1:
                        match = f"{fv*100:.1f}%"
                    else:
                        match = f"{fv:.1f}" if fv % 1 else str(int(fv))
                    break
                except Exception:
                    match = str(v)
                    break
        summary = None
        sum_candidates = ["summary", "final_summary", "feedback", "explanation", "conclusion"]
        for k in sum_candidates:
            if k in top and top[k]:
                v = top[k]
                summary = v if isinstance(v, str) else (json.dumps(v) if v is not None else None)
                break
        skills = None
        if "skills" in top and top["skills"]:
            s = top["skills"]
            if isinstance(s, list):
                skills = ", ".join(str(x) for x in s[:10])
            else:
                skills = str(s)
        else:
            for k, v in top.items():
                if isinstance(v, list) and len(v) and all(isinstance(i, str) for i in v[:5]) and len(k) < 20:
                    skills = ", ".join(v[:10])
                    break
        experience = None
        if "experience" in top and top["experience"]:
            experience = str(top["experience"])
        else:
            text_sources = []
            if summary:
                text_sources.append(summary)
            for k, v in top.items():
                if isinstance(v, str) and len(v) < 500:
                    text_sources.append(v)
            for txt in text_sources:
                m = re.search(r"(\d+(\.\d+)?)\s*(?:-|\sto\s)?\s*years?", txt, flags=re.I)
                if m:
                    experience = m.group(1) + " years"
                    break
        if summary and len(summary) > 300:
            summary_preview = summary[:300].strip() + "…"
        else:
            summary_preview = summary
        return {"name": name, "match": match, "summary": summary_preview, "skills": skills, "experience": experience}

    # Results page header
    st.title(":blue[_Talent Pulse_] - Results")
    st.write("Browse previously processed batches and view/download the *evaluation JSON* for each file. Results persist between app restarts.")
    st.divider()

    batches = query_batches_from_db()
    if not batches:
        st.info("No batches found in DB. Falling back to scanning results folder.")
        files = sorted(list(RESULTS_DIR.glob("*.json")), key=lambda p: p.stat().st_mtime, reverse=True)
        if not files:
            st.write("No results found.")
        else:
            # build preview rows from results folder (no DB metadata available)
            rows = []
            for p in files:
                try:
                    data = json.loads(p.read_text(encoding="utf-8"))
                except Exception:
                    data = {"_raw": p.read_text(encoding="utf-8")}
                preview = extract_preview_from_json(data)
                display_name = p.name.replace(".json", "")
                rows.append({"display_name": display_name, **preview, "path": p})
            # show simplified table (no IDs)
            table_rows = [{"file": r["display_name"], "candidate": r["name"] or "—", "match": r["match"] or "—", "experience": r["experience"] or "—"} for r in rows]
            st.table(table_rows)
            # expanders show full JSON and download button; download file named from original filename if possible
            for r in rows:
                with st.expander(f"{r['display_name']} — match: {r['match'] or '—'}"):
                    st.markdown(f"**Candidate:** {r['name'] or '—'}")
                    st.markdown(f"**Match / Score:** {r['match'] or '—'}")
                    st.markdown(f"**Experience:** {r['experience'] or '—'}")
                    st.markdown("**Top skills:**")
                    st.write(r["skills"] or "—")
                    st.subheader("Full result JSON")
                    try:
                        data = json.loads(r["path"].read_text(encoding="utf-8"))
                        st.json(data)
                        download_name = f"{r['display_name']}_result.json"
                        st.download_button("Download result JSON", data=json.dumps(data, ensure_ascii=False, indent=2), file_name=download_name)
                    except Exception:
                        st.text(r["path"].read_text(encoding="utf-8"))
    else:
        # Build a friendly label -> id map so we never show raw UUIDs
        batch_labels = []
        batch_map = {}
        for idx, b in enumerate(batches, start=1):
            # parse created_at for a nicer format if possible
            created_raw = b.get("created_at") or ""
            created_fmt = created_raw
            try:
                # try common ISO parse
                created_dt = datetime.fromisoformat(created_raw)
                created_fmt = created_dt.strftime("%Y-%m-%d %H:%M")
            except Exception:
                # leave as-is if parse fails
                created_fmt = created_raw
            label = f"Batch {idx} — {created_fmt} — {b['status'].upper()} ({b['completed_files']}/{b['total_files']})"
            batch_labels.append(label)
            batch_map[label] = b["id"]

        sel = st.selectbox("Select batch", options=batch_labels)
        sel_batch_id = batch_map.get(sel)

        files = query_files_for_batch(sel_batch_id)
        if not files:
            st.write("No files found for this batch (or DB schema differs).")
        else:
            # Build preview rows by reading each result JSON; DO NOT show internal IDs
            preview_rows = []
            for f in files:
                fid = f["id"]  # still used internally to find the result file
                data = read_result_json_for_file(fid)
                preview = extract_preview_from_json(data)
                preview_rows.append({
                    "file_id": fid,
                    "filename": f["filename"] or "Unnamed",
                    "status": f.get("status") or "—",
                    "name": preview["name"] or "—",
                    "match": preview["match"] or "—",
                    "experience": preview["experience"] or "—",
                    "skills": preview["skills"] or "—",
                    "summary": preview["summary"] or "—"
                })

            # show summary header
            st.subheader(f"Results for selected batch — {len(preview_rows)} files")
            # concise table without any UUIDs
            table_rows = [
                {
                    "file": r["filename"],
                    "candidate": r["name"],
                    "match": r["match"],
                    "experience": r["experience"],
                    "skills": (r["skills"][:100] + "…") if r["skills"] and len(r["skills"])>100 else r["skills"],
                    "status": r["status"]
                } for r in preview_rows
            ]
            st.table(table_rows)

            # Expanders: show the readable preview first, then full JSON, downloads use original filename
            for r in preview_rows:
                # header: filename and match (no IDs)
                with st.expander(f"{r['filename']} — match: {r['match']}"):
                    st.markdown(f"**Candidate:** {r['name']}")
                    st.markdown(f"**Match / Score:** {r['match']}")
                    st.markdown(f"**Experience:** {r['experience']}")
                    st.markdown(f"**Top skills:** {r['skills']}")
                    st.markdown("**Summary (trimmed):**")
                    st.write(r['summary'])

                    # Full JSON
                    data = read_result_json_for_file(r["file_id"])
                    if data:
                        st.subheader("Full result JSON")
                        st.json(data)
                        # Use original filename as download name (safe) - append suffix to avoid collisions
                        safe_name = "".join(ch for ch in r["filename"] if ch.isalnum() or ch in (" ", "_", "-")).rstrip()
                        download_filename = f"{safe_name}_result.json" if safe_name else f"result_{r['file_id']}.json"
                        try:
                            txt = json.dumps(data, ensure_ascii=False, indent=2)
                        except Exception:
                            txt = str(data)
                        st.download_button("Download result JSON", data=txt, file_name=download_filename)
                    else:
                        st.info("Result JSON not found for this file (maybe not processed yet).")
    # ----------------------------------------------------------------------------------------
