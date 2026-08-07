import datetime

from core.math_engine import is_math_query, solve_math

# =========================
# 🧠 QUICK-ANSWER SKILL ROUTER
#
# Handles fast, deterministic replies that don't need the LLM:
# math, time, date. Desktop/app control (open/close/volume/etc.)
# lives in core/desktop_control.py and is routed directly from
# brain.py instead of being duplicated here.
# =========================


def handle_skills(text: str):
    text = text.lower()

    # 🧮 MATH
    if is_math_query(text):
        result = solve_math(text)
        if result is not None:
            return f"{result}"
        return None

    # ⏰ TIME
    if "time" in text:
        now = datetime.datetime.now().strftime("%I:%M %p")
        return f"It's {now}"

    # 📅 DATE
    if "date" in text or "what day" in text:
        today = datetime.datetime.now().strftime("%A, %d %B %Y")
        return f"Today is {today}"

    return None
