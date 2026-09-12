"""Read-only discovery tools for real-world tasks."""

from .maps_search import format_place_results, search_places
from .web_search import format_search_results, search_web


def search_movie_options(movie: str, date: str = "", time: str = "", people: int = 0, location: str = "") -> str:
    query = f"{movie} movie showtimes {date} {time} {location}".strip()
    return format_search_results(query, search_web(query))


def search_restaurant_options(restaurant: str, date: str = "", time: str = "", people: int = 0, location: str = "") -> str:
    results = search_places(restaurant, location)
    query = f"{restaurant} {location}".strip()
    if results:
        return format_place_results(query, results)
    return format_search_results(f"{restaurant} restaurant {date} {time} {location}".strip(), search_web(query))


def search_food_options(restaurant: str, items: str = "", location: str = "") -> str:
    query = f"{restaurant} {items} menu delivery {location}".strip()
    return format_search_results(query, search_web(query))


def book_movie(**_arguments) -> str:
    return "Movie booking is not configured. I found the options, but did not make a booking."


def reserve_restaurant(**_arguments) -> str:
    return "Restaurant reservations are not configured. I found the options, but did not make a reservation."


def place_food_order(**_arguments) -> str:
    return "Food ordering is not configured. I found the menu, but did not place an order."
