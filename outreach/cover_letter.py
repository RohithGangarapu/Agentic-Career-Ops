import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from logger import logger
import os
from pathlib import Path
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage
from outreach.matching import JobMatch

COVER_LETTERS_DIR = Path(".career_ops/cover_letters")

def generate_cover_letter(row_id: str, company: str, designation: str, recruiter: str, job_description: str, job_match: JobMatch, candidate_name: str) -> str:
    """Generates a highly personalized, creative, and robust cover letter using matched skills."""
    COVER_LETTERS_DIR.mkdir(parents=True, exist_ok=True)
    
    file_path = COVER_LETTERS_DIR / f"{row_id}.txt"
    
    llm = ChatOpenAI(
        model=os.getenv("OPENROUTER_MODEL", "meta-llama/llama-3.1-8b-instruct"),
        api_key=os.getenv("OPENROUTER_API_KEY"),
        base_url="https://openrouter.ai/api/v1",
        max_tokens=1500,
        temperature=0.7
    )
    
    recruiter_greeting = f"Dear {recruiter}," if recruiter and recruiter.lower() not in ["unknown", "none"] else "Dear Hiring Team,"
    
    prompt = f"""
    You are an elite career strategist and expert copywriter. Your task is to write a highly creative, persuasive, and standout cover letter for a top-tier candidate.
    
    TARGET JOB:
    - Company: {company}
    - Designation: {designation}
    
    GREETING TO USE:
    {recruiter_greeting}
    
    GENUINE MATCHING QUALIFICATIONS (DO NOT INVENT ANYTHING ELSE):
    - Matched Skills: {', '.join(job_match.matched_skills)}
    - Relevant Experience:
      {chr(10).join(job_match.matched_experience)}
      
    - Summary of fit: {job_match.relevant_resume_points}
    
    ADVANCED COPYWRITING INSTRUCTIONS (AIDA FRAMEWORK):
    1. ATTENTION (Opening): Start with a powerful, confident hook. Do NOT use boring openers like "I am writing to apply for...". Instead, state immediately why the candidate's specific background makes them a force multiplier for {company}.
    2. INTEREST & DESIRE (Body): Weave the genuine matched skills and experience into a compelling narrative. Show, don't just tell. Focus on IMPACT and RESULTS rather than just listing responsibilities. 
    3. ACTION (Closing): Conclude with a strong, confident call to action. State that the resume is attached and express eagerness to discuss how the candidate can deliver immediate value to the team.
    
    CRITICAL RULES:
    - Write exactly 3-4 concise paragraphs.
    - Be highly professional, yet engaging and human. Let the candidate's expertise shine through confident tone.
    - Highlight ONLY the genuine matching qualifications provided above. STRICTLY NO HALLUCINATIONS of skills or metrics not provided.
    - Output strictly the final text of the cover letter. No markdown wrappers or preamble.
    - End the letter exactly with:
    
    Sincerely,
    {candidate_name}
    """
    
    logger.info(f"Generating advanced cover letter for {designation} at {company}...")
    response = llm.invoke([HumanMessage(content=prompt)])
    cover_letter_text = response.content.strip()
    
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(cover_letter_text)
        
    return str(file_path)

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    
    test_match = JobMatch(
        matched_skills=["Python", "FastAPI", "Docker", "Kubernetes"],
        matched_projects=[],
        matched_experience=[
            "Senior Python Developer | TechCorp | 2020 - Present",
            "- Led a team of 5 engineers to build a microservices architecture using FastAPI and Docker."
        ],
        relevant_resume_points="5+ years of Python experience, experience leading a team of 5 engineers"
    )
    
    path = generate_cover_letter(
        row_id="test_row_123",
        company="Google",
        designation="Senior Python Backend Engineer",
        recruiter="Sundar Pichai",
        job_description="...",
        job_match=test_match,
        candidate_name="John Doe"
    )
    logger.info(f"\n--- Advanced Cover Letter Saved to {path} ---")
    with open(path, "r") as f:
        logger.info(f.read())
