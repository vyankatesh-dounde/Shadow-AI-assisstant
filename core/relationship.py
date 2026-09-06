import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
REL_FILE = BASE_DIR / "memory" / "relationship.json"


def load_relationship():
    if REL_FILE.exists():
        try:
            return json.loads(REL_FILE.read_text())
        except:
            pass

    return {
        "level": 1,          # 1 → stranger, 5 → trusted
        "points": 0,
        "last_interaction": None
    }


def save_relationship(data):
    REL_FILE.write_text(json.dumps(data, indent=2))


def update_relationship(text):
    data = load_relationship()

    score = 0
    text = text.lower()

    # Positive signals
    if "thank" in text:
        score += 2
    if "good job" in text or "nice" in text:
        score += 2
    if "i like you" in text:
        score += 4

    # Emotional sharing = strong bond
    if "i am sad" in text or "i'm sad" in text:
        score += 3
    if "i am stressed" in text:
        score += 3

    # Increase points
    data["points"] += score

    # Level up logic
    if data["points"] > 20:
        data["level"] = 2
    if data["points"] > 50:
        data["level"] = 3
    if data["points"] > 100:
        data["level"] = 4
    if data["points"] > 200:
        data["level"] = 5

    save_relationship(data)
    return data
