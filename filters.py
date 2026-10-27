import re
from typing import Tuple, Dict, Any, Optional
import yaml

def load_config(config_path: str = "config.yaml") -> Dict[str, Any]:
    """Loads configuration dictionary from YAML file."""
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

# Precompile helper regex for word-boundary matching
def _contains_word(text: str, keyword: str) -> bool:
    """Checks if keyword exists in text as a distinct word/phrase."""
    escaped_kw = re.escape(keyword)
    pattern = rf"(?:\b|_){escaped_kw}(?:\b|_)"
    return bool(re.search(pattern, text, re.IGNORECASE))

def check_location(location: str, config: Dict[str, Any]) -> Tuple[bool, str]:
    """
    Checks if job location matches Bangalore/Bengaluru/Karnataka or Remote India.
    """
    if not location:
        return False, "Missing location"

    loc_lower = location.lower().strip()
    loc_cfg = config.get("locations", {})
    
    # 1. Direct Bangalore / Karnataka check
    include_list = loc_cfg.get("include", ["bangalore", "bengaluru", "karnataka"])
    for city in include_list:
        if city in loc_lower:
            return True, f"Matched local location: {city}"

    # 2. Remote check
    if loc_cfg.get("allow_remote_india", True):
        # Exclude foreign countries
        for foreign in loc_cfg.get("remote_exclude", []):
            if foreign in loc_lower:
                return False, f"Excluded foreign location: {foreign}"

        # Check explicit India remote
        for rem_kw in loc_cfg.get("remote_keywords", []):
            if rem_kw in loc_lower:
                return True, f"Matched remote India keyword: {rem_kw}"

        # Unspecified Remote or India
        if loc_lower in {"remote", "india", "remote, india", "india (remote)"}:
            return True, "Matched generic Remote/India"

    return False, f"Location '{location}' is not Bangalore or Remote India"

def check_role(title: str, config: Dict[str, Any]) -> Tuple[bool, str]:
    """
    Checks if job title matches target AI/ML/Data role keywords.
    Uses word boundaries to prevent false positives (e.g. 'email' matching 'ai').
    """
    if not title:
        return False, "Missing job title"

    role_keywords = config.get("role_keywords", [])
    for kw in role_keywords:
        if _contains_word(title, kw):
            return True, f"Matched role keyword: '{kw}'"

    return False, "Title does not match any target AI/ML/Data keywords"

def check_title_exclusions(title: str, config: Dict[str, Any]) -> Tuple[bool, str]:
    """
    Checks if job title contains senior, leadership, or excluded keywords.
    """
    if not title:
        return False, "Missing job title"

    exclusions = config.get("title_exclusions", [])
    for exc in exclusions:
        if _contains_word(title, exc):
            return True, f"Excluded by senior/leadership keyword: '{exc}'"

    return False, "No exclusion keywords found"

def check_experience_exclusions(
    title: str, 
    description: str, 
    config: Dict[str, Any]
) -> Tuple[bool, str]:
    """
    Checks if posting explicitly demands 3+ years of experience.
    """
    exp_cfg = config.get("experience", {})
    patterns = exp_cfg.get("regex_patterns", [r"\b([3-9]|\d{2,})\+?\s*(?:to\s*\d+\s*)?(?:years?|yrs?)\b"])
    
    # Check title first
    for pat in patterns:
        match = re.search(pat, title, re.IGNORECASE)
        if match:
            return True, f"Title requires {match.group(0)} experience"

    # Check description snippet if provided
    if description:
        # Search first 2000 chars where requirements are usually listed
        snippet = description[:2000]
        for pat in patterns:
            match = re.search(pat, snippet, re.IGNORECASE)
            if match:
                return True, f"Description specifies {match.group(0)} experience"

    return False, "Experience within eligible fresher range (0-2 years)"

