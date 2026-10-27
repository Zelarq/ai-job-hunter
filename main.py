import os
import sys
import csv
import time
import logging
from datetime import datetime
from typing import Dict, Any, List

from dotenv import load_dotenv

# Ensure environment variables are loaded
load_dotenv()

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from filters import load_config, filter_job
from storage import init_db, upsert_job, get_new_jobs_for_date, export_new_jobs_to_csv, get_storage_stats
from emailer import send_digest_email
from adapters import (
    fetch_greenhouse_jobs,
    fetch_lever_jobs,
    fetch_ashby_jobs,
    fetch_custom_jobs
)

def setup_logger(log_file: str = "logs/run.log") -> logging.Logger:
    """Configures multi-handler logging to file and console."""
    os.makedirs(os.path.dirname(log_file), exist_ok=True)
    logger = logging.getLogger("bangalore_scraper")
    logger.setLevel(logging.INFO)
    
    # Avoid duplicate handlers if re-run
    if logger.handlers:
        return logger

    # File Handler
    fh = logging.FileHandler(log_file, encoding="utf-8")
    fh.setLevel(logging.INFO)
    fh_formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    fh.setFormatter(fh_formatter)
    logger.addHandler(fh)

    # Console Handler
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch_formatter = logging.Formatter("[%(levelname)s] %(message)s")
    ch.setFormatter(ch_formatter)
    logger.addHandler(ch)

    return logger

