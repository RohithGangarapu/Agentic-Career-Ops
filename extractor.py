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
    """Uses LLM to extract Company, Designation, Location, and JD from raw post text."""
    llm = get_llm()
    structured_llm = llm.with_structured_output(ExtractedData)
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are an expert technical recruiter data extraction assistant. Analyze the given LinkedIn post text and extract the company name, the designation(s) they are hiring for, the location, the experience required, and the Job Description (JD). If multiple roles are mentioned, list them all. Do NOT extract the title of the author/recruiter. For experience, if it says 'Fresher', output '0', else output the years. If a piece of information is entirely missing, leave it null."),
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
            "jd": result.jd
        }
    except Exception as e:
        print(f"LLM extraction error: {e}")
        return {"company": None, "designation": None, "location": None, "experience": None, "jd": None}

def extract_contact_info(text: str) -> dict:
    """Uses regex to deterministically extract emails, phone numbers, and links."""
    email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
    # Match standard international/Indian formats, spaces, dashes
    phone_pattern = r'(?:(?:\+|00)91[\s-]?)?(?:\d{5}[\s-]?\d{5}|\d{3}[\s-]?\d{3}[\s-]?\d{4}|\d{4}[\s-]?\d{4}[\s-]?\d{2})'
    # Match standard URLs (http/https)
    link_pattern = r'https?://(?:www\.)?[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b(?:[-a-zA-Z0-9()@:%_\+.~#?&//=]*)'
    
    emails = list(set(re.findall(email_pattern, text)))
    phones = list(set(re.findall(phone_pattern, text)))
    links = list(set(re.findall(link_pattern, text)))
    
    # Simple clean up of false positive phones
    cleaned_phones = [p for p in phones if len(re.sub(r'\D', '', p)) >= 10]
    
    return {
        "emails": emails,
        "phones": cleaned_phones,
        "links": links
    }
