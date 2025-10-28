# db_simple.py
import sqlite3
from pathlib import Path

DB = Path("resume_simple.db")
DB.parent.mkdir(exist_ok=True)

def init_db():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS batches (
                   id TEXT PRIMARY KEY, created_at TEXT, status TEXT,
                   total_files INTEGER, completed_files INTEGER
                 )""")
    c.execute("""CREATE TABLE IF NOT EXISTS files (
                   id TEXT PRIMARY KEY, batch_id TEXT, filename TEXT,
                   path TEXT, checksum TEXT, status TEXT, result_path TEXT, error TEXT
                 )""")
    conn.commit()
    conn.close()

def create_batch(batch_id, total_files):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("INSERT INTO batches(id, created_at, status, total_files, completed_files) VALUES (?, datetime('now'), ?, ?, ?)",
              (batch_id, "PENDING", total_files, 0))
    conn.commit(); conn.close()

def add_file(file_id, batch_id, filename, path, checksum):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("INSERT INTO files(id, batch_id, filename, path, checksum, status) VALUES (?, ?, ?, ?, ?, ?)",
              (file_id, batch_id, filename, path, checksum, "PENDING"))
    conn.commit(); conn.close()

def set_file_done(file_id, result_path):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("UPDATE files SET status='DONE', result_path=? WHERE id=?", (result_path, file_id))
    c.execute("UPDATE batches SET completed_files = completed_files + 1 WHERE id=(SELECT batch_id FROM files WHERE id=?)", (file_id,))
    # update batch status
    c.execute("SELECT total_files, completed_files, id FROM batches WHERE id=(SELECT batch_id FROM files WHERE id=?)", (file_id,))
    row = c.fetchone()
    if row:
        total, completed, batch_id = row
        if completed >= total:
            c.execute("UPDATE batches SET status='COMPLETED' WHERE id=?", (batch_id,))
        else:
            c.execute("UPDATE batches SET status='PARTIAL' WHERE id=?", (batch_id,))
    conn.commit(); conn.close()

def set_file_error(file_id, error):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("UPDATE files SET status='ERROR', error=? WHERE id=?", (error, file_id))
    conn.commit(); conn.close()

def get_batch_progress(batch_id):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("SELECT total_files, completed_files, status FROM batches WHERE id=?", (batch_id,))
    r = c.fetchone()
    conn.close()
    if r:
        return {"total": r[0], "completed": r[1], "status": r[2]}
    return None
