import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from logger import logger
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
    body: str = Field(description="The polished, visually appealing HTML body of the email.")

def generate_email_draft(company: str, designation: str, recruiter: str, candidate_name: str, candidate_email: str, candidate_phone: str, job_match: JobMatch, cover_letter: str) -> EmailDraft:
    """Generates a concise email subject and body."""
    llm = ChatOpenAI(
        model=os.getenv("OPENROUTER_MODEL", "meta-llama/llama-3.1-8b-instruct"),
        api_key=os.getenv("OPENROUTER_API_KEY"),
        base_url="https://openrouter.ai/api/v1",
        max_tokens=800,
        temperature=0
    )
    
    # We use base llm without structured output to prevent LLaMA JSON hallucination loops with HTML
    
    recruiter_greeting = f"Hi {recruiter}," if recruiter and recruiter.lower() not in ["unknown", "none"] else "Hi,"
    
    prompt = f"""
    You are writing a highly professional, visually appealing email to apply for a job. 
    
    JOB DETAILS:
    - Company: {company}
    - Designation: {designation}
    
    GREETING:
    {recruiter_greeting}
    
    CONTEXT:
    Here is the full cover letter that was generated (do not copy it, just use it as context for the candidate's skills):
    {cover_letter}
    
    INSTRUCTIONS:
    1. Write an EXCELLENT, polished email body in beautifully formatted HTML. 
    2. Ensure the HTML is wrapped in a container with: font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; color: #333333; line-height: 1.6; max-width: 600px;
    3. Structure the content well: an engaging opening paragraph, a concise bulleted list of 2-3 key value propositions derived from the context, and a polite call to action.
    4. Use subtle visual elements (e.g., a light gray background with padding for the bulleted list, or a left border accent) to make it look premium.
    5. Mention that your resume is attached.
    6. Include a professional HTML signature block at the end with:
       <br><br>Best regards,<br>
       <span style="font-size: 16px; font-weight: bold; color: #1a1a1a;">{candidate_name}</span><br>
       <a href="mailto:{candidate_email}" style="color: #0077b5; text-decoration: none;">{candidate_email}</a><br>
       <span style="color: #666666;">{candidate_phone}</span>
       
    CRITICAL OUTPUT RULES:
    1. You MUST output ONLY the raw HTML code. Do NOT output a subject line.
    2. Do NOT include markdown blocks (like ```html).
    3. ABSOLUTELY NO AI CHATTER. Do NOT include any conversational text, explanations, or meta-commentary (e.g., "Here is the email", "Note: I've used a light gray background", etc.) either inside or outside the HTML. The email must look 100% human-written.
    """
    
    logger.info(f"Drafting email for {designation} at {company}...")
    response = llm.invoke([HumanMessage(content=prompt)])
    content = response.content.strip()
    
    subject = f"Application for {designation} - {candidate_name}"
    
    # Strip markdown if hallucinated
    if content.startswith("```html"):
        content = content[7:]
    elif content.startswith("```"):
        content = content[3:]
    if content.endswith("```"):
        content = content[:-3]
        
    # Strictly extract only the HTML part to avoid any conversational text LLaMA might inject
    body = content.strip()
    first_tag = body.find("<")
    last_tag = body.rfind(">")
    
    if first_tag != -1 and last_tag != -1 and last_tag > first_tag:
        body = body[first_tag:last_tag+1]
        
    return EmailDraft(subject=subject, body=body.strip())

def send_email(to_email: str, draft: EmailDraft, resume_path: str = None) -> bool:
    """Sends the email via SMTP."""
    # If multiple emails are provided, take the first one
    if "," in to_email:
        to_email = to_email.split(",")[0].strip()
        
    if resume_path is None:
        from outreach.resume_parser import get_resume_path
        found_path = get_resume_path()
        resume_path = str(found_path) if found_path else None
        
    smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER")
    smtp_password = os.getenv("SMTP_PASSWORD")
    
    if not smtp_user or not smtp_password:
        logger.info("⚠️ SMTP credentials missing. Email sending skipped.")
        return False
        
    msg = EmailMessage()
    msg["Subject"] = draft.subject
    msg["From"] = smtp_user
    msg["To"] = to_email
    msg.set_content("Please enable HTML to view this email.")
    msg.add_alternative(draft.body, subtype='html')
    
    resume_file = Path(resume_path)
    if resume_file.exists():
        with open(resume_file, "rb") as f:
            pdf_data = f.read()
        msg.add_attachment(pdf_data, maintype="application", subtype="pdf", filename=resume_file.name)
    else:
        logger.info(f"⚠️ Resume not found at {resume_path}. Attachment skipped.")
        
    try:
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_password)
            server.send_message(msg)
        logger.info(f"✅ Email successfully sent to {to_email}")
        return True
    except Exception as e:
        logger.info(f"❌ Failed to send email: {e}")
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
    logger.info("--- DRAFT SUBJECT ---")
    logger.info(draft.subject)
    logger.info("--- DRAFT BODY ---")
    logger.info(draft.body)