def load_companies(csv_path: str = "companies.csv") -> List[Dict[str, str]]:
    """Loads target companies from companies.csv."""
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"Missing target companies file: {csv_path}")

    companies = []
    with open(csv_path, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("name") and not row["name"].startswith("#"):
                companies.append({
                    "name": row.get("name", "").strip(),
                    "careers_url": row.get("careers_url", "").strip(),
                    "ats_type": row.get("ats_type", "custom").strip().lower(),
                    "ats_token": row.get("ats_token", "").strip(),
                    "priority": row.get("priority", "2").strip(),
                    "notes": row.get("notes", "").strip()
                })
    return companies

def scrape_company_jobs(
    company: Dict[str, str], 
    config: Dict[str, Any], 
    logger: logging.Logger
) -> List[Dict[str, Any]]:
    """
    Selects the appropriate ATS adapter and fetches jobs.
    Safely wrapped in try/except so one failing company never stops the pipeline.
    """
    name = company["name"]
    ats_type = company["ats_type"]
    token = company["ats_token"]
    careers_url = company["careers_url"]
    
    timeout = config.get("app", {}).get("request_timeout", 15)
    user_agent = config.get("app", {}).get("user_agent", "Mozilla/5.0")

    try:
        if ats_type == "greenhouse":
            return fetch_greenhouse_jobs(token or name.lower(), name, timeout, user_agent)
        elif ats_type == "lever":
            return fetch_lever_jobs(token or name.lower(), name, timeout, user_agent)
        elif ats_type == "ashby":
            return fetch_ashby_jobs(token or name.lower(), name, timeout, user_agent)
        else:
            # Custom careers page or fallback
            return fetch_custom_jobs(careers_url, name, timeout, user_agent)
    except Exception as e:
        logger.error(f"Failed to fetch jobs for '{name}' via {ats_type}: {e}")
        return []

def run_scraper():
    """Main pipeline loop."""
    start_time = datetime.now()
    run_date = start_time.strftime("%Y-%m-%d")

    config = load_config("config.yaml")
    log_file = config.get("logging", {}).get("log_file", "logs/run.log")
    logger = setup_logger(log_file)

    db_path = config.get("storage", {}).get("db_path", "data/jobs.db")
    init_db(db_path)

    logger.info("================================================================================")
    logger.info(f"Bangalore Career-Page Job Scraper started at {start_time.isoformat()}")
    logger.info("Target: Fresher AI/ML, Data Science, and Data Analyst roles in Bangalore")
    logger.info("================================================================================")

    companies = load_companies("companies.csv")
    logger.info(f"Loaded {len(companies)} target companies from companies.csv.")

    rate_limit_sleep = config.get("app", {}).get("rate_limit_sleep", 1.5)

    stats = {
        "companies_checked": 0,
        "raw_postings_scraped": 0,
        "matched_postings": 0,
        "new_jobs_saved": 0
    }

    all_matched_today = []

    for idx, company in enumerate(companies, start=1):
        name = company["name"]
        ats_type = company["ats_type"]
        token = company["ats_token"]
        
        logger.info(f"[{idx}/{len(companies)}] Fetching {name} (ATS: {ats_type}, Token: '{token}')...")
        stats["companies_checked"] += 1

        raw_jobs = scrape_company_jobs(company, config, logger)
        stats["raw_postings_scraped"] += len(raw_jobs)

        company_matches = 0
        company_new = 0

        for raw in raw_jobs:
            passed, reason, meta = filter_job(raw, config)
            if passed:
                stats["matched_postings"] += 1
                company_matches += 1
                
                # Tag notes with company priority or filter boost
                tag = meta.get("tag", "Fresher (0-2 yrs)")
                notes = company.get("notes", "")
                raw["notes"] = f"[{tag}] {notes}".strip()

                # Save to SQLite database (deduplicating by URL)
                is_new, record = upsert_job(raw, run_date, db_path)
                if is_new:
                    stats["new_jobs_saved"] += 1
                    company_new += 1
                    all_matched_today.append(record)
                    logger.info(f"  -> NEW MATCH: {record['title']} | {record['location']} ({record['url']})")

        logger.info(f"  Summary for {name}: {len(raw_jobs)} raw, {company_matches} matched filters, {company_new} brand-new.")

        # Respectful rate limiting between companies
        time.sleep(rate_limit_sleep)

    # Export daily CSV
    csv_dir = config.get("storage", {}).get("csv_export_dir", "data")
    new_jobs = get_new_jobs_for_date(run_date, db_path)
    csv_file = export_new_jobs_to_csv(new_jobs, csv_dir, run_date)

    total_stats = get_storage_stats(db_path)
    elapsed = (datetime.now() - start_time).total_seconds()

    logger.info("================================================================================")
    logger.info("RUN COMPLETE SUMMARY")
    logger.info(f"- Execution Time: {elapsed:.2f} seconds")
    logger.info(f"- Companies Checked: {stats['companies_checked']}")
    logger.info(f"- Total Raw Postings Analyzed: {stats['raw_postings_scraped']}")
    logger.info(f"- Total Filter Matches: {stats['matched_postings']}")
    logger.info(f"- Brand-New Jobs Discovered Today: {len(new_jobs)}")
    logger.info(f"- Daily CSV Export: {csv_file}")
    logger.info(f"- Total Cumulative Jobs in DB: {total_stats['total_jobs']}")
    logger.info("================================================================================")

    # Print clean table of new jobs to console
    if new_jobs:
        print("\n" + "="*80)
        print(f"[*] NEW BANGALORE FRESHER AI/ML & DATA JOBS DISCOVERED TODAY ({len(new_jobs)}):")
        print("="*80)
        for i, j in enumerate(new_jobs, 1):
            print(f"{i}. [{j['company']}] {j['title']}")
            print(f"   Location: {j['location']}")
            print(f"   URL: {j['url']}")
            print("-" * 80)
    else:
        print("\n[i] No brand-new jobs were added today. Existing postings have been refreshed in SQLite.")

    # Phase 8: Email Dispatch
    email_cfg = config.get("email", {})
    if email_cfg.get("enabled", True):
        send_even_if_empty = email_cfg.get("send_even_if_empty", False)
        if new_jobs or send_even_if_empty:
            receiver = os.getenv("RECEIVER_EMAIL")
            logger.info(f"Dispatching daily digest email for {len(new_jobs)} jobs to {receiver}...")
            email_stats = {
                "total_scraped": stats["raw_postings_scraped"],
                "passed_count": len(new_jobs)
            }
            try:
                sent = send_digest_email(new_jobs, email_stats)
                if sent:
                    logger.info("Daily digest email sent successfully!")
                else:
                    logger.warning("Failed to dispatch daily digest email.")
            except Exception as e:
                logger.error(f"Error during email dispatch: {e}")
        else:
            logger.info("No brand-new jobs found today. Skipping email dispatch (send_even_if_empty=False).")

if __name__ == "__main__":
    run_scraper()
