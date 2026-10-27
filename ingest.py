import re
import os
import pandas as pd
from jobspy import scrape_jobs
from db import hash_job, JobDatabase
from seleniumbase import Driver
from bs4 import BeautifulSoup
import time

# Compile regex patterns for pre-filtering
# Exclude senior, mid-level (II/III), or managerial roles
SENIOR_EXCLUDE_RE = re.compile(
    r"\b(senior|sr|lead|principal|staff|architect|manager|director|head|vp|chief|expert|president|ii|iii|iv|v|level\s*[2-5]|mid-level)\b",
    re.IGNORECASE
)

# Reject obvious non-technical roles
NON_TECH_RE = re.compile(
    r"\b(sales|marketing|hr|recruiter|accountant|writer|designer|product owner|project manager|scrum master)\b",
    re.IGNORECASE
)

# Target role title keywords (must match at least one, including tech internships)
TARGET_ROLE_RE = re.compile(
    r"\b(data|machine learning|ml|ai|artificial intelligence|analytics|statistics|llm|genai|generative|algorithms|scientist|analyst|intern|internship|trainee|apprentice)\b",
    re.IGNORECASE
)

def pre_filter_job(title: str, location: str) -> bool:
    """
    Returns True if the job matches the entry-level Data/AI profile and location constraints,
    and False if it is non-technical, too senior, or in an invalid location.
    """
    title = str(title).strip()
    location = str(location).strip()
    
    # 1. Check title exclusions (Senior/Manager/Non-tech)
    if SENIOR_EXCLUDE_RE.search(title):
        return False
    if NON_TECH_RE.search(title):
        return False
        
    # 2. Check title inclusion (Must match target role keywords)
    if not TARGET_ROLE_RE.search(title):
        return False
        
    # 3. Location filtering
    loc_lower = location.lower()
    is_bangalore = "bangalore" in loc_lower or "bengaluru" in loc_lower or "karnataka" in loc_lower
    
    # Accept 'India' (often implies remote or unspecified nationwide), 'Remote'
    is_remote = "remote" in loc_lower or loc_lower == "india" or loc_lower == "anywhere"
    
    # If it is remote, verify it's remote India
    if is_remote:
        # Reject if remote for another country (e.g. remote US, remote UK)
        if "us" in loc_lower or "united states" in loc_lower or "uk" in loc_lower or "europe" in loc_lower:
            return False
            
    if not (is_bangalore or is_remote):
        return False
        
    return True

def scrape_naukri_jobs(search_terms: list[str], location: str) -> list[dict]:
    """
    Custom SeleniumBase scraper for Naukri.com using Undetected ChromeDriver (UC Mode)
    to bypass anti-bot systems.
    """
    print("[Naukri Scraper] Starting Naukri scraping...")
    jobs = []
    
    try:
        driver = None
        for attempt in range(3):
            try:
                driver = Driver(uc=True, headless=True)
                break
            except Exception as e:
                print(f"[Naukri Scraper] Driver init failed on attempt {attempt+1}: {e}")
                time.sleep(2)
        if not driver:
            print("[Naukri Scraper] Could not initialize Selenium driver. Skipping Naukri.")
            return jobs
            
        for term in search_terms:
            print(f"[Naukri Scraper] Scraping for term: '{term}'...")
            formatted_term = term.replace(' ', '-').lower()
            formatted_loc = location.replace(' ', '-').lower()
            url = f"https://www.naukri.com/{formatted_term}-jobs-in-{formatted_loc}"
            
            driver.uc_open_with_reconnect(url, 4)
            time.sleep(4) # Wait for page to load
            
            soup = BeautifulSoup(driver.get_page_source(), 'html.parser')
            job_cards = soup.find_all('div', class_='srp-jobtuple-wrapper')
            
            if not job_cards:
                print(f"[Naukri Scraper] No job cards found for '{term}'.")
                continue
                
            print(f"[Naukri Scraper] Found {len(job_cards)} job cards for '{term}'.")
            
            for card in job_cards:
                title_elem = card.find('a', class_='title')
                title = title_elem.text.strip() if title_elem else ""
                job_url = title_elem['href'] if title_elem and title_elem.has_attr('href') else ""
                
                company_elem = card.find('a', class_='comp-name')
                company = company_elem.text.strip() if company_elem else ""
                
                loc_elem = card.find('span', class_='locWdth')
                loc = loc_elem.text.strip() if loc_elem else ""
                
                desc_elem = card.find('span', class_='job-desc')
                desc = desc_elem.text.strip() if desc_elem else ""
                
                if title and company:
                    jobs.append({
                        "title": title,
                        "company": company,
                        "location": loc,
                        "job_url": job_url,
                        "description": desc,
                        "source": "naukri"
                    })
                    
    except Exception as e:
        print(f"[Naukri Scraper] Error during scraping: {e}")
    finally:
        try:
            driver.quit()
        except:
            pass
            
    return jobs

