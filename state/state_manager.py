import json
import hashlib
from pathlib import Path
from pydantic import BaseModel, Field
from typing import Optional, Dict
import datetime

STATE_DIR = Path(".career_ops/state")
STATE_FILE = STATE_DIR / "state.json"

class RowState(BaseModel):
    row_id: str
    company: str
    designation: str
    email: str = ""
    phone: str = ""
    
    # Statuses: pending, processing, generated, sent, skipped, failed
    cover_letter_status: str = "pending"
    email_status: str = "pending"
    whatsapp_status: str = "pending"
    
    cover_letter_path: Optional[str] = None
    email_sent_at: Optional[str] = None
    whatsapp_sent_at: Optional[str] = None
    
    error: Optional[str] = None
    last_updated: str = Field(default_factory=lambda: datetime.datetime.now().isoformat())

class StateManager:
    def __init__(self):
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        self.state_file = STATE_FILE
        self.state: Dict[str, dict] = self._load_state()

    def _load_state(self) -> Dict[str, dict]:
        if self.state_file.exists():
            try:
                with open(self.state_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except json.JSONDecodeError:
                pass
        return {}

    def _save_state(self):
        with open(self.state_file, "w", encoding="utf-8") as f:
            json.dump(self.state, f, indent=2, ensure_ascii=False)

    @staticmethod
    def generate_row_id(urn: str, company: str, designation: str) -> str:
        """Deterministic row_id based on URN or Company+Designation hash"""
        if urn:
            return urn
        raw = f"{company}_{designation}".lower().strip()
        return hashlib.md5(raw.encode("utf-8")).hexdigest()

    def get_row(self, row_id: str) -> Optional[RowState]:
        if row_id in self.state:
            return RowState(**self.state[row_id])
        return None

    def upsert_row(self, row_state: RowState):
        row_state.last_updated = datetime.datetime.now().isoformat()
        self.state[row_state.row_id] = row_state.model_dump()
        self._save_state()
