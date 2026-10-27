import os
import json
import hashlib
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials

def hash_job(title: str, company: str) -> str:
    """
    Generates a unique 16-character hexadecimal hash of the job title and company.
    This serves as the unique identifier for a job posting.
    """
    try:
        normalized_title = str(title).lower().strip()
        normalized_company = str(company).lower().strip()
        raw_str = f"{normalized_title}|{normalized_company}"
        return hashlib.sha256(raw_str.encode('utf-8')).hexdigest()[:16]
    except Exception as e:
        print(f"Error generating job hash for {title} - {company}: {e}")
        # Return a fallback string hash
        fallback = f"{title}_{company}"
        return hashlib.sha256(fallback.encode('utf-8')).hexdigest()[:16]

class JobDatabase:
    def __init__(self, sheet_name=None):
        self.sheet_name = sheet_name or os.getenv("GOOGLE_SHEET_NAME", "JobHunter Tracker")
        self.sheet_url = os.getenv("GOOGLE_SHEET_URL")
        self.client = None
        self.spreadsheet = None
        self.jobs_seen_sheet = None
        self.passing_jobs_sheet = None
        self.seen_ids = set()
        
        try:
            self.client = self._authenticate()
            self.spreadsheet = self._open_or_create_spreadsheet()
            self.jobs_seen_sheet = self._get_or_create_worksheet("jobs_seen", ["job_id", "title", "company", "date_seen"])
            self.passing_jobs_sheet = self._get_or_create_worksheet(
                "passing_jobs", 
                ["job_id", "title", "company", "location", "url", "match_score", "domain", "reject_reasons", "resume_highlights", "date_added"]
            )
            # Cache of seen job IDs for fast lookups
            self._load_seen_cache()
        except Exception as e:
            print(f"Failed to initialize JobDatabase: {e}")
            raise e

    def _authenticate(self):
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]
        
        # 1. Try environment variable containing the service account JSON contents
        creds_json = os.getenv("GOOGLE_SHEETS_CREDS_JSON")
        if creds_json:
            try:
                creds_dict = json.loads(creds_json)
                creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
                return gspread.authorize(creds)
            except Exception as e:
                print(f"Error loading credentials from GOOGLE_SHEETS_CREDS_JSON: {e}")
        
        # 2. Try loading from a credentials.json file
        cred_path = os.getenv("GOOGLE_SHEETS_CREDS_PATH", "credentials.json")
        if os.path.exists(cred_path):
            try:
                creds = Credentials.from_service_account_file(cred_path, scopes=scopes)
                return gspread.authorize(creds)
            except Exception as e:
                print(f"Error loading credentials from {cred_path}: {e}")
                
        raise FileNotFoundError("Google Sheets credentials not found. Please provide 'credentials.json' or set GOOGLE_SHEETS_CREDS_JSON.")

    def _open_or_create_spreadsheet(self):
        if self.sheet_url:
            try:
                print(f"Opening spreadsheet by URL...")
                return self.client.open_by_url(self.sheet_url)
            except Exception as e:
                print(f"Failed to open spreadsheet by URL: {e}")
                raise e
        try:
            return self.client.open(self.sheet_name)
        except gspread.SpreadsheetNotFound:
            try:
                print(f"Spreadsheet '{self.sheet_name}' not found. Creating a new one...")
                sh = self.client.create(self.sheet_name)
                # Note: The service account owns this sheet. The user needs to share it or access it via API.
                return sh
            except Exception as e:
                print(f"Failed to create new spreadsheet '{self.sheet_name}': {e}")
                raise e
        except Exception as e:
            print(f"Error opening spreadsheet '{self.sheet_name}': {e}")
            raise e

    def _get_or_create_worksheet(self, name, headers):
        try:
            return self.spreadsheet.worksheet(name)
        except gspread.WorksheetNotFound:
            try:
                print(f"Worksheet '{name}' not found. Creating a new one...")
                ws = self.spreadsheet.add_worksheet(title=name, rows="1000", cols=str(len(headers)))
                ws.append_row(headers)
                return ws
            except Exception as e:
                print(f"Failed to create worksheet '{name}': {e}")
                raise e
        except Exception as e:
            print(f"Error opening worksheet '{name}': {e}")
            raise e

    def _load_seen_cache(self):
        try:
            # Fetch all job_ids from the first column of the jobs_seen tab
            # col_values(1) gets everything including the header
            col_vals = self.jobs_seen_sheet.col_values(1)
            if len(col_vals) > 1:
                self.seen_ids = set(col_vals[1:])  # Skip the header
            else:
                self.seen_ids = set()
            print(f"Successfully loaded {len(self.seen_ids)} job_ids intoSeen cache.")
        except Exception as e:
            print(f"Warning: Could not fetch initial seen jobs cache: {e}. Defaulting to empty cache.")
            self.seen_ids = set()

    def is_job_seen(self, job_id: str) -> bool:
        """Checks if the job_id exists in the local seen cache."""
        return job_id in self.seen_ids

    def add_seen_jobs(self, jobs: list[dict]):
        """
        Appends a list of jobs to the 'jobs_seen' sheet in a single batch.
        Updates the local cache with the new job IDs.
        """
        if not jobs:
            return
            
        rows_to_append = []
        date_seen = datetime.now().isoformat()
        
        for job in jobs:
            job_id = job.get("job_id")
            if job_id and job_id not in self.seen_ids:
                rows_to_append.append([
                    job_id,
                    job.get("title", ""),
                    job.get("company", ""),
                    job.get("location", ""),
                    date_seen,
                    job.get("job_url", "")
                ])
                self.seen_ids.add(job_id)
                
        if rows_to_append:
            try:
                self.jobs_seen_sheet.append_rows(rows_to_append)
                print(f"Successfully appended {len(rows_to_append)} jobs to 'jobs_seen' sheet.")
            except Exception as e:
                print(f"Error writing batch of seen jobs to Google Sheet: {e}")

    def add_passing_jobs(self, jobs: list[dict]):
        """
        Appends a list of passing jobs (match_score >= 5) to the 'passing_jobs' sheet in a single batch.
        """
        if not jobs:
            return
            
        rows_to_append = []
        date_added = datetime.now().isoformat()
        
        for job in jobs:
            reject_reasons = json.dumps(job.get("reject_reasons", []))
            resume_highlights = json.dumps(job.get("resume_highlights", []))
            
            rows_to_append.append([
                job.get("job_id", ""),
                job.get("title", ""),
                job.get("company", ""),
                job.get("location", ""),
                job.get("job_url", ""),
                job.get("match_score", 0),
                job.get("domain", ""),
                reject_reasons,
                resume_highlights,
                date_added
            ])
            
        if rows_to_append:
            try:
                self.passing_jobs_sheet.append_rows(rows_to_append)
                print(f"Successfully appended {len(rows_to_append)} passing jobs to 'passing_jobs' sheet.")
            except Exception as e:
                print(f"Error writing batch of passing jobs to Google Sheet: {e}")