def is_fresher_or_intern(title: str, description: str, config: Dict[str, Any]) -> Tuple[bool, str]:
    """
    Checks if posting explicitly targets freshers, new grads, or interns (0-1 or 0-2 years).
    Returns (is_match, tag_name).
    """
    fresher_kws = config.get("fresher_keywords", [])
    
    # Check for internship explicitly
    intern_kws = ["intern", "internship", "internships", "co-op", "coop", "apprentice", "trainee", "student"]
    for kw in intern_kws:
        if _contains_word(title, kw):
            return True, "Internship"

    # Check title for other fresher keywords
    for kw in fresher_kws:
        if _contains_word(title, kw):
            return True, f"Fresher ({kw})"

    # Check description snippet if provided
    if description:
        snippet = description[:1500]
        for kw in intern_kws:
            if _contains_word(snippet, kw):
                return True, "Internship (in description)"
        for kw in fresher_kws:
            if _contains_word(snippet, kw):
                return True, f"Fresher (in description: {kw})"

    return False, "Standard Entry-Level (0-2 years)"

def filter_job(job: Dict[str, Any], config: Dict[str, Any]) -> Tuple[bool, str, Dict[str, Any]]:
    """
    Main pipeline filter for a single job posting.
    Enforces:
    1. Bangalore / Remote India location
    2. No Senior, Lead, or Mid-level (II, III, Staff, Manager) titles
    3. Target AI/ML/Data roles or internships
    4. Strict experience ceiling (rejects > 2 years: 2.5+, 3+, 4+, 5+, 2-4 yrs, etc.)
    5. Flags and supports Internships and Freshers (0-1 / 0-2 years)
    """
    title = job.get("title", "")
    location = job.get("location", "")
    description = job.get("description", "")

    # 1. Location Filter
    loc_ok, loc_reason = check_location(location, config)
    if not loc_ok:
        return False, loc_reason, {"filter_stage": "location"}

    # 2. Title Senior / Mid-level Exclusion (e.g. Senior, Lead, II, III, Staff)
    is_excluded, exc_reason = check_title_exclusions(title, config)
    if is_excluded:
        return False, exc_reason, {"filter_stage": "title_exclusion"}

    # 3. Role Title Inclusion (Must be AI, ML, Data, or AI/Data Intern)
    role_ok, role_reason = check_role(title, config)
    # Special check: If title is "Data Intern" or "AI Intern" or "ML Intern"
    if not role_ok and any(k in title.lower() for k in ["data", "ai", "ml", "analytics"]) and "intern" in title.lower():
        role_ok = True
        role_reason = "Matched Data/AI Internship title"

    if not role_ok:
        return False, role_reason, {"filter_stage": "role_keyword"}

    # 4. Strict Experience Filter (rejects >2 years: 2.5+, 3+, 4+, 5+ years, 2-4 yrs, etc.)
    has_high_exp, exp_reason = check_experience_exclusions(title, description, config)
    if has_high_exp:
        return False, exp_reason, {"filter_stage": "experience"}

    # 5. Check Fresher / Internship Tag
    is_fresher, tag = is_fresher_or_intern(title, description, config)

    # 6. Optional strict check if user only wants explicit intern/fresher terms in title
    require_explicit = config.get("experience", {}).get("require_explicit_fresher_or_intern", False)
    if require_explicit and not is_fresher:
        return False, "Not explicitly tagged with fresher or intern keywords", {"filter_stage": "explicit_fresher_required"}

    return True, f"Passed all filters [{tag}]", {
        "filter_stage": "passed",
        "is_fresher_boost": is_fresher,
        "tag": tag,
        "matched_role": role_reason
    }

if __name__ == "__main__":
    cfg = load_config()
    test_jobs = [
        {"title": "Junior Data Analyst", "location": "Bangalore, India", "description": "0-1 years exp"},
        {"title": "Data Science Intern", "location": "Bengaluru, Karnataka", "description": "Internship for students/grads"},
        {"title": "AI/ML Intern", "location": "Bangalore", "description": "No prior experience required"},
        {"title": "Data Analyst (0-2 yrs)", "location": "Bangalore", "description": "Fresher or 1-2 years experience"},
        {"title": "SDE II - AI", "location": "Bangalore", "description": "2-4 years experience"},
        {"title": "Senior Machine Learning Engineer", "location": "Bangalore, India", "description": "5+ years"},
        {"title": "Data Scientist", "location": "Bangalore", "description": "Requires 3+ years experience"},
        {"title": "Data Engineer", "location": "Remote - India", "description": "1 year experience"},
    ]
    for j in test_jobs:
        passed, reason, meta = filter_job(j, cfg)
        print(f"[{'PASS' if passed else 'FAIL'}] {j['title']} ({j['location']}) -> {reason}")
