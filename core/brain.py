import re

from ai.llm import ask_ai, FALLBACK_REPLIES
from core.file_indexer import open_indexed, build_index
from core.relationship import update_relationship, load_relationship
from core.desktop_control import (
    open_app, open_smart, open_website, open_path,
    open_named_folder, open_drive,
    switch_window, switch_window_back, show_all_windows, minimize_all,
    close_window, volume_up, volume_down,
)
from core.skills import handle_skills
from core.reminder_nlp import try_create_reminder
from core.wake_word import is_wake_word, handle_wake_word
from core.memory import add_message, load_facts, load_conversation, save_fact, save_fact_list
from core.memory_extractor import ai_extract_memory
from core.web_search import search_and_format
from integrations.memory_integration import (
    learn_from_text,
    fact_ack,
    build_memory_context,
    get_daily_memory,
    remember_today,
)


# =========================================================
# ⚡ COMMAND HANDLERS
# =========================================================

def _cmd_reminder(text, lower, facts):
    return try_create_reminder(text)


def _cmd_web_search(text, lower, facts):
    """Search the web and return actual result titles/snippets/URLs.

    This is deliberately before the generic `open` handler so a request
    like "search for Python FastAPI" cannot be mistaken for an app/file
    command.
    """
    prefixes = (
        "search the web for ",
        "search web for ",
        "web search for ",
        "search google for ",
        "search google ",
        "google search for ",
        "google for ",
        "google ",
        "search for ",
        "search ",
        "look up ",
        "look online for ",
        "find online ",
    )

    query = None
    for prefix in prefixes:
        if lower.startswith(prefix):
            query = text[len(prefix):].strip()
            break

    if not query:
        return None

    # Avoid treating a very short empty-ish command as a real search.
    if not query:
        return "What should I search for?"

    return search_and_format(query)


def _cmd_drive(text, lower, facts):
    return open_drive(lower)


def _cmd_skill(text, lower, facts):
    return handle_skills(text)


def _cmd_index_files(text, lower, facts):
    if "index files" in lower or "scan files" in lower:
        return build_index()
    return None


def _cmd_open_my(text, lower, facts):
    if "open my" in lower or "find my" in lower:
        name = lower.replace("open my", "").replace("find my", "").strip()
        result = open_indexed(name)
        if "couldn't find" in result.lower():
            result = open_smart(name)
        return result
    return None


def _cmd_window(text, lower, facts):
    if "switch window" in lower or "next window" in lower:
        return switch_window()
    if "previous window" in lower:
        return switch_window_back()
    if "show all windows" in lower or "task view" in lower:
        return show_all_windows()
    if "minimize all" in lower or "show desktop" in lower:
        return minimize_all()
    if "close window" in lower:
        return close_window()
    return None


def _cmd_memory_recall(text, lower, facts):
    if "what happened yesterday" in lower:
        daily = get_daily_memory()
        return daily if daily else "Nothing important was recorded yesterday"

    if "what do you remember about me" in lower:
        context = build_memory_context()
        return context if context else "I don't know much about you yet."

    if "how am i doing" in lower and "mood" in facts:
        return f"You seemed {facts['mood']} earlier… are you okay?"

    return None


def _cmd_open(text, lower, facts):
    if "open" not in lower:
        return None

    if "youtube" in lower:
        return open_website("youtube")
    if "google" in lower:
        return open_website("google")

    name = re.sub(r"^\s*open\s+", "", text, count=1, flags=re.I).strip()
    name_lower = name.lower()

    folder_result = open_named_folder(name_lower)
    if folder_result:
        return folder_result

    stripped_name = re.sub(
        r"\s+(folder|file)s?$", "", name_lower
    ).strip()

    if stripped_name and stripped_name != name_lower:
        folder_result = open_named_folder(stripped_name)
        if folder_result:
            return folder_result

    drive_result = open_drive(lower)
    if drive_result:
        return drive_result

    if name_lower.startswith("file ") or name_lower.startswith("folder "):
        path = re.sub(
            r"^(file|folder)\s+", "", name, flags=re.I
        ).strip()
        return open_path(path)

    result = open_app(text)
    if "couldn't find" not in result.lower():
        return result

    return open_smart(stripped_name or name)


