import os
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import List, Dict, Any
from jinja2 import Template
from dotenv import load_dotenv

# Ensure environment variables are loaded
load_dotenv()

# Inline CSS Email Template for Gmail compatibility
EMAIL_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>JobHunter AI Agent Daily Digest</title>
</head>
<body style="margin: 0; padding: 0; font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; background-color: #f6f8fa; color: #24292e;">
    <table border="0" cellpadding="0" cellspacing="0" width="100%" style="background-color: #f6f8fa; padding: 20px 0;">
        <tr>
            <td align="center">
                <!-- Outer Container -->
                <table border="0" cellpadding="0" cellspacing="0" width="600" style="background-color: #ffffff; border: 1px solid #e1e4e8; border-radius: 6px; overflow: hidden; box-shadow: 0 4px 6px rgba(0,0,0,0.04);">
                    
                    <!-- Header -->
                    <tr>
                        <td style="background: linear-gradient(135deg, #1f4068, #162447); padding: 30px 40px; text-align: left;">
                            <h1 style="color: #ffffff; margin: 0; font-size: 24px; font-weight: 700; letter-spacing: -0.5px;">JobHunter AI v2.0</h1>
                            <p style="color: #8f9fc2; margin: 5px 0 0 0; font-size: 14px; font-weight: 500;">Daily Entry-Level Data & AI Digest</p>
                        </td>
                    </tr>
                    
                    <!-- Execution Status Banner -->
                    <tr>
                        <td style="padding: 20px 40px; background-color: #e3f2fd; border-bottom: 1px solid #e1e4e8;">
                            <table border="0" cellpadding="0" cellspacing="0" width="100%">
                                <tr>
                                    <td style="font-size: 13px; color: #0d47a1; font-weight: 600;">
                                        Run Date: {{ run_date }}
                                    </td>
                                    <td align="right" style="font-size: 13px; color: #0d47a1; font-weight: 600;">
                                        Total Scraped: {{ stats.total_scraped }} | Passed Filter: {{ stats.passed_count }}
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>
                    
                    <!-- Content Body -->
                    <tr>
                        <td style="padding: 30px 40px;">
                            {% if jobs %}
                                <p style="margin: 0 0 20px 0; font-size: 16px; line-height: 1.5; color: #586069;">
                                    We analyzed the latest listings and found <strong>{{ jobs|length }}</strong> matching role(s) that fit your profile. Here is your ranked digest:
                                </p>
                                
                                <!-- Loop over jobs -->
                                {% for job in jobs %}
                                    <table border="0" cellpadding="0" cellspacing="0" width="100%" style="border: 1px solid #e1e4e8; border-radius: 6px; margin-bottom: 20px; background-color: #ffffff;">
                                        <tr>
                                            <td style="padding: 20px;">
                                                <table border="0" cellpadding="0" cellspacing="0" width="100%">
                                                    <!-- Title & Score -->
                                                    <tr>
                                                        <td style="vertical-align: top;">
                                                            <h2 style="margin: 0; font-size: 18px; font-weight: 700; line-height: 1.3;">
                                                                <a href="{{ job.job_url }}" target="_blank" style="color: #0366d6; text-decoration: none;">{{ job.title }}</a>
                                                            </h2>
                                                            <p style="margin: 4px 0 0 0; font-size: 14px; font-weight: 600; color: #24292e;">
                                                                {{ job.company }}
                                                            </p>
                                                        </td>
                                                        <td align="right" style="vertical-align: top; padding-left: 10px;">
                                                            <span style="display: inline-block; padding: 4px 10px; font-size: 13px; font-weight: 700; border-radius: 20px; color: #ffffff; background-color: {% if job.match_score >= 8 %}#2c974b{% elif job.match_score >= 6 %}#dbab09{% else %}#0366d6{% endif %};">
                                                                Score: {{ job.match_score }}/10
                                                            </span>
                                                        </td>
                                                    </tr>
                                                    
                                                    <!-- Location & Domain Badge -->
                                                    <tr>
                                                        <td colspan="2" style="padding-top: 8px; font-size: 13px; color: #586069;">
                                                            <strong>Location:</strong> {{ job.location }} | 
                                                            <strong>Domain:</strong> <span style="background-color: #f1f8ff; color: #0366d6; padding: 2px 6px; border-radius: 3px; font-size: 12px; font-weight: 600;">{{ job.domain }}</span>
                                                        </td>
                                                    </tr>
                                                    
                                                    <!-- Resume Highlights / Matches -->
                                                    {% if job.resume_highlights %}
                                                        <tr>
                                                            <td colspan="2" style="padding-top: 15px; border-top: 1px solid #eaecef; margin-top: 15px;">
                                                                <h4 style="margin: 0 0 8px 0; font-size: 13px; font-weight: 700; color: #24292e;">Core Match Highlights:</h4>
                                                                <ul style="margin: 0; padding-left: 20px; font-size: 13px; line-height: 1.5; color: #444d56;">
                                                                    {% for highlight in job.resume_highlights %}
                                                                        <li style="margin-bottom: 4px;">{{ highlight }}</li>
                                                                    {% endfor %}
                                                                </ul>
                                                            </td>
                                                        </tr>
                                                    {% endif %}
                                                    
                                                    <!-- Apply Button -->
                                                    <tr>
                                                        <td colspan="2" style="padding-top: 15px; text-align: right;">
                                                            <a href="{{ job.job_url }}" target="_blank" style="display: inline-block; padding: 8px 16px; font-size: 13px; font-weight: 600; color: #ffffff; background-color: #0366d6; text-decoration: none; border-radius: 6px;">
                                                                Apply Now &rarr;
                                                            </a>
                                                        </td>
                                                    </tr>
                                                </table>
                                            </td>
                                        </tr>
                                    </table>
                                {% endfor %}
                                
                            {% else %}
                                <!-- No Jobs Case -->
                                <div style="text-align: center; padding: 30px 0;">
                                    <p style="font-size: 18px; font-weight: 600; color: #586069; margin: 0 0 10px 0;">No new matching jobs found today.</p>
                                    <p style="font-size: 14px; color: #6a737d; margin: 0;">
                                        All scraped listings were either duplicates of previously evaluated roles, did not meet location requirements, demanded 3+ years of experience, or fell below the filtering score criteria.
                                    </p>
                                </div>
                            {% endif %}
                        </td>
                    </tr>
                    
                    <!-- Footer -->
                    <tr>
                        <td style="background-color: #fafbfc; border-top: 1px solid #e1e4e8; padding: 20px 40px; text-align: center; font-size: 12px; color: #6a737d;">
                            <p style="margin: 0 0 5px 0;">This email was automatically generated by JobHunter AI Agent v2.0.</p>
                            <p style="margin: 0;">Running on cron schedule via GitHub Actions.</p>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>
