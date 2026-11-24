"""Consolidated web, place, and real-world discovery."""

from urllib.parse import urlencode
import requests

MAX_RESULTS = 1


def search_web(query: str) -> list[dict]:
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
                results.append({"title": topic["Text"].split(" - ", 1)[0], "url": topic.get("FirstURL", ""), "snippet": topic["Text"]})
            if len(results) >= MAX_RESULTS:
                return
    add_topics(payload.get("RelatedTopics", []))
    return results[:MAX_RESULTS]


def format_search_results(query: str, results: list[dict]) -> str:
    if not results:
        return f"I couldn't retrieve web results for '{query}'."
    lines = [f"Web results for: {query}"]
    for index, result in enumerate(results, 1):
        lines.append(f"{index}. {result['title']}")
        if result.get("url"):
            lines.append(f"   {result['url']}")
        if result.get("snippet"):
            lines.append(f"   {result['snippet']}")
    return "\n".join(lines)


def search_and_format(query: str) -> str:
    return format_search_results(query, search_web(query))


def search_places(query: str, location: str = "") -> list[dict]:
    query = (query or "").strip()
    location = (location or "").strip()
    if not query:
        return []
    try:
        response = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": f"{query} {location}".strip(), "format": "jsonv2", "addressdetails": 1, "extratags": 1, "limit": 5},
            headers={"User-Agent": "Shadow-AI/1.0 (local assistant place search)"},
            timeout=10,
        )
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, ValueError):
        return []
    results = []
    for item in payload if isinstance(payload, list) else []:
        extra = item.get("extratags") or {}
        latitude, longitude = item.get("lat"), item.get("lon")
        map_url = ("https://www.google.com/maps/search?" + urlencode({"api": 1, "query": f"{latitude},{longitude}"})) if latitude and longitude else ""
        results.append({
            "name": item.get("name") or item.get("display_name", "").split(",", 1)[0],
            "address": item.get("display_name", ""),
            "phone": extra.get("phone") or extra.get("contact:phone", ""),
            "website": extra.get("website") or extra.get("contact:website", ""),
            "map_url": map_url,
        })
    return results


def format_place_results(query: str, results: list[dict]) -> str:
    if not results:
        return f"I couldn't find map results for '{query}'."
    lines = [f"Map results for: {query}"]
    for index, result in enumerate(results, 1):
        lines.append(f"{index}. {result['name']}")
        if result.get("address"):
            lines.append(f"   Address: {result['address']}")
        if result.get("phone"):
            lines.append(f"   Phone: {result['phone']}")
        if result.get("website"):
            lines.append(f"   Website: {result['website']}")
        if result.get("map_url"):
            lines.append(f"   Map: {result['map_url']}")
    return "\n".join(lines)


def search_places_and_format(query: str, location: str = "") -> str:
    return format_place_results(f"{query} {location}".strip(), search_places(query, location))


def search_movie_options(movie: str, date: str = "", time: str = "", people: int = 0, location: str = "") -> str:
    query = f"{movie} movie showtimes {date} {time} {location}".strip()
    return format_search_results(query, search_web(query))

def search_restaurant_options(restaurant: str, date: str = "", time: str = "", people: int = 0, location: str = "") -> str:
    results = search_places(restaurant, location)
    query = f"{restaurant} {location}".strip()
    return format_place_results(query, results) if results else format_search_results(f"{restaurant} restaurant {date} {time} {location}".strip(), search_web(query))

def search_food_options(restaurant: str, items: str = "", location: str = "") -> str:
    query = f"{restaurant} {items} menu delivery {location}".strip()
    return format_search_results(query, search_web(query))

def book_movie(**_arguments): return "Movie booking is not configured."
def reserve_restaurant(**_arguments): return "Restaurant reservations are not configured."
def place_food_order(**_arguments): return "Food ordering is not configured."

__all__ = [
    "search_places_and_format",
    "search_and_format",
    "book_movie",
    "place_food_order",
    "reserve_restaurant",
    "search_food_options",
    "search_movie_options",
    "search_restaurant_options",
]