def _cmd_volume(text, lower, facts):
    if "volume up" in lower:
        return volume_up()
    if "volume down" in lower:
        return volume_down()
    return None


def _cmd_power(text, lower, facts):
    if any(w in lower for w in ("shutdown", "stop server", "close server")):
        return (
            "Use the Stop Server button on the dashboard "
            "to shut the server down safely."
        )

    if "restart" in lower and (
        "pc" in lower or "computer" in lower or "windows" in lower
    ):
        return (
            "Use the Restart button on the dashboard - "
            "it'll ask you to confirm first."
        )

    if "sleep pc" in lower or ("sleep" in lower and "computer" in lower):
        return (
            "Use the Sleep button on the dashboard - "
            "it'll ask you to confirm first."
        )

    return None


COMMANDS = [
    _cmd_reminder,
    _cmd_web_search,
    _cmd_skill,
    _cmd_index_files,
    _cmd_open_my,
    _cmd_window,
    _cmd_drive,
    _cmd_memory_recall,
    _cmd_open,
    _cmd_volume,
    _cmd_power,
]


def _store_ai_extracted_memory(memory: dict):
    for k, v in memory.items():
        if not isinstance(v, str) or not v.strip():
            continue

        if k in ("like", "dislike"):
            save_fact_list(k, v)
        else:
            save_fact(k, v)


async def process(text, personality):
    lower = text.lower().strip()

    # =========================================================
    # 👋 STEP 1 — WAKE WORD
    # =========================================================
    if is_wake_word(text):
        reply = handle_wake_word(text)
        add_message("user", text)
        add_message("assistant", reply)
        return reply

    # =========================================================
    # 🧠 STEP 2 — LEARN FROM USER
    # =========================================================
    changes = learn_from_text(text)

    rel = update_relationship(text)
    facts = load_facts()
    conversation = load_conversation()

    # =========================================================
    # ⚡ STEP 3 — COMMAND ROUTER
    # =========================================================
    for command in COMMANDS:
        reply = command(text, lower, facts)
        if reply is not None:
            add_message("user", text)
            add_message("assistant", reply)
            remember_today(load_conversation())
            return reply

    # =========================================================
    # 📝 STEP 3.5 — QUICK FACT ACK
    # =========================================================
    ack = fact_ack(changes)
    if ack is not None:
        add_message("user", text)
        add_message("assistant", ack)
        remember_today(load_conversation())
        return ack

    # =========================================================
    # 🤖 STEP 4 — LLM FALLBACK
    # =========================================================
    if len(text.split()) >= 4:
        memory = await ai_extract_memory(text, personality)
        if memory:
            _store_ai_extracted_memory(memory)
            facts = load_facts()

    level = rel.get("level", load_relationship().get("level", 1))

    relationship_context = f"""
        Relationship Level: {level}
        User trust increases over time.
        At higher levels, be more personal, relaxed, and expressive.
    """

    memory_context = build_memory_context()

    enhanced_input = f"""
    {memory_context}
    {relationship_context}
    User: {text}
    """

    reply = await ask_ai(
        enhanced_input,
        personality,
        facts,
        conversation,
    )

    if level >= 4:
        if not reply.endswith(("?", ".", "!")):
            reply += "."
        reply = reply.replace("I will", "I'll").replace(
            "you are", "you're"
        )

    if level >= 5:
        reply = reply.replace("Hello", "Hey")

    add_message("user", text)

    if reply not in FALLBACK_REPLIES:
        add_message("assistant", reply)

    remember_today(load_conversation())

    return reply