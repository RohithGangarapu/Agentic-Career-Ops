import os
import smtplib
from pathlib import Path
from email.message import EmailMessage
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage
from outreach.matching import JobMatch

class EmailDraft(BaseModel):
    subject: str = Field(description="The professional subject line for the email.")
    body: str = Field(description="The concise, personalized body of the email.")

def generate_email_draft(company: str, designation: str, recruiter: str, candidate_name: str, candidate_email: str, candidate_phone: str, job_match: JobMatch, cover_letter: str) -> EmailDraft:
    """Generates a concise email subject and body."""
    llm = ChatOpenAI(
        model=os.getenv("OPENROUTER_MODEL", "meta-llama/llama-3.1-8b-instruct"),
        api_key=os.getenv("OPENROUTER_API_KEY"),
        base_url="https://openrouter.ai/api/v1",
        model_kwargs={"response_format": {"type": "json_object"}}
    )
    
    structured_llm = llm.with_structured_output(EmailDraft)
    
    recruiter_greeting = f"Hi {recruiter}," if recruiter and recruiter.lower() not in ["unknown", "none"] else "Hi,"
    
    prompt = f"""
    You are writing a short, professional email to apply for a job. 
    
    JOB DETAILS:
    - Company: {company}
    - Designation: {designation}
    
    GREETING:
    {recruiter_greeting}
    
    CONTEXT:
    Here is the full cover letter that was generated (do not copy it, just use it as context for the candidate's skills):
    {cover_letter}
    
    INSTRUCTIONS:
    1. Write an engaging subject line (e.g., "Application for [Designation] - [Candidate Name]").
    2. Write a VERY CONCISE email body (3-4 sentences max). 
    3. State the role you're applying for, a brief 1-sentence personalized hook connecting your genuine experience, and mention that your resume is attached.
    4. Sign off with:
       Best regards,
       {candidate_name}
       {candidate_email}
       {candidate_phone}
       
    Output strictly as a structured JSON with 'subject' and 'body'.
    """
    
    print(f"Drafting email for {designation} at {company}...")
    draft = structured_llm.invoke([HumanMessage(content=prompt)])
    return draft

def send_email(to_email: str, draft: EmailDraft, resume_path: str = "assets/resume/ROHITH_RESUME.pdf") -> bool:
    """Sends the email via SMTP."""
    # If multiple emails are provided, take the first one
    if "," in to_email:
        to_email = to_email.split(",")[0].strip()
        
    smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER")
    smtp_password = os.getenv("SMTP_PASSWORD")
    
    if not smtp_user or not smtp_password:
        print("⚠️ SMTP credentials missing. Email sending skipped.")
        return False
        
    msg = EmailMessage()
    msg["Subject"] = draft.subject
    msg["From"] = smtp_user
    msg["To"] = to_email
    msg.set_content(draft.body)
    
    resume_file = Path(resume_path)
    if resume_file.exists():
        with open(resume_file, "rb") as f:
            pdf_data = f.read()
        msg.add_attachment(pdf_data, maintype="application", subtype="pdf", filename=resume_file.name)
    else:
        print(f"⚠️ Resume not found at {resume_path}. Attachment skipped.")
        
    try:
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_password)
            server.send_message(msg)
        print(f"✅ Email successfully sent to {to_email}")
        return True
    except Exception as e:
        print(f"❌ Failed to send email: {e}")
        return False

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    
    test_match = JobMatch(
        matched_skills=["Python"],
        matched_projects=[],
        matched_experience=["Senior Python Developer"],
        relevant_resume_points="5 years Python"
    )
    draft = generate_email_draft("Google", "Python Developer", "Sundar", "John Doe", "john@example.com", "555", test_match, "My cover letter...")
    print("--- DRAFT SUBJECT ---")
    print(draft.subject)
    print("--- DRAFT BODY ---")
    print(draft.body)
