import re
from dataclasses import dataclass

import requests

from config import TAVILY_API_KEY
from services.cache_service import get_cached_payload, set_cached_payload


TAVILY_ENDPOINT = "https://api.tavily.com/search"
DISCOVERY_SEARCHES = [
    {
        "query": "official Apple iPhone tech specs iPhone 16 iPhone 15",
        "domains": ["support.apple.com"],
    },
    {
        "query": "official OnePlus phone specs OnePlus Nord 4 OnePlus 12R",
        "domains": ["oneplus.com"],
    },
]


@dataclass(frozen=True)
class DiscoveredSpecSource:
    brand: str
    model: str
    os: str
    source_url: str
    page_parser: str


def discover_official_spec_sources() -> tuple[list[DiscoveredSpecSource], str]:
    if not TAVILY_API_KEY:
        return [], "TAVILY_API_KEY is not set for official spec discovery."

    sources: list[DiscoveredSpecSource] = []
    for search in DISCOVERY_SEARCHES:
        payload = _search(search["query"], search["domains"])
        if payload is None:
            continue
        for result in payload.get("results", []):
            source = _source_from_result(result)
            if source is not None:
                sources.append(source)
    unique_sources = {source.source_url: source for source in sources}
    return list(unique_sources.values()), f"Tavily discovered {len(unique_sources)} official spec pages."


def _search(query: str, domains: list[str]) -> dict | None:
    query_key = f"tavily-spec-discovery:{query.casefold()}"
    cached_payload = get_cached_payload(query_key)
    if cached_payload is not None:
        return cached_payload

    try:
        response = requests.post(
            TAVILY_ENDPOINT,
            headers={
                "Authorization": f"Bearer {TAVILY_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "query": query,
                "topic": "general",
                "search_depth": "basic",
                "include_answer": False,
                "include_raw_content": False,
                "max_results": 10,
                "include_domains": domains,
            },
            timeout=20,
        )
        response.raise_for_status()
    except requests.RequestException:
        return None

    payload = response.json()
    set_cached_payload(query_key, payload, source="tavily_spec_discovery")
    return payload


def _source_from_result(result: dict) -> DiscoveredSpecSource | None:
    title = result.get("title", "")
    url = result.get("url", "")
    iphone = re.search(
        r"(iPhone\s+\d+(?:\s+Plus)?)\s+-\s+(?:Tech Specs|Technical Specifications)",
        title,
    )
    if iphone and iphone.group(1) in {"iPhone 15", "iPhone 16"} and "support.apple.com" in url:
        return DiscoveredSpecSource(
            brand="Apple",
            model=iphone.group(1),
            os="ios",
            source_url=url,
            page_parser="iphone_generic",
        )

    oneplus = re.search(r"(OnePlus\s+.+?)\s+Specs", title)
    if oneplus and "oneplus.com" in url:
        model = oneplus.group(1).removeprefix("OnePlus ").strip()
        return DiscoveredSpecSource(
            brand="OnePlus",
            model=model,
            os="android",
            source_url=url,
            page_parser="oneplus_generic",
        )
    return None
