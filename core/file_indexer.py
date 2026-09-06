import os
import json
import threading
import time
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
INDEX_FILE = BASE_DIR / "memory" / "file_index.json"

SEARCH_PATHS = [
    "C:\\Users",
    "D:\\",
    "E:\\"
]

# =========================
# 📦 BUILD INDEX
# =========================
def build_index():
    index = []

    for base in SEARCH_PATHS:
        for root, dirs, files in os.walk(base):
            try:
                for d in dirs:
                    index.append({
                        "name": d.lower(),
                        "path": os.path.join(root, d),
                        "type": "folder"
                    })

                for f in files:
                    index.append({
                        "name": f.lower(),
                        "path": os.path.join(root, f),
                        "type": "file"
                    })
            except:
                continue

    INDEX_FILE.parent.mkdir(exist_ok=True)
    INDEX_FILE.write_text(json.dumps(index, indent=2))

    return f"Indexed {len(index)} items."

# =========================
# 📦 Fast Search Function
# =========================
def search_index(query: str):
    if not INDEX_FILE.exists():
        return None

    query = query.lower()

    try:
        data = json.loads(INDEX_FILE.read_text())
    except:
        return None

    # 🔍 scoring system
    results = []

    for item in data:
        score = 0

        if query in item["name"]:
            score += 10

        # partial match boost
        for word in query.split():
            if word in item["name"]:
                score += 3

        if score > 0:
            results.append((score, item))

    # 🎯 best match
    results.sort(reverse=True, key=lambda x: x[0])

    if results:
        return results[0][1]["path"]

    return None


def open_indexed(query: str):
    path = search_index(query)

    if path:
        os.startfile(path)
        return f"Opening {query}"
    else:
        return f"I couldn't find {query}"


# =========================
# 🔁 AUTO INDEX (BACKGROUND)
# =========================
def auto_index(interval=3600):
    def run():
        while True:
            try:
                build_index()
            except Exception as e:
                print("Indexing error:", e)

            time.sleep(interval)

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
