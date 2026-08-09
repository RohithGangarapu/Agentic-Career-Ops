import os
import time
import urllib.parse
import subprocess
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage
from outreach.matching import JobMatch

class WhatsAppDraft(BaseModel):
    message: str = Field(description="The short, conversational WhatsApp outreach message.")

def generate_whatsapp_draft(company: str, designation: str, recruiter: str, candidate_name: str, job_match: JobMatch) -> WhatsAppDraft:
    """Generates a highly conversational, short WhatsApp outreach message."""
    llm = ChatOpenAI(
        model=os.getenv("OPENROUTER_MODEL", "meta-llama/llama-3.1-8b-instruct"),
        api_key=os.getenv("OPENROUTER_API_KEY"),
        base_url="https://openrouter.ai/api/v1",
        model_kwargs={"response_format": {"type": "json_object"}}
    )
    
    structured_llm = llm.with_structured_output(WhatsAppDraft)
    
    recruiter_greeting = f"Hi {recruiter}," if recruiter and recruiter.lower() not in ["unknown", "none"] else "Hi there,"
    
    prompt = f"""
    You are writing a highly engaging, friendly, and persuasive WhatsApp message to a recruiter or hiring manager.
    Your goal is to get their attention instantly in a chat environment without being overly formal or boring.
    
    JOB DETAILS:
    - Company: {company}
    - Designation: {designation}
    
    GREETING:
    {recruiter_greeting}
    
    YOUR MATCHING QUALIFICATIONS:
    - Matched Skills: {', '.join(job_match.matched_skills)}
    - Summary of fit: {job_match.relevant_resume_points}
    
    INSTRUCTIONS:
    1. Write a very brief message (2-3 short, punchy sentences MAX). It must be optimized for mobile reading.
    2. Be friendly, confident, and professional. 
    3. State the role and seamlessly weave in one core reason you're a high-impact fit based on the matched skills.
    4. Provide a gentle call-to-action (e.g., offering to share your resume if they're open to chatting).
    5. Sign off with your name: {candidate_name}.
    
    Output strictly as a structured JSON with 'message'.
    """
    
    print(f"Drafting WhatsApp message for {designation} at {company}...")
    draft = structured_llm.invoke([HumanMessage(content=prompt)])
    return draft

def send_whatsapp(phone_number: str, draft: WhatsAppDraft, resume_path: str = None) -> bool:
    """
    Automates sending the WhatsApp message using Mac native commands (no extra libraries required).
    It also attempts to attach the resume by copying it to the clipboard and pasting it.
    """
    if resume_path is None:
        from outreach.resume_parser import get_resume_path
        found_path = get_resume_path()
        resume_path = str(found_path) if found_path else None

    # If multiple phones are provided, take the first one
    if "," in phone_number:
        phone_number = phone_number.split(",")[0]
        
    # Clean phone number (keep only digits and +)
    clean_phone = "".join([c for c in phone_number if c.isdigit() or c == "+"])
    
    # Ensure it has a country code, defaulting to +91 (India) if it's 10 digits
    if len(clean_phone) == 10 and clean_phone.isdigit():
        clean_phone = "+91" + clean_phone
    elif not clean_phone.startswith("+"):
        clean_phone = "+" + clean_phone

    if len(clean_phone) < 11:
        print(f"⚠️ Invalid phone number length for {phone_number}. Skipping WhatsApp automation.")
        return False
        
    print("\n" + "="*40)
    print(f"📱 AUTOMATING WHATSAPP MESSAGE TO {clean_phone}")
    print("="*40)
    print(draft.message)
    print(f"📎 Attempting to attach resume: {resume_path}")
    print("="*40 + "\n")
    
    try:
        # 1. Copy the resume file to the Mac clipboard
        abs_resume_path = os.path.abspath(resume_path)
        if os.path.exists(abs_resume_path):
            copy_script = f'set the clipboard to POSIX file "{abs_resume_path}"'
            subprocess.run(["osascript", "-e", copy_script])
        else:
            print(f"⚠️ Resume not found at {abs_resume_path}. Proceeding without attachment.")

        # 2. Encode the message for URL
        encoded_message = urllib.parse.quote(draft.message)
        
        # 3. Open URL
        print("Opening WhatsApp... Please do not touch your keyboard or mouse...")
        whatsapp_url = f"whatsapp://send?phone={clean_phone}&text={encoded_message}"
        
        # Try to open the Desktop app first
        result = subprocess.run(["open", whatsapp_url], capture_output=True)
        
        if result.returncode != 0:
            # Fallback to web
            web_url = f"https://web.whatsapp.com/send?phone={clean_phone}&text={encoded_message}"
            subprocess.run(["open", web_url])
            # Web takes longer to load
            time.sleep(15)
        else:
            # Desktop app is faster
            time.sleep(5)
            
        # 4. Use AppleScript to press 'Enter' (Send Text)
        enter_script = 'tell application "System Events" to keystroke return'
        subprocess.run(["osascript", "-e", enter_script])
        time.sleep(1) # Wait for text to send
        
        # 5. Use AppleScript to press 'Cmd + V' (Paste Resume)
        if os.path.exists(abs_resume_path):
            paste_script = 'tell application "System Events" to keystroke "v" using command down'
            subprocess.run(["osascript", "-e", paste_script])
            time.sleep(2) # Wait for file preview to load in WhatsApp
            
            # 6. Press 'Enter' again to send the attachment
            subprocess.run(["osascript", "-e", enter_script])
        
        print("✅ WhatsApp message & resume automated successfully.")
        return True
    except Exception as e:
        print(f"❌ Failed to automate WhatsApp message: {e}")
        return False

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    
    test_match = JobMatch(
        matched_skills=["Python", "FastAPI"],
        matched_projects=[],
        matched_experience=[],
        relevant_resume_points="5 years Python, building microservices"
    )
    draft = generate_whatsapp_draft("Google", "Python Developer", "Sundar", "John Doe", test_match)
    print(draft.message)
    # send_whatsapp("+911234567890", draft)
