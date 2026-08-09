import os
import json
from typing import List
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from outreach.resume_parser import load_master_resume, StructuredResume

class JobMatch(BaseModel):
    matched_skills: List[str] = Field(description="Skills required by the JD that are genuinely present in the resume.")
    matched_projects: List[str] = Field(description="Projects from the resume that demonstrate required skills.")
    matched_experience: List[str] = Field(description="Experience bullets from the resume that align with the role.")
    relevant_resume_points: str = Field(description="A short summary of why the candidate is a good fit, using ONLY facts from the resume.")

def match_job_to_resume(job_designation: str, job_description: str, company: str) -> JobMatch:
    """Matches a job description strictly against the master resume."""
    
    # Load the cached structured resume
    resume: StructuredResume = load_master_resume(force_reprocess=False)
    resume_json = json.dumps(resume.model_dump(), indent=2)
    
    llm = ChatOpenAI(
        model=os.getenv("OPENROUTER_MODEL", "meta-llama/llama-3.1-8b-instruct"),
        api_key=os.getenv("OPENROUTER_API_KEY"),
        base_url="https://openrouter.ai/api/v1",
        model_kwargs={"response_format": {"type": "json_object"}}
    )
    
    structured_llm = llm.with_structured_output(JobMatch)
    
    prompt = f"""
    You are an expert technical recruiter analyzing a candidate's fit for a role.
    
    CRITICAL BUSINESS RULES:
    1. You MUST match the Job Description (JD) ONLY against information genuinely present in the candidate's resume.
    2. NEVER invent, fabricate, or hallucinate skills, technologies, experience, projects, or metrics.
    3. If the candidate does not have a required skill mentioned in the JD, simply omit it. Do not lie.
    
    --- CANDIDATE RESUME ---
    {resume_json}
    
    --- TARGET JOB ---
    Company: {company}
    Designation: {job_designation}
    Job Description:
    {job_description}
    
    Analyze the fit and extract strictly genuine matching elements into a structured JSON response.
    """
    
    print(f"Analyzing JD fit for {job_designation} at {company}...")
    match_result = structured_llm.invoke(prompt)
    return match_result

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    
    # Sample Test
    test_company = "Google"
    test_designation = "Senior Python Backend Engineer"
    test_jd = "Looking for a backend engineer with 5+ years of Python experience. Must have experience with FastAPI, Docker, and Kubernetes. AWS certification is a huge plus. Will lead a team of 3 engineers."
    
    print(f"Testing match for {test_designation} at {test_company}")
    match = match_job_to_resume(test_designation, test_jd, test_company)
    print("\n--- Match Results ---")
    print(json.dumps(match.model_dump(), indent=2))
