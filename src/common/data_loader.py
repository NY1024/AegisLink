import json
import os
from pathlib import Path

BASE_DIR = Path("/Users/elwood/Desktop/test/AegisLink")
INTERNAL_DATA_DIR = BASE_DIR / "internal_data"

def load_spreadsheet(spreadsheet_id: str):
    file_path = INTERNAL_DATA_DIR / f"spreadsheet_{spreadsheet_id}.json"
    if file_path.exists():
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    print(f"[WARN] File not found: {file_path}")
    return None

def load_contact(contact_id: str):
    file_path = INTERNAL_DATA_DIR / f"contact_{contact_id}.json"
    if file_path.exists():
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    print(f"[WARN] File not found: {file_path}")
    return None

def load_calendar(calendar_id: str):
    file_path = INTERNAL_DATA_DIR / f"calendar_{calendar_id}.json"
    if file_path.exists():
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    print(f"[WARN] File not found: {file_path}")
    return None

def list_available_data():
    data_list = []
    if INTERNAL_DATA_DIR.exists():
        for f in INTERNAL_DATA_DIR.glob("*.json"):
            data_list.append(f.name)
    return data_list
