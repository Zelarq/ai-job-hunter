import logging
from typing import List, Dict, Any
import requests

logger = logging.getLogger("adapter_greenhouse")

def fetch_greenhouse_jobs(
    token: str, 
    company_name: str = "", 
    timeout: int = 15,
    user_agent: str = "Mozilla/5.0"
) -> List[Dict[str, Any]]:
    """
    Fetches job listings from Greenhouse Public Job Board API:
    https://boards-api.greenhouse.io/v1/boards/{token}/jobs
    
    Returns standard job dictionaries:
    [
        {
            "company": company_name or token,
            "title": str,
            "location": str,
            "url": str,
            "posted_date": str,
            "description": str,
            "ats_type": "greenhouse"
        }
    ]
    """
    if not token or not token.strip():
        logger.warning(f"Empty token provided for Greenhouse adapter (company: {company_name}).")
        return []

    clean_token = token.strip()
    endpoint = f"https://boards-api.greenhouse.io/v1/boards/{clean_token}/jobs"
    headers = {"User-Agent": user_agent}

    try:
        response = requests.get(endpoint, headers=headers, timeout=timeout)
        if response.status_code == 404:
            logger.warning(f"Greenhouse board not found (404) for token '{clean_token}'.")
            return []
        
        response.raise_for_status()
        data = response.json()
        raw_jobs = data.get("jobs", [])
        
        normalized_jobs = []
        for raw in raw_jobs:
            title = (raw.get("title") or "").strip()
            url = (raw.get("absolute_url") or "").strip()
            
            # Location is typically a dictionary with 'name'
            loc_obj = raw.get("location")
            if isinstance(loc_obj, dict):
                location = (loc_obj.get("name") or "").strip()
            elif isinstance(loc_obj, str):
                location = loc_obj.strip()
            else:
                location = ""

            posted_date = (raw.get("updated_at") or "")[:10]  # Extracts YYYY-MM-DD
            
            # Optional snippet if available
            description = (raw.get("content") or "").strip()

            if title and url:
                normalized_jobs.append({
                    "company": company_name or clean_token.capitalize(),
                    "title": title,
                    "location": location,
                    "url": url,
                    "posted_date": posted_date,
                    "description": description,
                    "ats_type": "greenhouse"
                })

        logger.info(f"Greenhouse [{clean_token}]: Fetched {len(normalized_jobs)} raw jobs.")
        return normalized_jobs

    except requests.exceptions.RequestException as re:
        logger.error(f"HTTP error fetching Greenhouse jobs for '{clean_token}': {re}")
        return []
    except Exception as e:
        logger.error(f"Unexpected error in Greenhouse adapter for '{clean_token}': {e}")
        return []

if __name__ == "__main__":
    import sys
    test_token = sys.argv[1] if len(sys.argv) > 1 else "databricks"
    jobs = fetch_greenhouse_jobs(test_token, "Databricks")
    print(f"Total jobs: {len(jobs)}")
    if jobs:
        print("Sample job:", jobs[0])
