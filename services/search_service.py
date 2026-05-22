import hashlib
from dataclasses import dataclass
from typing import Any

import requests

from config import SERPAPI_API_KEY
from services.cache_service import get_cached_payload, set_cached_payload


SERPAPI_ENDPOINT = "https://serpapi.com/search.json"
COUNTRY_GL = {
    "turkey": "tr",
    "turkiye": "tr",
    "türkiye": "tr",
    "saudi arabia": "sa",
    "ksa": "sa",
    "united states": "us",
    "usa": "us",
}


@dataclass
class SearchPayload:
    payload: dict[str, Any] | None
    note: str


def search_shopping_prices(query: str, country: str) -> SearchPayload:
    query_key = _cache_key(query, country)
    cached_payload = get_cached_payload(query_key)
    if cached_payload is not None:
        return SearchPayload(
            payload=cached_payload,
            note="Official specs with Neon-cached shopping price observations.",
        )

    if not SERPAPI_API_KEY:
        return SearchPayload(
            payload=None,
            note="Official specs only. Add SERPAPI_API_KEY to fetch new shopping prices.",
        )

    params = {
        "engine": "google_shopping",
        "q": query,
        "gl": _country_code(country),
        "hl": "en",
        "api_key": SERPAPI_API_KEY,
    }
    try:
        response = requests.get(SERPAPI_ENDPOINT, params=params, timeout=15)
        response.raise_for_status()
        payload = response.json()
    except requests.RequestException:
        return SearchPayload(
            payload=None,
            note="Seed specs only. Shopping provider is unavailable right now.",
        )
    set_cached_payload(query_key, payload, source="serpapi_google_shopping")
    return SearchPayload(
        payload=payload,
        note="Official specs with fresh shopping price observations.",
    )


def _cache_key(query: str, country: str) -> str:
    digest = hashlib.sha256(f"{country.casefold()}::{query.casefold()}".encode()).hexdigest()
    return f"serpapi-shopping:{digest}"


def _country_code(country: str) -> str:
    return COUNTRY_GL.get(country.strip().casefold(), "us")
