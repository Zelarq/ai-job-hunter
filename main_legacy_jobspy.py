import os
import sys
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables from .env file if running locally
load_dotenv()

from db import JobDatabase
from ingest import ingest_jobs
from llm_filter import filter_jobs_list
from emailer import send_digest_email

def run_pipeline():
    print(f"==================================================")
    print(f"JobHunter AI Agent Pipeline started at {datetime.now().isoformat()}")
    print(f"==================================================")
    
    # 1. Initialize database connection
    try:
        db = JobDatabase()
    except Exception as e:
        print(f"CRITICAL: Failed to initialize Google Sheets database. Pipeline aborting. Error: {e}")
        sys.exit(1)
        
    # 2. Run Ingestion (Scrape & Pre-Filter & Seen De-duplication)
    try:
        unseen_jobs = ingest_jobs(db, hours_old=24)
    except Exception as e:
        print(f"CRITICAL: Job ingestion failed. Pipeline aborting. Error: {e}")
        sys.exit(1)
        
    # Stats to track for email digest summary
    stats = {
        "total_scraped": len(unseen_jobs),
        "passed_count": 0
    }
    
    scored_jobs = []
    passing_jobs = []
    
    # 3. LLM Filter & Score (only if there are new unseen jobs)
    if unseen_jobs:
        try:
            # Send batch of unseen jobs to Groq API
            scored_jobs = filter_jobs_list(unseen_jobs, delay_sec=1.5)
            
            # Filter for passing jobs (match_score >= 5)
            passing_jobs = [job for job in scored_jobs if job.get("match_score", 0) >= 5]
            stats["passed_count"] = len(passing_jobs)
            
            print(f"Scoring complete. Total evaluated: {len(scored_jobs)}, Passed filter: {len(passing_jobs)}")
        except Exception as e:
            print(f"Error during LLM filtering: {e}")
            print("Will attempt to proceed with empty list to update database and notify.")
    else:
        print("No new unseen jobs found in ingestion. Skipping LLM scoring.")
        
    # 4. Update Database
    # We do database writes in try/except blocks so that failures here don't prevent the emailer from notifying the user.
    if scored_jobs:
        try:
            print("Writing processed jobs to 'jobs_seen' worksheet...")
            db.add_seen_jobs(scored_jobs)
        except Exception as e:
            print(f"Error writing to 'jobs_seen' worksheet: {e}")
            
        if passing_jobs:
            try:
                print("Writing passing jobs to 'passing_jobs' worksheet...")
                db.add_passing_jobs(passing_jobs)
            except Exception as e:
                print(f"Error writing to 'passing_jobs' worksheet: {e}")
                
    # 5. Send Daily Digest Email
    try:
        print(f"Triggering email dispatch...")
        email_sent = send_digest_email(passing_jobs, stats)
        if email_sent:
            print("Daily digest email sent successfully!")
        else:
            print("Failed to send daily digest email.")
    except Exception as e:
        print(f"Error executing email dispatch: {e}")
        
    print(f"==================================================")
    print(f"Pipeline run finished at {datetime.now().isoformat()}")
    print(f"==================================================")

if __name__ == "__main__":
    run_pipeline()
