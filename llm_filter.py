import os
import json
import time
from typing import List, Dict, Any
from pydantic import BaseModel, Field
from groq import Groq

# Define structured output schema using Pydantic
class JobEvaluation(BaseModel):
    match_score: int = Field(
        ..., 
        ge=0, 
        le=10, 
        description="Fit score from 0 (completely unsuitable) to 10 (perfect match) based on candidate profile."
    )
    domain: str = Field(
        ..., 
        description="Categorized domain: 'Data Scientist', 'Data Analyst', 'Machine Learning Engineer', or 'Reject'."
    )
    reject_reasons: List[str] = Field(
        default_factory=list,
        description="List of reasons for rejection if match_score < 5, or explanations for score reductions (e.g., capped experience)."
    )
    resume_highlights: List[str] = Field(
        default_factory=list,
        description="Exactly 2 bullet points describing how the candidate's skills map to the role. Must be empty if rejected."
    )

SYSTEM_PROMPT = """You are a precision job-filtering engine evaluating roles for an entry-level candidate.
Candidate Target Profile:
- Target Role: Fresher (0-2 years experience) Data Analyst, Data Scientist, Machine Learning Engineer.
- Target Location: Bangalore/Bengaluru (hybrid/on-site reporting to Bangalore) or explicitly "Remote - India".
- Tech Stack Priorities: Python, SQL, Power BI, Tableau, Excel, Pandas, NumPy, Scikit-learn, LangChain.

Strict Filtering Rules:
1. Location: Accept Bangalore/Bengaluru, hybrid roles reporting to Bangalore, or explicitly "Remote - India" / "India". Reject other specific cities (e.g. Pune, Mumbai).
2. Domain Exclusions: Accept Data Science, ML, Analytics. Strictly REJECT Data Engineering and DevOps. (Note: Do NOT reject a Data Science/ML role just because it mentions AWS/Azure/GCP as a nice-to-have or deployment tool. Only reject if Cloud Infrastructure/DevOps is the CORE focus of the role.)
3. Tech Stack: Prioritize the target tech stack.
4. Experience:
   - Accept 0-2 years (Freshers, new grads, PPO-track internships).
   - Cap the score at maximum 6/10 if the role demands 1-3 years.
   - Strictly REJECT (match_score=0, domain="Reject") any roles with hard requirements of 3+ years experience.
5. Scoring: 
   - If ANY hard criterion fails (wrong location, excluded domain, 3+ years exp, heavy cloud), set match_score=0 and domain="Reject".
   - For accepted roles, weight 50% core stack overlap and 50% experience fit.
6. Output: You must respond with a JSON object containing the keys: 'match_score', 'domain', 'reject_reasons', and 'resume_highlights'.
   - 'resume_highlights' must contain exactly 2 bullet points extracting the exact keywords from the JD that match the candidate's core tech stack. If the role is rejected, this list must be empty.
   - Provide clean JSON only. Do not wrap in markdown blocks like ```json ... ```. Do not output conversational filler.
"""

def evaluate_single_job(client: Groq, job: Dict[str, Any], retries: int = 2) -> Dict[str, Any]:
    """
    Evaluates a single job posting using the Groq API and validates the output with Pydantic.
    """
    model_name = "llama-3.3-70b-versatile"
    
    user_content = f"""Title: {job.get('title')}
Company: {job.get('company')}
Location: {job.get('location')}
URL: {job.get('job_url')}
Job Description:
{job.get('description', '')[:4000]}  # Limit description length to stay within context windows
"""

    for attempt in range(retries + 1):
        try:
            # We call the Groq completions endpoint forcing a JSON object output
            response = client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_content}
                ],
                response_format={"type": "json_object"},
                temperature=0.1,  # Low temperature for deterministic classification
            )
            
            raw_content = response.choices[0].message.content.strip()
            
            # Parse the JSON response
            data = json.loads(raw_content)
            
            # Validate output using Pydantic schema
            evaluation = JobEvaluation(**data)
            
            # Convert back to dict and append to job
            job_eval = evaluation.model_dump()
            
            # Final validation check: Ensure no highlights exist if match_score is 0 or domain is Reject
            if job_eval["match_score"] == 0 or job_eval["domain"] == "Reject":
                job_eval["match_score"] = 0
                job_eval["domain"] = "Reject"
                job_eval["resume_highlights"] = []
                
            return {**job, **job_eval}
            
        except json.JSONDecodeError as jde:
            print(f"JSON decode attempt {attempt + 1} failed for {job.get('title')}: {jde}")
            if attempt == retries:
                break
            time.sleep(1)
        except Exception as e:
            print(f"Error during LLM evaluation attempt {attempt + 1} for {job.get('title')}: {e}")
            if attempt == retries:
                break
            time.sleep(1)
            
    # Fallback response if API fails or parsing fails repeatedly
    print(f"Falling back to rejection for job: {job.get('title')} due to persistent errors.")
    return {
        **job,
        "match_score": 0,
        "domain": "Reject",
        "reject_reasons": ["Pipeline evaluation failure (Groq API or JSON decoding issue)"],
        "resume_highlights": []
    }

def filter_jobs_list(jobs: List[Dict[str, Any]], delay_sec: float = 1.0) -> List[Dict[str, Any]]:
    """
    Evaluates a list of unseen jobs using Groq API sequentially, adding a delay to avoid rate limits.
    """
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        print("Warning: GROQ_API_KEY environment variable is not set. LLM filtering will fail.")
        # Return all jobs rejected by default if API key is missing
        return [{**job, "match_score": 0, "domain": "Reject", "reject_reasons": ["Missing GROQ_API_KEY"]} for job in jobs]

    try:
        client = Groq(api_key=api_key)
    except Exception as e:
        print(f"Error initializing Groq client: {e}")
        return [{**job, "match_score": 0, "domain": "Reject", "reject_reasons": ["Groq Client Init Error"]} for job in jobs]

    evaluated_jobs = []
    total = len(jobs)
    model_name = "llama-3.3-70b-versatile"
    print(f"Evaluating {total} jobs with Groq {model_name}...")
    
    from concurrent.futures import ThreadPoolExecutor, as_completed
    
    def evaluate_with_delay(idx, job):
        # Stagger requests slightly to avoid hitting rate limits instantly
        time.sleep(idx * delay_sec)
        print(f"[{idx+1}/{total}] Evaluating: {job.get('title')} at {job.get('company')}...")
        return evaluate_single_job(client, job)

    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(evaluate_with_delay, idx, job): job for idx, job in enumerate(jobs)}
        for future in as_completed(futures):
            try:
                evaluated_job = future.result()
                evaluated_jobs.append(evaluated_job)
            except Exception as e:
                print(f"Error during parallel evaluation: {e}")
            
    return evaluated_jobs