"""

def send_digest_email(passing_jobs: List[Dict[str, Any]], stats: Dict[str, int]) -> bool:
    """
    Sends the compiled daily HTML digest of matching jobs via Gmail SMTP.
    If the jobs list is empty, a status update is sent instead of a blank email.
    """
    sender_email = os.getenv("SENDER_EMAIL")
    sender_password = os.getenv("SENDER_PASSWORD")
    receiver_email = os.getenv("RECEIVER_EMAIL")
    
    if not (sender_email and sender_password and receiver_email):
        print("Error: Missing email configuration environment variables.")
        print(f"SENDER_EMAIL is {'set' if sender_email else 'missing'}")
        print(f"SENDER_PASSWORD (App Password) is {'set' if sender_password else 'missing'}")
        print(f"RECEIVER_EMAIL is {'set' if receiver_email else 'missing'}")
        return False
        
    sender_password = sender_password.strip()

    run_date_str = datetime.now().strftime("%B %d, %Y")
    
    # Normalize job objects so both 'url' and 'job_url' work
    normalized_jobs = []
    for j in passing_jobs:
        job_copy = dict(j)
        job_copy["job_url"] = job_copy.get("job_url") or job_copy.get("url", "")
        job_copy["match_score"] = job_copy.get("match_score", 9)
        job_copy["domain"] = job_copy.get("domain", "AI / Data Science")
        if not job_copy.get("resume_highlights"):
            highlights = [
                f"Target role match: {job_copy.get('title')}",
                f"Verified location: {job_copy.get('location')}"
            ]
            job_copy["resume_highlights"] = highlights
        normalized_jobs.append(job_copy)

    # Sort passing jobs by match score descending
    sorted_jobs = sorted(normalized_jobs, key=lambda x: x.get("match_score", 0), reverse=True)
    
    # Setup Jinja2 Template and render HTML
    try:
        template = Template(EMAIL_TEMPLATE)
        html_content = template.render(
            jobs=sorted_jobs,
            stats=stats,
            run_date=run_date_str
        )
    except Exception as e:
        print(f"Failed to render HTML email template: {e}")
        return False
        
    # Build MIME message
    msg = MIMEMultipart("alternative")
    
    subject_prefix = f"[{run_date_str}]"
    if sorted_jobs:
        msg["Subject"] = f"{subject_prefix} JobHunter Alert: {len(sorted_jobs)} New Entry-Level Matches Found!"
    else:
        msg["Subject"] = f"{subject_prefix} JobHunter: Daily Status Update (No Matches)"
        
    msg["From"] = sender_email
    msg["To"] = receiver_email
    
    # Text fallback
    text_content = f"JobHunter Daily Digest - {run_date_str}\n\n"
    if sorted_jobs:
        text_content += f"Found {len(sorted_jobs)} matching roles.\n\n"
        for job in sorted_jobs:
            text_content += f"- {job.get('title')} at {job.get('company')} ({job.get('location')})\n"
            text_content += f"  Score: {job.get('match_score')}/10\n"
            text_content += f"  Link: {job.get('job_url')}\n\n"
    else:
        text_content += "No new matching jobs were found today."
        
    msg.attach(MIMEText(text_content, "plain"))
    msg.attach(MIMEText(html_content, "html"))
    
    # Connect and send via Gmail SMTP
    smtp_server = "smtp.gmail.com"
    smtp_port = 587
    
    try:
        print(f"Connecting to Gmail SMTP server {smtp_server}:{smtp_port}...")
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.ehlo()
        server.starttls()  # Upgrade to secure encrypted connection
        server.ehlo()
        
        print("Logging in to SMTP server...")
        server.login(sender_email, sender_password)
        
        print(f"Sending email to {receiver_email}...")
        server.sendmail(sender_email, receiver_email, msg.as_string())
        
        print("Email sent successfully!")
        server.quit()
        return True
    except Exception as e:
        print(f"Error occurred while sending email: {e}")
        return False