def ingest_jobs(db: JobDatabase, hours_old: int = 24) -> list[dict]:
    """
    Scrapes jobs from LinkedIn, Indeed, and Glassdoor using python-jobspy,
    applies pre-filters, deduplicates against Google Sheets seen jobs database,
    and returns a list of dictionaries containing fresh, unseen jobs.
    """
    search_terms = [
        "Data Analyst", 
        "Data Scientist", 
        "Machine Learning Engineer",
        "Junior Machine Learning Engineer",
        "Junior Generative AI / LLM Engineer",
        "Junior Data Scientist",
        "Data Analyst / Junior Business Data Analyst",
        "Junior Python Developer",
        "Junior BI Analyst / Power BI Developer",
        "AI Application Developer",
        "Cloud AI/ML Engineer"
    ]
    
    scraped_jobs_list = []
    
    print(f"Starting job ingestion for the past {hours_old} hours...")
    
    from concurrent.futures import ThreadPoolExecutor, as_completed
    
    def scrape_term(term: str):
        print(f"Scraping for term: '{term}'...")
        try:
            jobs_df = scrape_jobs(
                site_name=["linkedin", "indeed", "glassdoor", "google", "zip_recruiter"],
                search_term=term,
                location="Bangalore, India",
                results_wanted=25,
                hours_old=hours_old,
                country_indeed="India",
                linkedin_fetch_description=True
            )
            return term, jobs_df
        except Exception as e:
            print(f"Error scraping '{term}' using python-jobspy: {e}")
            return term, None

    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = {executor.submit(scrape_term, term): term for term in search_terms}
        for future in as_completed(futures):
            term, jobs_df = future.result()
            if jobs_df is not None and not jobs_df.empty:
                print(f"Scraped {len(jobs_df)} raw postings for '{term}'.")
                for _, row in jobs_df.iterrows():
                    title = str(row.get("title", "")) if not pd.isna(row.get("title")) else ""
                    company = str(row.get("company", "")) if not pd.isna(row.get("company")) else ""
                    location = str(row.get("location", "")) if not pd.isna(row.get("location")) else ""
                    job_url = str(row.get("job_url", "")) if not pd.isna(row.get("job_url")) else ""
                    description = str(row.get("description", "")) if not pd.isna(row.get("description")) else ""
                    site_source = str(row.get("site", "")) if not pd.isna(row.get("site")) else ""
                    
                    scraped_jobs_list.append({
                        "title": title,
                        "company": company,
                        "location": location,
                        "job_url": job_url,
                        "description": description,
                        "source": site_source
                    })
            else:
                print(f"No postings found for '{term}'.")
            
    # Include Naukri scraper results if any
    try:
        naukri_jobs = scrape_naukri_jobs(search_terms, "bangalore")
        scraped_jobs_list.extend(naukri_jobs)
    except Exception as e:
        print(f"Error running Naukri scraper: {e}")

    # Deduplicate in-memory by job_id hash
    unique_scraped = {}
    for job in scraped_jobs_list:
        job_id = hash_job(job["title"], job["company"])
        job["job_id"] = job_id
        # Keep the one with description if duplicates arise
        if job_id not in unique_scraped or (not unique_scraped[job_id]["description"] and job["description"]):
            unique_scraped[job_id] = job

    # Filter and check against Google Sheets seen jobs
    filtered_jobs = []
    skipped_count = 0
    duplicate_count = 0
    
    for job_id, job in unique_scraped.items():
        # Check database seen cache first
        if db.is_job_seen(job_id):
            duplicate_count += 1
            continue
            
        # Run pre-filtering regex rules
        if not pre_filter_job(job["title"], job["location"]):
            skipped_count += 1
            continue
            
        filtered_jobs.append(job)
        
    print(f"Ingestion summary:")
    print(f"- Total unique scraped: {len(unique_scraped)}")
    print(f"- Skipped as already seen: {duplicate_count}")
    print(f"- Skipped by pre-filter regex: {skipped_count}")
    print(f"- Passed to LLM evaluation: {len(filtered_jobs)}")
    
    return filtered_jobs
