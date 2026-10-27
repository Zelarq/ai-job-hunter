import os
import csv
import sqlite3
import logging
from datetime import datetime
from typing import List, Dict, Any, Tuple, Optional

logger = logging.getLogger("storage")

DEFAULT_DB_PATH = "data/jobs.db"

def init_db(db_path: str = DEFAULT_DB_PATH):
    """Initializes SQLite database and creates the 'jobs' table and indexes."""
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                url TEXT PRIMARY KEY,
                company TEXT NOT NULL,
                title TEXT NOT NULL,
                location TEXT,
                first_seen TEXT NOT NULL,
                last_seen TEXT NOT NULL,
                ats_type TEXT,
                notes TEXT
            );
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_first_seen ON jobs(first_seen);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_company ON jobs(company);")
        conn.commit()
    logger.info(f"SQLite database initialized at {db_path}.")

def upsert_job(
    job: Dict[str, Any], 
    run_date: Optional[str] = None, 
    db_path: str = DEFAULT_DB_PATH
) -> Tuple[bool, Dict[str, Any]]:
    """
    Inserts a job posting if new (first_seen = run_date),
    or updates last_seen if already present in database.
    Returns:
        (is_new: bool, job_record: dict)
    """
    if not run_date:
        run_date = datetime.now().strftime("%Y-%m-%d")

    url = (job.get("url") or "").strip()
    if not url:
        return False, {}

    company = (job.get("company") or "").strip()
    title = (job.get("title") or "").strip()
    location = (job.get("location") or "").strip()
    ats_type = (job.get("ats_type") or "").strip()
    notes = (job.get("notes") or "").strip()

    is_new = False
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        
        # Check if URL exists
        cursor.execute("SELECT first_seen, last_seen FROM jobs WHERE url = ?", (url,))
        row = cursor.fetchone()

        if row is None:
            # New job insertion
            cursor.execute("""
                INSERT INTO jobs (url, company, title, location, first_seen, last_seen, ats_type, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (url, company, title, location, run_date, run_date, ats_type, notes))
            is_new = True
            first_seen = run_date
        else:
            # Update last_seen
            first_seen = row[0]
            cursor.execute("UPDATE jobs SET last_seen = ? WHERE url = ?", (run_date, url))

        conn.commit()

    record = {
        "url": url,
        "company": company,
        "title": title,
        "location": location,
        "first_seen": first_seen,
        "last_seen": run_date,
        "ats_type": ats_type,
        "notes": notes
    }
    return is_new, record

def get_new_jobs_for_date(
    run_date: Optional[str] = None, 
    db_path: str = DEFAULT_DB_PATH
) -> List[Dict[str, Any]]:
    """Returns all jobs where first_seen equals run_date."""
    if not run_date:
        run_date = datetime.now().strftime("%Y-%m-%d")

    results = []
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("""
            SELECT url, company, title, location, first_seen, last_seen, ats_type, notes
            FROM jobs
            WHERE first_seen = ?
            ORDER BY company ASC, title ASC
        """, (run_date,))
        rows = cursor.fetchall()
        for r in rows:
            results.append(dict(r))

    return results

def export_new_jobs_to_csv(
    new_jobs: List[Dict[str, Any]], 
    export_dir: str = "data", 
    run_date: Optional[str] = None
) -> str:
    """Exports a list of new jobs to data/new_jobs_YYYY-MM-DD.csv."""
    if not run_date:
        run_date = datetime.now().strftime("%Y-%m-%d")

    os.makedirs(export_dir, exist_ok=True)
    filename = f"new_jobs_{run_date}.csv"
    filepath = os.path.join(export_dir, filename)

    fieldnames = ["company", "title", "location", "url", "first_seen", "ats_type", "notes"]
    with open(filepath, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(new_jobs)

    logger.info(f"Exported {len(new_jobs)} new jobs to {filepath}.")
    return filepath

def get_storage_stats(db_path: str = DEFAULT_DB_PATH) -> Dict[str, Any]:
    """Returns database summary statistics."""
    if not os.path.exists(db_path):
        return {"total_jobs": 0, "total_companies": 0}

    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*), COUNT(DISTINCT company) FROM jobs")
        total_jobs, total_companies = cursor.fetchone()
        
    return {
        "total_jobs": total_jobs,
        "total_companies": total_companies
    }

if __name__ == "__main__":
    init_db()
    today = datetime.now().strftime("%Y-%m-%d")
    sample = {
        "url": "https://example.com/job/101",
        "company": "Acme Analytics",
        "title": "Junior Data Scientist",
        "location": "Bangalore, India",
        "ats_type": "greenhouse"
    }
    is_new, rec = upsert_job(sample, today)
    print(f"First insert is_new: {is_new}")
    
    # Second insert test
    is_new2, rec2 = upsert_job(sample, today)
    print(f"Second insert is_new: {is_new2}")

    new_list = get_new_jobs_for_date(today)
    print(f"New jobs today: {len(new_list)}")
    csv_file = export_new_jobs_to_csv(new_list)
    print(f"Exported to: {csv_file}")
