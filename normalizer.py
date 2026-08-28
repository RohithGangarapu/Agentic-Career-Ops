from logger import logger
from typing import List, Optional, Any
from pydantic import BaseModel, Field, field_validator

class NormalizedPost(BaseModel):
    urn: str
    url: str
    company: str
    designation: str
    location: str
    experience: str
    jd: str
    emails: str
    phones: str
    links: str
    scraped_at: str
    raw_text: str
    
    @field_validator('company', 'designation', 'location', 'experience', 'jd', mode='before')
    def null_to_empty(cls, v: Any) -> str:
        if v is None:
            return ""
        return str(v).strip()
    
    @field_validator('emails', 'phones', 'links', mode='before')
    def list_to_string(cls, v: Any) -> str:
        if v is None:
            return ""
        if isinstance(v, list):
            return ", ".join(v)
        return str(v).strip()
    
    @field_validator('company', 'designation', 'location')
    def title_case(cls, v: str) -> str:
        if v:
            return v.title()
        return v

def normalize_posts(structured_posts: List[dict]) -> List[dict]:
    """
    Takes the structured posts and strictly validates/normalizes them into flat dictionaries
    suitable for immediate export to a spreadsheet.
    """
    normalized_results = []
    
    for post in structured_posts:
        try:
            # Prepare data
            raw_data = {
                "urn": post.get("urn", ""),
                "url": post.get("url", ""),
                "company": post.get("company"),
                "designation": post.get("designation"),
                "location": post.get("location"),
                "experience": post.get("experience"),
                "jd": post.get("jd"),
                "emails": post.get("emails", []),
                "phones": post.get("phones", []),
                "links": post.get("links", []),
                "scraped_at": post.get("scraped_at", ""),
                "raw_text": post.get("text", "") # save the original raw text just in case
            }
            
            # Validate and Normalize using Pydantic
            normalized_model = NormalizedPost(**raw_data)
            normalized_results.append(normalized_model.model_dump())
        except Exception as e:
            logger.info(f"⚠️ Error normalizing post {post.get('urn')}: {e}")
            
    return normalized_results
