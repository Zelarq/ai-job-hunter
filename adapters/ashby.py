import logging
from typing import List, Dict, Any
import requests

logger = logging.getLogger("adapter_ashby")

def fetch_ashby_jobs(
    board: str, 
    company_name: str = "", 
    timeout: int = 15,
    user_agent: str = "Mozilla/5.0"
) -> List[Dict[str, Any]]:
    """
    Fetches job listings from Ashby Public Job Board API:
    https://api.ashbyhq.com/posting-api/job-board/{board}
    
    Returns standard job dictionaries:
    [
        {
            "company": company_name or board,
            "title": str,
            "location": str,
            "url": str,
            "posted_date": str,
            "description": str,
            "ats_type": "ashby"
        }
    ]
    """
    if not board or not board.strip():
        logger.warning(f"Empty board token provided for Ashby adapter (company: {company_name}).")
        return []

    clean_board = board.strip()
    endpoint = f"https://api.ashbyhq.com/posting-api/job-board/{clean_board}"
    headers = {"User-Agent": user_agent}

    try:
        response = requests.get(endpoint, headers=headers, timeout=timeout)
        if response.status_code == 404:
            logger.warning(f"Ashby board not found (404) for board '{clean_board}'.")
            return []
            
        response.raise_for_status()
        data = response.json()
        raw_jobs = data.get("jobs", [])
        
        normalized_jobs = []
        for raw in raw_jobs:
            title = (raw.get("title") or "").strip()
            url = (raw.get("jobUrl") or raw.get("applyUrl") or "").strip()
            
            # Location can be string or address object
            location_val = raw.get("location")
            if isinstance(location_val, str):
                location = location_val.strip()
            elif isinstance(location_val, dict):
                location = location_val.get("name", "")
            else:
                location = ""
                
            # Secondary locations / remote
            is_remote = raw.get("isRemote", False)
            if is_remote and "remote" not in location.lower():
                location = f"{location} (Remote)".strip() if location else "Remote"

            published_at = (raw.get("publishedAt") or "")[:10]
            description = (raw.get("descriptionPlain") or "").strip()

            if title and url:
                normalized_jobs.append({
                    "company": company_name or clean_board.capitalize(),
                    "title": title,
                    "location": location,
                    "url": url,
                    "posted_date": published_at,
                    "description": description,
                    "ats_type": "ashby"
                })

        logger.info(f"Ashby [{clean_board}]: Fetched {len(normalized_jobs)} raw jobs.")
        return normalized_jobs

    except requests.exceptions.RequestException as re:
        logger.error(f"HTTP error fetching Ashby jobs for '{clean_board}': {re}")
        return []
    except Exception as e:
        logger.error(f"Unexpected error in Ashby adapter for '{clean_board}': {e}")
        return []

if __name__ == "__main__":
    import sys
    test_board = sys.argv[1] if len(sys.argv) > 1 else "ramp"
    jobs = fetch_ashby_jobs(test_board, "Ramp")
    print(f"Total jobs: {len(jobs)}")
    if jobs:
        print("Sample job title:", jobs[0].get("title"))
        print("Sample job location:", jobs[0].get("location"))
