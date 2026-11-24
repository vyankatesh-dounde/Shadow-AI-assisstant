"""Manual contact directory and confirmation-gated phone launching."""

import json
import re
import webbrowser
from pathlib import Path
from typing import Any
from memory.storage import get_kv

CALL_BOOK_FILE = Path(__file__).resolve().parent.parent / "memory" / "call_book.json"
CATEGORIES = ("family", "hotels", "box_office")
PHONE_RE = re.compile(r"^[+0-9().\-\s]{3,32}$")


def load_call_book() -> dict[str, dict[str, Any]]:
    if CALL_BOOK_FILE.exists():
        try:
            value = json.loads(CALL_BOOK_FILE.read_text(encoding="utf-8"))
            if isinstance(value, dict):
                return {
                    category: value.get(category, {})
                    if isinstance(value.get(category, {}), dict) else {}
                    for category in CATEGORIES
                }
        except (OSError, json.JSONDecodeError):
            pass
    value = get_kv("call_book", {})
    if not isinstance(value, dict):
        return {category: {} for category in CATEGORIES}
    if not isinstance(value, dict):
        return {category: {} for category in CATEGORIES}
    return {
        category: value.get(category, {})
        if isinstance(value.get(category, {}), dict) else {}
        for category in CATEGORIES
    }


def _phone_from_entry(entry: Any) -> str | None:
    if isinstance(entry, str):
        return entry.strip()
    if isinstance(entry, dict) and isinstance(entry.get("phone"), str):
        return entry["phone"].strip()
    return None


def find_contact(name: str, category: str = "") -> dict[str, str] | None:
    wanted = (name or "").strip().casefold()
    if not wanted:
        return None
    categories = [category] if category in CATEGORIES else CATEGORIES
    book = load_call_book()
    for current_category in categories:
        for saved_name, entry in book[current_category].items():
            if saved_name.casefold() != wanted:
                continue
            phone = _phone_from_entry(entry)
            if phone and PHONE_RE.fullmatch(phone):
                return {"name": saved_name, "phone": phone, "category": current_category}
    return None


def call_contact(name: str, phone: str) -> str:
    if not PHONE_RE.fullmatch((phone or "").strip()):
        return "That contact has an invalid phone number."
    webbrowser.open(f"tel:{phone.strip()}")
    return f"Opening a call to {name}."
