import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from logger import logger
import fitz
import json
import os
from pathlib import Path
from pydantic import BaseModel
from typing import List, Optional
from langchain_openai import ChatOpenAI

class StructuredResume(BaseModel):
    name: str
    email: Optional[str]
    phone: Optional[str]
    summary: str
    skills: List[str]
    experience: List[str]
    projects: List[str]
    certifications: List[str]

def get_resume_path() -> Optional[Path]:
    """Dynamically finds the first PDF in the assets/resume directory."""
    resume_dir = Path("assets/resume")
    if not resume_dir.exists():
        return None
    pdfs = list(resume_dir.glob("*.pdf"))
    if not pdfs:
        return None
    return pdfs[0]

def load_master_resume(force_reprocess: bool = False) -> StructuredResume:
    """Loads, extracts, and structures text from the master resume PDF."""
    resume_path = get_resume_path()
    structured_path = Path("assets/resume/structured_resume.json")
    
    if not resume_path or not resume_path.exists():
        raise FileNotFoundError("No PDF resume found in assets/resume/ directory. Please place your resume there.")
        
    # Reuse cached structured resume if available
    if structured_path.exists() and not force_reprocess:
        with open(structured_path, "r", encoding="utf-8") as f:
            return StructuredResume(**json.load(f))
            
    # Read PDF text
    doc = fitz.open(str(resume_path))
    text_content = []
    for page in doc:
        text_content.append(page.get_text())
    full_text = "\n".join(text_content).strip()
    
    # Structure using LLM
    llm = ChatOpenAI(
        model=os.getenv("OPENROUTER_MODEL", "meta-llama/llama-3.1-8b-instruct"),
        api_key=os.getenv("OPENROUTER_API_KEY"),
        base_url="https://openrouter.ai/api/v1",
        model_kwargs={"response_format": {"type": "json_object"}}
    )
    
    structured_llm = llm.with_structured_output(StructuredResume)
    
    prompt = f"""
    You are an expert resume parser. Extract the structured information from the following raw resume text.
    Do not invent or hallucinate any information. If a section is missing, leave the list empty or the field null.
    
    --- RESUME TEXT ---
    {full_text}
    """
    
    structured_resume = structured_llm.invoke(prompt)
    
    # Cache the result
    with open(structured_path, "w", encoding="utf-8") as f:
        json.dump(structured_resume.model_dump(), f, indent=2, ensure_ascii=False)
        
    return structured_resume

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    
    logger.info("Parsing master resume...")
    profile = load_master_resume(force_reprocess=True)
    logger.info("--- Structured Resume Profile ---")
    logger.info(json.dumps(profile.model_dump(), indent=2))
