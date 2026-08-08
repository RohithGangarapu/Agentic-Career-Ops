from typing import TypedDict, List, Optional
from langgraph.graph import StateGraph, START, END
from extractor import extract_contact_info, extract_structured_data

class ExtractionState(TypedDict):
    raw_text: str
    emails: List[str]
    phones: List[str]
    links: List[str]
    company: Optional[str]
    designation: Optional[str]
    location: Optional[str]
    experience: Optional[str]
    jd: Optional[str]

def extract_contacts_node(state: ExtractionState):
    contacts = extract_contact_info(state["raw_text"])
    return {"emails": contacts["emails"], "phones": contacts["phones"], "links": contacts["links"]}

def extract_structured_node(state: ExtractionState):
    structured = extract_structured_data(state["raw_text"])
    return {
        "company": structured.get("company"),
        "designation": structured.get("designation"),
        "location": structured.get("location"),
        "experience": structured.get("experience"),
        "jd": structured.get("jd")
    }

# Build LangGraph
workflow = StateGraph(ExtractionState)
workflow.add_node("extract_contacts", extract_contacts_node)
workflow.add_node("extract_structured", extract_structured_node)

workflow.add_edge(START, "extract_contacts")
workflow.add_edge("extract_contacts", "extract_structured")
workflow.add_edge("extract_structured", END)

app = workflow.compile()

def process_post(text: str) -> dict:
    """Executes the LangGraph extraction workflow on a single post text."""
    initial_state = {
        "raw_text": text,
        "emails": [],
        "phones": [],
        "links": [],
        "company": None,
        "designation": None,
        "location": None,
        "experience": None,
        "jd": None
    }
    
    result = app.invoke(initial_state)
    
    # Return everything except the raw_text to keep output clean
    return {
        "emails": result["emails"],
        "phones": result["phones"],
        "links": result["links"],
        "company": result["company"],
        "designation": result["designation"],
        "location": result["location"],
        "experience": result["experience"],
        "jd": result["jd"]
    }
