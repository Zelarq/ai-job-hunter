import logging
from datetime import datetime
from typing import List, Dict, Any
import requests

logger = logging.getLogger("adapter_lever")

def fetch_lever_jobs(
    slug: str, 
    company_name: str = "", 
    timeout: int = 15,
    user_agent: str = "Mozilla/5.0"
) -> List[Dict[str, Any]]:
    """
    Fetches job listings from Lever Postings API:
    https://api.lever.co/v0/postings/{slug}?mode=json
    
    Returns standard job dictionaries:
    [
        {
            "company": company_name or slug,
            "title": str,
            "location": str,
            "url": str,
            "posted_date": str,
            "description": str,
            "ats_type": "lever"
        }
    ]
    """
    if not slug or not slug.strip():
        logger.warning(f"Empty slug provided for Lever adapter (company: {company_name}).")
        return []

    clean_slug = slug.strip()
    endpoint = f"https://api.lever.co/v0/postings/{clean_slug}?mode=json"
    headers = {"User-Agent": user_agent}

    try:
        response = requests.get(endpoint, headers=headers, timeout=timeout)
        if response.status_code == 404:
            logger.warning(f"Lever board not found (404) for slug '{clean_slug}'.")
            return []
            
        response.raise_for_status()
        raw_postings = response.json()
        
        # Lever API returns a top-level list
        if not isinstance(raw_postings, list):
            logger.warning(f"Unexpected response format from Lever for '{clean_slug}': {type(raw_postings)}")
            return []

        normalized_jobs = []
        for raw in raw_postings:
            title = (raw.get("text") or "").strip()
            url = (raw.get("hostedUrl") or raw.get("applyUrl") or "").strip()
            
            # Categories hold location details
            categories = raw.get("categories") or {}
            location = (categories.get("location") or "").strip()
            
            # Workplaces / additional locations if available
            workplace_type = raw.get("workplaceType", "")
            if workplace_type and workplace_type.lower() == "remote":
                location = f"{location} (Remote)".strip()

            # Date created (epoch in ms)
            created_at_ms = raw.get("createdAt")
            if created_at_ms:
                try:
                    posted_date = datetime.fromtimestamp(created_at_ms / 1000.0).strftime("%Y-%m-%d")
                except Exception:
                    posted_date = ""
            else:
                posted_date = ""

            description = (raw.get("descriptionPlain") or "").strip()

            if title and url:
                normalized_jobs.append({
                    "company": company_name or clean_slug.capitalize(),
                    "title": title,
                    "location": location,
                    "url": url,
                    "posted_date": posted_date,
                    "description": description,
                    "ats_type": "lever"
                })

        logger.info(f"Lever [{clean_slug}]: Fetched {len(normalized_jobs)} raw jobs.")
        return normalized_jobs

    except requests.exceptions.RequestException as re:
        logger.error(f"HTTP error fetching Lever jobs for '{clean_slug}': {re}")
        return []
    except Exception as e:
        logger.error(f"Unexpected error in Lever adapter for '{clean_slug}': {e}")
        return []

if __name__ == "__main__":
    import sys
    test_slug = sys.argv[1] if len(sys.argv) > 1 else "urbancompany"
    jobs = fetch_lever_jobs(test_slug, "Urban Company")
    print(f"Total jobs: {len(jobs)}")
    if jobs:
        print("Sample job title:", jobs[0].get("title"))
        print("Sample job location:", jobs[0].get("location"))
