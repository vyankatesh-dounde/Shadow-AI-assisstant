"""
Shadow Google + Chrome search skill.

Instead of scraping Google's HTML from Python (which Google may block),
this skill uses the user's actual Chrome browser:

1. Opens a Google search in Chrome.
2. Waits for the results page to load.
3. Copies the visible page text from Chrome.
4. Parses the copied text into a compact list of search results.
5. Returns the results to Shadow.

This is intentionally Windows/Chrome oriented because Shadow is a
desktop assistant designed to control the local Windows PC.
"""

import re
import subprocess
import time
import webbrowser
from pathlib import Path
from urllib.parse import quote_plus

import pyautogui


GOOGLE_SEARCH_URL = "https://www.google.com/search"
CHROME_WAIT_SECONDS = 2.5
MAX_RESULTS = 5


def _chrome_path():
    candidates = [
        Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
        Path(r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"),
        Path.home()
        / r"AppData\Local\Google\Chrome\Application\chrome.exe",
    ]

    for path in candidates:
        if path.exists():
            return str(path)

    return None


def _open_chrome(url: str) -> bool:
    try:
        chrome = _chrome_path()

        if chrome:
            subprocess.Popen([chrome, url])
        else:
            webbrowser.open(url)

        return True
    except Exception as exc:
        print("Chrome open error:", exc)
        return False


def _get_clipboard_text() -> str:
    """Read Windows clipboard without requiring pyperclip."""
    try:
        import tkinter as tk

        root = tk.Tk()
        root.withdraw()

        try:
            value = root.clipboard_get()
        finally:
            root.destroy()

        return value if isinstance(value, str) else ""

    except Exception as exc:
        print("Clipboard read error:", exc)
        return ""


def _copy_page_text() -> str:
    """Copy the visible text of the active Chrome page."""
    try:
        pyautogui.hotkey("ctrl", "a")
        time.sleep(0.15)
        pyautogui.hotkey("ctrl", "c")
        time.sleep(0.35)
        return _get_clipboard_text()
    except Exception as exc:
        print("Chrome page copy error:", exc)
        return ""


def _looks_blocked(page_text: str) -> bool:
    lower = page_text.lower()

    blocked_markers = (
        "unusual traffic",
        "captcha",
        "verify you're a human",
        "our systems have detected unusual traffic",
    )

    return any(marker in lower for marker in blocked_markers)


def _clean_lines(page_text: str) -> list[str]:
    lines = []

    for raw in page_text.splitlines():
        line = re.sub(r"\s+", " ", raw).strip()

        if not line:
            continue

        # Remove common Google navigation noise.
        if line in {
            "Images",
            "Videos",
            "News",
            "Maps",
            "Shopping",
            "More",
            "Tools",
            "Settings",
            "Sign in",
        }:
            continue

        lines.append(line)

    return lines


def _looks_like_url(line: str) -> bool:
    return bool(
        re.match(
            r"^(https?://|www\.)",
            line,
            flags=re.I,
        )
    )


def _parse_results(page_text: str, query: str) -> list[dict]:
    """Best-effort parser for the copied Google results page.

    Google changes its page structure frequently. We therefore parse
    the stable human-readable text rather than relying on Google's
    private HTML classes.
    """
    lines = _clean_lines(page_text)

    results = []
    seen_titles = set()

    # Search result pages commonly expose:
    # title
    # URL/breadcrumb
    # snippet
    #
    # We identify likely result titles by finding lines followed by a
    # URL-like line, then collect a short snippet afterward.
    for i, line in enumerate(lines):
        if i + 1 >= len(lines):
            continue

        url_line = lines[i + 1]

        if not _looks_like_url(url_line):
            continue

        title = line

        # Skip Google UI / query metadata.
        if len(title) < 3 or len(title) > 180:
            continue

        if title.casefold() in seen_titles:
            continue

        snippet_parts = []

        for candidate in lines[i + 2:i + 7]:
            if _looks_like_url(candidate):
                break

            if candidate.lower() in {
                "cached",
                "more results",
                "people also ask",
            }:
                continue

            snippet_parts.append(candidate)

            if len(" ".join(snippet_parts)) >= 220:
                break

        results.append({
            "title": title,
            "url": url_line,
            "snippet": " ".join(snippet_parts)[:300],
        })

        seen_titles.add(title.casefold())

        if len(results) >= MAX_RESULTS:
            break

    # Fallback: if Google rendered URLs differently, return useful
    # text chunks rather than claiming nothing was found.
    if not results:
        candidates = []

        for line in lines:
            lower = line.lower()

            if query.lower() in lower:
                continue

            if len(line) >= 25 and len(line) <= 180:
                candidates.append(line)

        for line in candidates[:MAX_RESULTS]:
            results.append({
                "title": line,
                "url": "",
                "snippet": "",
            })

    return results


def search_google_with_chrome(
    query: str,
    open_browser: bool = True,
) -> list[dict]:
    query = (query or "").strip()

    if not query:
        return []

    url = f"{GOOGLE_SEARCH_URL}?q={quote_plus(query)}"

    if open_browser:
        if not _open_chrome(url):
            return []

        time.sleep(CHROME_WAIT_SECONDS)

    page_text = _copy_page_text()

    if not page_text:
        return []

    if _looks_blocked(page_text):
        return [{
            "title": "Google requires verification",
            "url": url,
            "snippet": (
                "Google displayed a verification page. "
                "The search was opened in Chrome, but Shadow "
                "could not safely read the results."
            ),
        }]

    return _parse_results(page_text, query)


def format_search_results(query: str, results: list[dict]) -> str:
    if not results:
        return (
            f"I opened Google for '{query}', but I couldn't read the "
            "results from Chrome."
        )

    if (
        len(results) == 1
        and results[0]["title"] == "Google requires verification"
    ):
        return (
            f"Google opened in Chrome for '{query}', but Google is "
            "asking for verification. Complete it in Chrome and try again."
        )

    lines = [f"Google results for: {query}"]

    for index, result in enumerate(results, 1):
        lines.append(f"{index}. {result['title']}")

        if result.get("url"):
            lines.append(f"   {result['url']}")

        if result.get("snippet"):
            lines.append(f"   {result['snippet']}")

    return "\n".join(lines)


def search_and_format(query: str) -> str:
    results = search_google_with_chrome(query)
    return format_search_results(query, results)


def open_google_search(query: str) -> str:
    query = (query or "").strip()

    if not query:
        return "What should I search for?"

    url = f"{GOOGLE_SEARCH_URL}?q={quote_plus(query)}"

    if _open_chrome(url):
        return f"Opening Google results for {query}"

    return "I couldn't open Chrome."