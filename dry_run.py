import sys
import random
from datetime import datetime
from ingest import ingest_jobs
from db import hash_job

class MockJobDatabase:
    def __init__(self):
        self.seen_ids = set()
        print("[MockDB] Initialized mock database.")

    def is_job_seen(self, job_id: str) -> bool:
        return job_id in self.seen_ids

    def add_seen_jobs(self, jobs: list[dict]):
        print(f"[MockDB] Writing {len(jobs)} jobs to 'jobs_seen' mock sheet...")
        for job in jobs:
            self.seen_ids.add(job.get("job_id"))

    def add_passing_jobs(self, jobs: list[dict]):
        print(f"[MockDB] Writing {len(jobs)} passing jobs to 'passing_jobs' mock sheet...")
        for job in jobs:
            print(f"  -> Added {job.get('title')} at {job.get('company')} to passing jobs")

def mock_filter_jobs_list(jobs: list[dict], delay_sec: float = 1.0) -> list[dict]:
    print(f"[MockLLM] Scoring {len(jobs)} jobs... (Mock Mode)")
    scored_jobs = []
    for job in jobs:
        score = random.randint(1, 10)
        job["match_score"] = score
        job["domain"] = "Data Science"
        job["reject_reasons"] = ["No specific reasons"] if score >= 5 else ["Not a good fit"]
        job["resume_highlights"] = ["Experience matches", "Skills match"] if score >= 5 else []
        scored_jobs.append(job)
    return scored_jobs

def mock_send_digest_email(passing_jobs: list[dict], stats: dict) -> bool:
    print(f"[MockEmailer] Triggering email dispatch...")
    print(f"[MockEmailer] Stats: {stats}")
    print(f"[MockEmailer] Email would contain {len(passing_jobs)} jobs.")
    return True

def run_dry_run():
    print(f"==================================================")
    print(f"JobHunter AI Agent Pipeline (DRY RUN) started at {datetime.now().isoformat()}")
    print(f"==================================================")
    
    # 1. Initialize database connection
    db = MockJobDatabase()
        
    # 2. Run Ingestion (Scrape & Pre-Filter & Seen De-duplication)
    try:
        # We only look back 2 hours for a faster dry run instead of 24
        unseen_jobs = ingest_jobs(db, hours_old=2)
    except Exception as e:
        print(f"CRITICAL: Job ingestion failed. Pipeline aborting. Error: {e}")
        sys.exit(1)
        
    stats = {
        "total_scraped": len(unseen_jobs),
        "passed_count": 0
    }
    
    scored_jobs = []
    passing_jobs = []
    
    # 3. LLM Filter & Score
    if unseen_jobs:
        scored_jobs = mock_filter_jobs_list(unseen_jobs, delay_sec=0)
        passing_jobs = [job for job in scored_jobs if job.get("match_score", 0) >= 5]
        stats["passed_count"] = len(passing_jobs)
        
        print(f"Scoring complete. Total evaluated: {len(scored_jobs)}, Passed filter: {len(passing_jobs)}")
    else:
        print("No new unseen jobs found in ingestion. Skipping LLM scoring.")
        
    # 4. Update Database
    if scored_jobs:
        db.add_seen_jobs(scored_jobs)
        if passing_jobs:
            db.add_passing_jobs(passing_jobs)
                
    # 5. Send Daily Digest Email
    email_sent = mock_send_digest_email(passing_jobs, stats)
    if email_sent:
        print("Daily digest email sent successfully! (Mocked)")
        
    print(f"==================================================")
    print(f"Pipeline run finished at {datetime.now().isoformat()}")
    print(f"==================================================")

if __name__ == "__main__":
    run_dry_run()
