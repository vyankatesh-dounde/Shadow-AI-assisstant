"""Web search using DuckDuckGo's instant-answer endpoint."""

import requests


MAX_RESULTS = 5


def search_web(query: str) -> list[dict]:
    """Search without stealing the active window or overwriting clipboard.

    The former implementation launched Chrome and sent Ctrl+A/C through
    pyautogui. If Chrome was not foreground, those keystrokes affected the
    user's active application instead. DuckDuckGo's documented instant-answer
    endpoint is a safe best-effort source for compact results.
    """
    query = (query or "").strip()
    if not query:
        return []
    try:
        response = requests.get(
            "https://api.duckduckgo.com/",
            params={"q": query, "format": "json", "no_html": "1", "skip_disambig": "1"},
            timeout=10,
        )
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, ValueError):
        return []

    results = []
    if payload.get("AbstractText"):
        results.append({
            "title": payload.get("Heading") or query,
            "url": payload.get("AbstractURL", ""),
            "snippet": payload["AbstractText"],
        })

    def add_topics(topics):
        for topic in topics:
            if "Topics" in topic:
                add_topics(topic["Topics"])
            elif topic.get("Text"):
                results.append({
                    "title": topic["Text"].split(" - ", 1)[0],
                    "url": topic.get("FirstURL", ""),
                    "snippet": topic["Text"],
                })
            if len(results) >= MAX_RESULTS:
                return

    add_topics(payload.get("RelatedTopics", []))
    return results[:MAX_RESULTS]


def format_search_results(query: str, results: list[dict]) -> str:
    if not results:
        return (
            f"I couldn't retrieve web results for '{query}'."
        )

    lines = [f"Web results for: {query}"]

    for index, result in enumerate(results, 1):
        lines.append(f"{index}. {result['title']}")

        if result.get("url"):
            lines.append(f"   {result['url']}")

        if result.get("snippet"):
            lines.append(f"   {result['snippet']}")

    return "\n".join(lines)


def search_and_format(query: str) -> str:
    results = search_web(query)
    return format_search_results(query, results)
