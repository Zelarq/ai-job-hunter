import logging
from typing import List, Dict, Any
import requests
from bs4 import BeautifulSoup

logger = logging.getLogger("adapter_custom")

def fetch_custom_jobs(
    careers_url: str, 
    company_name: str = "", 
    timeout: int = 15,
    user_agent: str = "Mozilla/5.0"
) -> List[Dict[str, Any]]:
    """
    Handles custom career pages (Phase 5).
    Step 1: Check if page returns static HTML with job links/cards.
    Step 2: If Javascript-heavy / blocked, log as manual review.
    """
    if not careers_url or not careers_url.strip():
        return []

    url = careers_url.strip()
    headers = {"User-Agent": user_agent}

    try:
        response = requests.get(url, headers=headers, timeout=timeout)
        if response.status_code != 200:
            logger.warning(f"Custom page {url} returned status {response.status_code}. Marking for manual check.")
            return []

        soup = BeautifulSoup(response.text, "html.parser")
        
        # Look for typical job card or listing patterns
        job_links = []
        for a in soup.find_all("a", href=True):
            href = a["href"]
            text = a.get_text(strip=True)
            # If href or text contains job-related keywords
            if any(k in href.lower() for k in ["/job/", "/jobs/", "/careers/", "/position/"]) and len(text) > 4:
                full_url = href if href.startswith("http") else requests.compat.urljoin(url, href)
                job_links.append({
                    "company": company_name or "Custom",
                    "title": text,
                    "location": "Bangalore",  # default context if on Bangalore careers page
                    "url": full_url,
                    "posted_date": "",
                    "description": "",
                    "ats_type": "custom"
                })

        if job_links:
            logger.info(f"Custom [{company_name}]: Found {len(job_links)} candidate job links via HTML parsing.")
            return job_links
        else:
            logger.info(f"Custom [{company_name}]: No direct HTML jobs found at {url}. Logged for manual review.")
            return []

    except Exception as e:
        logger.warning(f"Error checking custom careers page {url}: {e}. Logged for manual review.")
        return []
