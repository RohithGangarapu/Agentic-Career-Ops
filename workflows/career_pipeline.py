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
    print(f"\n--- Starting Outreach Pipeline ---")
    print(f"Loading rows from {xlsx_filepath}")
    
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
            print(f"🔄 Row '{company} - {designation}' already tracked (ID: {row_id}). Skipping for now.")
            skipped_rows_count += 1
            # Here we will add logic to resume failed/pending tasks in later phases
        else:
            print(f"✨ NEW ROW: '{company} - {designation}' (ID: {row_id})")
            new_state = RowState(
                row_id=row_id,
                company=company,
                designation=designation,
                email=str(row.get("Email", "")),
                phone=str(row.get("Phone Number", ""))
            )
            
            # Phase 3: JD Matching
            try:
                from outreach.matching import match_job_to_resume
                from outreach.cover_letter import generate_cover_letter
                from outreach.resume_parser import load_master_resume
                
                # Load profile to get candidate name
                resume_profile = load_master_resume()
                candidate_name = resume_profile.name
                
                match = match_job_to_resume(designation, str(row.get("Job Description", "")), company)
                print(f"   => Matched {len(match.matched_skills)} skills and {len(match.matched_experience)} experiences.")
                
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
                print(f"   => Generated Cover Letter: {cover_letter_path}")
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
                    
                    print(f"   => Email drafted for {email_address} (Subject: {email_draft.subject})")
                    
                    # send_email is called, but will safely skip if SMTP credentials are not in .env
                    sent = send_email(to_email=email_address, draft=email_draft)
                    if sent:
                        new_state.email_status = "sent"
                    else:
                        new_state.email_status = "generated_not_sent"
                else:
                    print("   => No email address found. Skipping email generation.")
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
                    print("   => No phone number found. Skipping WhatsApp generation.")
                    new_state.whatsapp_status = "skipped"
                
            except Exception as e:
                print(f"   => ❌ Error during outreach generation: {e}")
                new_state.error = str(e)
                new_state.cover_letter_status = "failed"
                new_state.email_status = "failed"
                new_state.whatsapp_status = "failed"
            
            state_manager.upsert_row(new_state)
            new_rows_count += 1
            
    print(f"\nPipeline Finished! New rows: {new_rows_count}, Skipped: {skipped_rows_count}")
