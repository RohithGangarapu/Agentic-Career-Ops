from openpyxl import Workbook
from pathlib import Path
from typing import List

def export_to_xlsx(normalized_posts: List[dict], output_filepath: Path):
    """
    Exports normalized LinkedIn posts to an Excel (.xlsx) file using openpyxl.
    """
    wb = Workbook()
    ws = wb.active
    ws.title = "LinkedIn Jobs"
    
    # Define headers prioritizing the most important information
    headers = [
        "Company", 
        "Designation",
        "Location",
        "Experience",
        "Emails", 
        "Phones", 
        "Links",
        "Job Description", 
        "Post URL", 
        "Scraped At",
        "URN",
        "Raw Text"
    ]
    ws.append(headers)
    
    # Append rows
    for post in normalized_posts:
        row = [
            post.get("company", ""),
            post.get("designation", ""),
            post.get("location", ""),
            post.get("experience", ""),
            post.get("emails", ""),
            post.get("phones", ""),
            post.get("links", ""),
            post.get("jd", ""),
            post.get("url", ""),
            post.get("scraped_at", ""),
            post.get("urn", ""),
            post.get("raw_text", "")
        ]
        # Openpyxl doesn't support writing None or certain illegal characters, 
        # but our normalizer already converted everything to clean strings!
        ws.append(row)
        
    # Auto-adjust column widths for better readability
    for col in ws.columns:
        max_length = 0
        column = col[0].column_letter
        for cell in col:
            try:
                if len(str(cell.value)) > max_length:
                    max_length = len(str(cell.value))
            except:
                pass
        
        # Cap max length so massive JD columns don't break the layout
        adjusted_width = min(max_length + 2, 50) 
        ws.column_dimensions[column].width = adjusted_width

    wb.save(output_filepath)
