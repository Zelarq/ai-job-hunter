import re
import csv
import sys
import logging
from typing import Tuple, Optional
import requests
from bs4 import BeautifulSoup

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("detect_ats")

DEFAULT_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

# Regex detection patterns for common Applicant Tracking Systems (ATS)
ATS_PATTERNS = [
    # Greenhouse: boards.greenhouse.io/<token>
    ("greenhouse", re.compile(r"boards\.greenhouse\.io/(?:embed/job_board\?for=)?([a-zA-Z0-9_\-]+)", re.IGNORECASE)),
    ("greenhouse", re.compile(r"boards-api\.greenhouse\.io/v1/boards/([a-zA-Z0-9_\-]+)", re.IGNORECASE)),
    ("greenhouse", re.compile(r"grnh\.se/([a-zA-Z0-9_\-]+)", re.IGNORECASE)),
    
    # Lever: jobs.lever.co/<slug>
    ("lever", re.compile(r"jobs\.lever\.co/([a-zA-Z0-9_\-]+)", re.IGNORECASE)),
    ("lever", re.compile(r"api\.lever\.co/v0/postings/([a-zA-Z0-9_\-]+)", re.IGNORECASE)),
    
    # Ashby: jobs.ashbyhq.com/<board>
    ("ashby", re.compile(r"jobs\.ashbyhq\.com/([a-zA-Z0-9_\-]+)", re.IGNORECASE)),
    ("ashby", re.compile(r"ashbyhq\.com/posting-api/job-board/([a-zA-Z0-9_\-]+)", re.IGNORECASE)),
    
    # SmartRecruiters: jobs.smartrecruiters.com/<company>
    ("smartrecruiters", re.compile(r"jobs\.smartrecruiters\.com/([a-zA-Z0-9_\-]+)", re.IGNORECASE)),
    
    # Workable: apply.workable.com/<account>
    ("workable", re.compile(r"apply\.workable\.com/([a-zA-Z0-9_\-]+)", re.IGNORECASE)),
]

def scan_text_for_ats(text: str) -> Tuple[Optional[str], Optional[str]]:
    """Scans raw URL or HTML text for known ATS links and extracts token."""
    for ats_type, pattern in ATS_PATTERNS:
        match = pattern.search(text)
        if match:
            token = match.group(1).split("?")[0].split("#")[0].strip()
            # Filter out non-token keywords
            if token.lower() not in {"embed", "jobs", "apply", "careers", "search"}:
                return ats_type, token
    return None, None

def detect_ats(careers_url: str, timeout: int = 10) -> Tuple[str, str]:
    """
    Given a company careers URL, checks URL and follows HTTP response to detect ATS and token.
    Returns (ats_type, ats_token). Fallback is ('custom', '').
    """
    if not careers_url or not careers_url.strip():
        return "custom", ""
        
    url = careers_url.strip()
    
    # 1. First, check if the provided careers_url itself directly matches an ATS domain
    ats_type, token = scan_text_for_ats(url)
    if ats_type and token:
        logger.info(f"Direct URL match: {url} -> {ats_type} ({token})")
        return ats_type, token

    # 2. Fetch the HTML page and scan for embedded iframes, scripts, or links
    headers = {"User-Agent": DEFAULT_USER_AGENT}
    try:
        response = requests.get(url, headers=headers, timeout=timeout, allow_redirects=True)
        final_url = response.url
        
        # Check final redirected URL
        ats_type, token = scan_text_for_ats(final_url)
        if ats_type and token:
            logger.info(f"Redirect match: {final_url} -> {ats_type} ({token})")
            return ats_type, token

        html_content = response.text
        
        # Scan full HTML body
        ats_type, token = scan_text_for_ats(html_content)
        if ats_type and token:
            logger.info(f"HTML content match in {url} -> {ats_type} ({token})")
            return ats_type, token

        # Check BeautifulSoup parsed tags (iframes, a tags, script sources)
        soup = BeautifulSoup(html_content, "html.parser")
        
        # Check iframes
        for iframe in soup.find_all("iframe", src=True):
            ats_type, token = scan_text_for_ats(iframe["src"])
            if ats_type and token:
                logger.info(f"Iframe match in {url} -> {ats_type} ({token})")
                return ats_type, token

        # Check links
        for a_tag in soup.find_all("a", href=True):
            ats_type, token = scan_text_for_ats(a_tag["href"])
            if ats_type and token:
                logger.info(f"A-tag link match in {url} -> {ats_type} ({token})")
                return ats_type, token

    except Exception as e:
        logger.warning(f"Error fetching {url} during ATS detection: {e}")

    # Fallback to custom
    return "custom", ""

def update_companies_csv(csv_path: str = "companies.csv"):
    """
    Reads companies.csv, detects ATS for any missing entries,
    and updates the file in place.
    """
    logger.info(f"Reading target company list from {csv_path}...")
    rows = []
    updated_count = 0

    with open(csv_path, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or ["name", "careers_url", "ats_type", "ats_token", "priority", "notes"]
        for row in reader:
            ats_type = (row.get("ats_type") or "").strip()
            ats_token = (row.get("ats_token") or "").strip()
            careers_url = (row.get("careers_url") or "").strip()

            # If ats_type or token is missing, attempt auto-detection
            if (not ats_type or not ats_token) and careers_url:
                detected_type, detected_token = detect_ats(careers_url)
                if detected_type != "custom" and detected_token:
                    row["ats_type"] = detected_type
                    row["ats_token"] = detected_token
                    updated_count += 1
                    logger.info(f"Detected {row.get('name')}: {detected_type} / {detected_token}")
                elif not ats_type:
                    row["ats_type"] = "custom"
                    row["ats_token"] = ""
            rows.append(row)

    with open(csv_path, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    logger.info(f"Finished detection. Updated {updated_count} companies in {csv_path}.")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        target_url = sys.argv[1]
        t, tok = detect_ats(target_url)
        print(f"URL: {target_url}\nATS: {t}\nToken: {tok}")
    else:
        update_companies_csv()
