# Bangalore Career-Page Job Scraper

A reliable, anti-bot-resilient job ingestion engine that directly queries official Applicant Tracking System (ATS) APIs (Greenhouse, Lever, Ashby) and custom career pages for **Fresher AI/ML, Data Science, and Data Analyst** roles in **Bangalore / Bengaluru**.

---

## 📁 Project Structure

```
├── companies.csv        # Target company list (name, URL, ATS type, token, priority)
├── config.yaml          # Filtering keywords (locations, roles, fresher boosts, exclusions)
├── main.py              # Pipeline orchestrator: iterates companies, filters, saves, and reports
├── detect.py            # Automatic ATS detection tool for career URLs
├── filters.py           # Precision location, role, experience, and fresher filtering rules
├── storage.py           # SQLite database management, deduplication, and CSV export
├── adapters/
│   ├── __init__.py
│   ├── greenhouse.py    # Greenhouse Public Board API adapter
│   ├── lever.py         # Lever Postings JSON API adapter
│   ├── ashby.py         # Ashby Public Job Board API adapter
│   └── custom.py        # Custom HTML career page parser with manual review fallback
├── data/
│   ├── jobs.db          # Persistent SQLite database with deduplication indexing
│   └── new_jobs_*.csv   # Daily exports of newly discovered postings
└── logs/
    └── run.log          # Detailed execution logs
```

---

## 🚀 How to Run

### 1. Manual Execution
Run the scraper directly using the virtual environment Python:
```powershell
.\venv\Scripts\python.exe main.py
```
Or double-click `run_daily.bat`.

### 2. Auto-Detect ATS for New Companies
If you add companies with only a `careers_url` in [companies.csv](file:///d:/collage/JobHunter%20AI%20Agent/companies.csv):
```powershell
.\venv\Scripts\python.exe detect.py
```
Or test an individual URL:
```powershell
.\venv\Scripts\python.exe detect.py "https://boards.greenhouse.io/stripe"
```

---

## ⚙️ Filter Configuration (`config.yaml`)

- **Locations**: Bangalore, Bengaluru, Karnataka, Blr, and India-wide remote roles (strictly excludes foreign remote US/UK/EU).
- **Target Roles**: `ai`, `ml`, `machine learning`, `data scientist`, `data analyst`, `data engineer`, `nlp`, `computer vision`, `llm`, `genai`.
- **Fresher Boost**: `trainee`, `graduate`, `associate`, `junior`, `entry`, `intern`, `0-1`, `0-2` years.
- **Exclusions**: `senior`, `lead`, `principal`, `staff`, `manager`, `architect`, `director`, `vp`, `iii`, `iv`, `level 3+`.
- **Experience Check**: Regex drops any posting requiring 3+ years of experience.

---

## ⏰ Scheduling Daily Runs (Phase 8)

### Windows Task Scheduler
1. Open **Task Scheduler** (`taskschd.msc`).
2. Click **Create Basic Task** -> Name it `Bangalore Career Job Scraper`.
3. Set Trigger to **Daily** at your preferred time (e.g. 09:00 AM).
4. Action -> **Start a program**:
   - **Program/script**: `D:\collage\JobHunter AI Agent\run_daily.bat`
   - **Start in**: `D:\collage\JobHunter AI Agent`
5. Finish. It will automatically run daily, deduplicate postings, and output a daily CSV report in `data/`.
