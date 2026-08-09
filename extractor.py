import os
import re
from typing import List, Optional
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from dotenv import load_dotenv
import warnings

warnings.filterwarnings("ignore", category=UserWarning, module="pydantic")

load_dotenv()

class ExtractedData(BaseModel):
    company: Optional[str] = Field(None, description="The name of the company hiring. Extract only the company name, e.g., 'Google'. Leave null if not found.")
    designation: Optional[str] = Field(None, description="The job title(s) or designation(s) THEY ARE HIRING FOR in the post text (e.g., 'Senior Python Developer', 'QA Tester'). If they are hiring for multiple roles, list all of them separated by commas. DO NOT extract the job title of the person who posted the job.")
    location: Optional[str] = Field(None, description="The location of the job (e.g., 'Pune, Maharashtra', 'Remote', 'Jersey City, NJ'). Leave null if not found.")
    experience: Optional[str] = Field(None, description="The experience required for the job. If the post mentions 'Fresher', output '0'. Otherwise, output the number of years of experience required (e.g., '3-5', '10+'). Leave null if not found.")
    jd: Optional[str] = Field(None, description="The Job Description (JD) text including responsibilities, requirements, and tech stack. Leave null if not found.")
    emails: Optional[List[str]] = Field(default_factory=list, description="A list of email addresses explicitly mentioned in the text. De-obfuscate them if necessary (e.g., 'john at gmail dot com' -> 'john@gmail.com'). Do NOT hallucinate emails.")
    phones: Optional[List[str]] = Field(default_factory=list, description="A list of phone numbers explicitly mentioned in the text. Strip out formatting characters like spaces or dashes, keeping only digits and the '+' sign.")
    links: Optional[List[str]] = Field(default_factory=list, description="A list of URLs or application links explicitly mentioned in the text.")

def get_llm():
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise ValueError("OPENROUTER_API_KEY environment variable is not set. Please add it to your .env file.")
        
    model = os.getenv("OPENROUTER_MODEL", "meta-llama/llama-3.1-8b-instruct")
    
    return ChatOpenAI(
        model=model,
        api_key=api_key,
        base_url="https://openrouter.ai/api/v1",
        temperature=0
    )

def extract_structured_data(text: str) -> dict:
    """Uses LLM to extract Company, Designation, Location, JD, Emails, Phones, and Links from raw post text."""
    llm = get_llm()
    structured_llm = llm.with_structured_output(ExtractedData)
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are an expert technical recruiter data extraction assistant. Analyze the given LinkedIn post text and extract the company name, the designation(s) they are hiring for, the location, the experience required, and the Job Description (JD).\n\nCRITICAL CONTACT INFO RULES:\n1. Extract ANY emails mentioned. You MUST intelligently de-obfuscate them (e.g., 'hr [at] company [dot] com' becomes 'hr@company.com'). NEVER guess or hallucinate an email if it is not in the text.\n2. Extract ANY phone numbers mentioned. Clean them to standard formats (e.g., '+919876543210').\n3. Extract application URLs.\n\nFor experience, if it says 'Fresher', output '0', else output the years. If a piece of information is entirely missing, leave it null or an empty list. NEVER invent data."),
        ("user", "{text}")
    ])
    
    chain = prompt | structured_llm
    
    try:
        result = chain.invoke({"text": text})
        return {
            "company": result.company,
            "designation": result.designation,
            "location": result.location,
            "experience": result.experience,
            "jd": result.jd,
            "emails": result.emails if result.emails else [],
            "phones": result.phones if result.phones else [],
            "links": result.links if result.links else []
        }
    except Exception as e:
        print(f"LLM extraction error: {e}")
        return {"company": None, "designation": None, "location": None, "experience": None, "jd": None, "emails": [], "phones": [], "links": []}

def extract_contact_info(text: str) -> dict:
    """Deprecated: Replaced by extract_structured_data."""
    return {
        "emails": [],
        "phones": [],
        "links": []
    }
