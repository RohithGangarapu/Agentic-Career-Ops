import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from logger import logger
import openpyxl
from pathlib import Path
from state.state_manager import StateManager, RowState

def load_rows_from_xlsx(filepath: Path) -> list[dict]:
    """Reads rows from the generated XLSX file into a list of dicts."""
    wb = openpyxl.load_workbook(filepath)
    ws = wb.active
    
    headers = []
    rows = []
    
    for i, row in enumerate(ws.iter_rows(values_only=True)):
        if i == 0:
            headers = [str(cell) if cell else f"col_{j}" for j, cell in enumerate(row)]
        else:
            row_dict = {headers[j]: cell for j, cell in enumerate(row)}
            rows.append(row_dict)
            
    return rows

def run_pipeline(xlsx_filepath: Path):
    logger.info(f"\n--- Starting Outreach Pipeline ---")
    logger.info(f"Loading rows from {xlsx_filepath}")
    
    rows = load_rows_from_xlsx(xlsx_filepath)
    state_manager = StateManager()
    
    new_rows_count = 0
    skipped_rows_count = 0
    
    for row in rows:
        company = str(row.get("Company", ""))
        designation = str(row.get("Designation", ""))
        urn = str(row.get("URN", ""))
        
        row_id = StateManager.generate_row_id(urn, company, designation)
        
        existing_state = state_manager.get_row(row_id)
        
        if existing_state:
            # Check if it needs processing
            if existing_state.error or existing_state.cover_letter_status in ["failed", "pending"] or existing_state.email_status in ["failed", "pending"] or existing_state.whatsapp_status in ["failed", "pending"]:
                logger.info(f"🔄 Retrying tracked Row '{company} - {designation}' (ID: {row_id}) which previously failed or is pending.")
                new_state = existing_state
                # Clear previous error before retry
                new_state.error = None
            else:
                logger.info(f"🔄 Row '{company} - {designation}' already successfully processed or skipped (ID: {row_id}). Skipping.")
                skipped_rows_count += 1
                continue
        else:
            logger.info(f"✨ NEW ROW: '{company} - {designation}' (ID: {row_id})")
            new_state = RowState(
                row_id=row_id,
                company=company,
                designation=designation,
                email=str(row.get("Email", "")),
                phone=str(row.get("Phone Number", ""))
            )
            
        email_val = str(row.get("Emails", "")).strip()
        phone_val = str(row.get("Phones", "")).strip()
        
        has_email = email_val and email_val.lower() not in ["none", "null", ""]
        has_phone = phone_val and phone_val.lower() not in ["none", "null", ""]
        
        if not has_email and not has_phone:
            logger.info(f"   => Skipping '{company} - {designation}': No email or phone found.")
            new_state.cover_letter_status = "skipped"
            new_state.email_status = "skipped"
            new_state.whatsapp_status = "skipped"
            state_manager.upsert_row(new_state)
            skipped_rows_count += 1
            continue
                
        # Phase 3: JD Matching
        try:
            from outreach.matching import match_job_to_resume
            from outreach.cover_letter import generate_cover_letter
            from outreach.resume_parser import load_master_resume
            
            # Load profile to get candidate name
            resume_profile = load_master_resume()
            candidate_name = resume_profile.name
            
            match = match_job_to_resume(designation, str(row.get("Job Description", "")), company)
            logger.info(f"   => Matched {len(match.matched_skills)} skills and {len(match.matched_experience)} experiences.")
            
            # Phase 4: Cover Letter Generation
            cover_letter_path = generate_cover_letter(
                row_id=row_id,
                company=company,
                designation=designation,
                recruiter=str(row.get("Recruiter", "")),
                job_description=str(row.get("Job Description", "")),
                job_match=match,
                candidate_name=candidate_name
            )
            logger.info(f"   => Generated Cover Letter: {cover_letter_path}")
            new_state.cover_letter_path = cover_letter_path
            new_state.cover_letter_status = "generated"
            
            # Phase 5: Email Generation
            email_address = str(row.get("Emails", "")).strip()
            if email_address and email_address.lower() != "none":
                from outreach.email_sender import generate_email_draft, send_email
                
                with open(cover_letter_path, "r", encoding="utf-8") as f:
                    cover_letter_text = f.read()
                    
                email_draft = generate_email_draft(
                    company=company,
                    designation=designation,
                    recruiter=str(row.get("Recruiter", "")),
                    candidate_name=candidate_name,
                    candidate_email=resume_profile.email or "",
                    candidate_phone=resume_profile.phone or "",
                    job_match=match,
                    cover_letter=cover_letter_text
                )
                
                logger.info(f"   => Email drafted for {email_address} (Subject: {email_draft.subject})")
                
                # send_email is called, but will safely skip if SMTP credentials are not in .env
                sent = send_email(to_email=email_address, draft=email_draft)
                if sent:
                    new_state.email_status = "sent"
                else:
                    new_state.email_status = "generated_not_sent"
            else:
                logger.info("   => No email address found. Skipping email generation.")
                new_state.email_status = "skipped"
                
            # Phase 6: WhatsApp Generation
            phone_number = str(row.get("Phones", "")).strip()
            if phone_number and phone_number.lower() != "none":
                from outreach.whatsapp import generate_whatsapp_draft, send_whatsapp
                
                wa_draft = generate_whatsapp_draft(
                    company=company,
                    designation=designation,
                    recruiter=str(row.get("Recruiter", "")),
                    candidate_name=candidate_name,
                    job_match=match
                )
                
                sent = send_whatsapp(phone_number, wa_draft)
                if sent:
                    new_state.whatsapp_status = "prepared"
                else:
                    new_state.whatsapp_status = "failed"
            else:
                logger.info("   => No phone number found. Skipping WhatsApp generation.")
                new_state.whatsapp_status = "skipped"
            
        except Exception as e:
            logger.info(f"   => ❌ Error during outreach generation: {e}")
            new_state.error = str(e)
            new_state.cover_letter_status = "failed"
            new_state.email_status = "failed"
            new_state.whatsapp_status = "failed"
        
        state_manager.upsert_row(new_state)
        new_rows_count += 1
        
    logger.info(f"\nPipeline Finished! New rows: {new_rows_count}, Skipped: {skipped_rows_count}")
