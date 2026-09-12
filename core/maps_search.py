"""Read-only place lookup using OpenStreetMap's public Nominatim service."""

from urllib.parse import urlencode

import requests


NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "Shadow-AI/1.0 (local assistant place search)"
MAX_RESULTS = 5


def search_places(query: str, location: str = "") -> list[dict]:
    query = (query or "").strip()
    location = (location or "").strip()
    if not query:
        return []

    search_query = f"{query} {location}".strip()
    try:
        response = requests.get(
            NOMINATIM_URL,
            params={
                "q": search_query,
                "format": "jsonv2",
                "addressdetails": 1,
                "extratags": 1,
                "limit": MAX_RESULTS,
            },
            headers={"User-Agent": USER_AGENT},
            timeout=10,
        )
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, ValueError):
        return []

    results = []
    for item in payload if isinstance(payload, list) else []:
        extra = item.get("extratags") or {}
        latitude = item.get("lat")
        longitude = item.get("lon")
        map_url = ""
        if latitude and longitude:
            map_url = "https://www.google.com/maps/search/?" + urlencode(
                {"api": 1, "query": f"{latitude},{longitude}"}
            )
        results.append({
            "name": item.get("name") or item.get("display_name", "").split(",", 1)[0],
            "address": item.get("display_name", ""),
            "phone": extra.get("phone") or extra.get("contact:phone", ""),
            "website": extra.get("website") or extra.get("contact:website", ""),
            "map_url": map_url,
            "latitude": latitude,
            "longitude": longitude,
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
    full_query = f"{query} {location}".strip()
    return format_place_results(full_query, search_places(query, location))
