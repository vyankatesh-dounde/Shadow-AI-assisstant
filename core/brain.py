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
from integrations.memory_integration import (
    learn_from_text,
    fact_ack,
    build_memory_context,
    get_daily_memory,
    remember_today,
)


# =========================================================
# ⚡ COMMAND HANDLERS
#
# Every function below takes (text, lower, facts) and returns either
# a reply string (it matched → stop here, LLM never runs) or None
# (it didn't match → keep trying the next one). This is the single
# source of truth for "is this a command Shadow already knows how to
# do, or does it need the LLM."
#
# ORDER MATTERS - checked top to bottom, first match wins.
# =========================================================

def _cmd_reminder(text, lower, facts):
    # "remind me to drink water in 10 minutes" etc.
    return try_create_reminder(text)

def _cmd_drive(text, lower, facts):
    # "C drive", "open D drive", "d:" — works with or without "open"
    return open_drive(lower)

def _cmd_skill(text, lower, facts):
    # math / time / date - fast, deterministic, no LLM needed.
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
    if "file" in lower or "folder" in lower:
        path = text.replace("open", "").strip()
        return open_path(path)

    name = lower.replace("open", "").strip()

    # "open desktop" / "open downloads" / etc.
    folder_result = open_named_folder(name)
    if folder_result:
        return folder_result

    # "open c drive" / "open d:"
    drive_result = open_drive(lower)
    if drive_result:
        return drive_result

    # known app shortcut (chrome, notepad, vs code, ...)
    result = open_app(text)
    if "couldn't find" not in result.lower():
        return result

    # last resort: fuzzy filesystem search
    return open_smart(name)


def _cmd_volume(text, lower, facts):
    if "volume up" in lower:
        return volume_up()
    if "volume down" in lower:
        return volume_down()
    return None


def _cmd_power(text, lower, facts):
    # Deliberately NOT triggered by a bare "shutdown"/"restart" word
    # with no context - a message merely *containing* one of these
    # used to restart/shut down the PC with zero confirmation. They
    # now always point to the dashboard's Power panel, which asks
    # first.
    if any(w in lower for w in ("shutdown", "stop server", "close server")):
        return "Use the Stop Server button on the dashboard to shut the server down safely."

    if "restart" in lower and ("pc" in lower or "computer" in lower or "windows" in lower):
        return "Use the Restart button on the dashboard - it'll ask you to confirm first."

    if "sleep pc" in lower or ("sleep" in lower and "computer" in lower):
        return "Use the Sleep button on the dashboard - it'll ask you to confirm first."

    return None


COMMANDS = [
    _cmd_reminder,
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


async def process(text, personality):
    lower = text.lower().strip()

    # =========================================================
    # 👋 STEP 1 — WAKE WORD (checked before literally anything else)
    #
    # A bare "shadow" / "hey shadow" is just the trigger that opens
    # the mic - it isn't a question. It gets a canned "Yes?" /
    # "Good morning..." reply and STOPS here. It is never learned
    # from, never scored for relationship points, never checked
    # against commands, and never sent to the LLM.
    # =========================================================
    if is_wake_word(text):
        reply = handle_wake_word(text)
        add_message("user", text)
        add_message("assistant", reply)
        return reply

    # =========================================================
    # 🧠 STEP 2 — LEARN FROM USER
    # Runs for every real message, whether it turns out to be a
    # command or something that needs the LLM. `changes` captures
    # what extract_and_store() actually saved/removed (if anything) -
    # used below, after the command router, to short-circuit plain
    # fact statements ("I like pizza") straight to a canned reply
    # instead of an LLM round trip.
    # =========================================================
    changes = learn_from_text(text)

    if len(text.split()) >= 4:
        memory = await ai_extract_memory(text, personality)
        for k, v in memory.items():
            if k in ("like", "dislike"):
                save_fact_list(k, str(v))
            else:
                save_fact(k, str(v))
        facts = load_facts()  # pick up anything ai_extract_memory just saved

    rel = update_relationship(text)
    facts = load_facts()
    conversation = load_conversation()

    # =========================================================
    # ⚡ STEP 3 — COMMAND ROUTER
    # Try every known command in order. The first one that matches
    # runs its action and returns immediately - the LLM never sees
    # this message at all.
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
    # No command matched, but Step 2 recognized a plain fact
    # statement (like/dislike/favorite/name). Give a short one-line
    # confirmation instead of sending it to the LLM - saying "I like
    # pizza" doesn't need a multi-paragraph reply about relationship
    # levels. Mood/important_event are deliberately excluded from
    # this shortcut (see build_fact_ack in core/memory_extractor.py)
    # so emotional disclosures still get a real response below.
    # =========================================================
    ack = fact_ack(changes)
    if ack is not None:
        add_message("user", text)
        add_message("assistant", ack)
        remember_today(load_conversation())
        return ack

    # =========================================================
    # 🤖 STEP 4 — NOTHING MATCHED → FALL THROUGH TO THE LLM
    # This is the only path that ever calls ask_ai().
    # =========================================================

    level = rel.get("level", load_relationship().get("level", 1))

    # ❤️ Relationship context
    relationship_context = f"""
        Relationship Level: {level}
        User trust increases over time.
        At higher levels, be more personal, relaxed, and expressive.
    """

    # 🧠 Memory context
    memory_context = build_memory_context()

    enhanced_input = f"""
    {memory_context}
    {relationship_context}
    User: {text}
    """

    reply = await ask_ai(enhanced_input, personality, facts, conversation)

    # 🎭 Behavior tweak (human-like) at higher relationship levels
    if level >= 4:
        if not reply.endswith(("?", ".", "!")):
            reply += "."
        reply = reply.replace("I will", "I'll").replace("you are", "you're")

    if level >= 5:
        reply = reply.replace("Hello", "Hey")

    # 💾 Save conversation - keep the user's side always, but don't
    # let a canned fallback ("I'm offline right now.", etc.) enter
    # history, since a small model will sometimes try to continue/
    # explain that meta-text on the next turn instead of answering
    # the new question.
    add_message("user", text)
    if reply not in FALLBACK_REPLIES:
        add_message("assistant", reply)

    remember_today(load_conversation())

    return reply