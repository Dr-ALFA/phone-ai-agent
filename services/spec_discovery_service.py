import re
from dataclasses import dataclass

import requests

from config import TAVILY_API_KEY
from services.cache_service import get_cached_payload, set_cached_payload


TAVILY_ENDPOINT = "https://api.tavily.com/search"
MAX_DISCOVERED_PER_BRAND = 6
BRAND_SEARCHES = [
    {"brand": "Apple", "query": "official iPhone tech specs", "domains": ["support.apple.com"]},
    {"brand": "Samsung", "query": "official Samsung Galaxy smartphone specifications", "domains": ["samsung.com"]},
    {"brand": "Xiaomi", "query": "official Xiaomi Redmi POCO phone specs", "domains": ["mi.com"]},
    {"brand": "Google", "query": "official Pixel phone technical specifications", "domains": ["support.google.com", "store.google.com"]},
    {"brand": "OnePlus", "query": "official OnePlus phone specs", "domains": ["oneplus.com"]},
    {"brand": "Motorola", "query": "official Motorola phone specifications", "domains": ["motorola.com"]},
    {"brand": "Honor", "query": "official HONOR smartphone specifications", "domains": ["honor.com"]},
    {"brand": "Oppo", "query": "official OPPO phone specs", "domains": ["oppo.com"]},
    {"brand": "Realme", "query": "official realme phone specs", "domains": ["realme.com"]},
    {"brand": "General Mobile", "query": "General Mobile smartphone technical specifications", "domains": ["generalmobile.com"]},
    {"brand": "Casper", "query": "Casper VIA telefon teknik özellikleri", "domains": ["casper.com.tr"]},
    {"brand": "Reeder", "query": "Reeder telefon teknik özellikleri", "domains": ["reeder.com.tr"]},
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
    for search in BRAND_SEARCHES:
        payload = _search(search["query"], search["domains"])
        if payload is None:
            continue
        for result in payload.get("results", []):
            source = _source_from_result(search["brand"], result)
            if source is not None:
                sources.append(source)
    unique_sources = _cap_sources_by_brand(sources)
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


def _source_from_result(brand: str, result: dict) -> DiscoveredSpecSource | None:
    title = result.get("title", "")
    url = result.get("url", "")
    iphone = re.search(
        r"(iPhone\s+\d+(?:\s+Plus)?)\s+-\s+(?:Tech Specs|Technical Specifications)",
        title,
    )
    if brand == "Apple" and iphone and iphone.group(1) in {"iPhone 15", "iPhone 16"} and "support.apple.com" in url:
        return DiscoveredSpecSource(
            brand="Apple",
            model=iphone.group(1),
            os="ios",
            source_url=url,
            page_parser="iphone_generic",
        )
    if brand == "Apple":
        return None

    oneplus = re.search(r"(OnePlus\s+.+?)\s+Specs", title)
    if brand == "OnePlus" and oneplus and "oneplus.com" in url:
        model = oneplus.group(1).removeprefix("OnePlus ").strip()
        if _non_phone_title(model):
            return None
        return DiscoveredSpecSource(
            brand="OnePlus",
            model=model,
            os="android",
            source_url=url,
            page_parser="oneplus_generic",
        )
    model = _generic_model_from_title(brand, title)
    if model is None or _non_phone_title(model) or not _looks_like_product_page(url):
        return None
    return DiscoveredSpecSource(
        brand=brand,
        model=model,
        os="android",
        source_url=url,
        page_parser="generic_official",
    )


def _generic_model_from_title(brand: str, title: str) -> str | None:
    cleaned = re.split(r"\s*(?:\||-|–|:)\s*", title, maxsplit=1)[0].strip()
    if brand == "Google":
        match = re.search(r"(Pixel\s+[A-Za-z0-9 ]+)", title)
        return _clean_model(match.group(1)) if match else None
    if brand == "Samsung":
        match = re.search(r"(Galaxy\s+[A-Za-z0-9+ ]+)", cleaned)
        return _clean_model(match.group(1)) if match else None
    if brand == "Xiaomi":
        match = re.search(r"((?:Xiaomi|Redmi|POCO)\s+[A-Za-z0-9+ ]+)", cleaned, re.IGNORECASE)
        return _clean_model(match.group(1)) if match else None
    if brand == "General Mobile":
        match = re.search(r"(GM\s+[A-Za-z0-9+ ]+)", cleaned)
        return _clean_model(match.group(1)) if match else None
    if brand == "Casper":
        match = re.search(r"(VIA\s+[A-Za-z0-9+ ]+)", title)
        return _clean_model(match.group(1)) if match else None
    if brand == "Reeder":
        match = re.search(r"(?:Reeder\s+)?([A-Za-z]*\d+[A-Za-z0-9+ ]*)", cleaned)
        return _clean_model(match.group(1)) if match else None
    if brand.casefold() in title.casefold():
        return _clean_model(cleaned.removeprefix(brand))
    return None


def _looks_like_product_page(url: str) -> bool:
    lowered = url.casefold()
    blocked = (
        "blog",
        "news",
        "compare",
        "support/contact",
        "category",
        "telefon-modelleri",
        "all-smartphones",
        "product-list",
        "hardware-diagram",
    )
    return not any(term in lowered for term in blocked)


def _non_phone_title(value: str) -> bool:
    blocked = (
        "watch",
        "buds",
        "pad",
        "tablet",
        "phones",
        "smartphones",
        "series",
        "features",
        "hardware",
        "diagram",
        "accessory",
        "specifications",
        "camera specifications",
    )
    lowered = value.casefold()
    return any(term in lowered for term in blocked)


def _clean_model(value: str) -> str | None:
    model = re.sub(
        r"\b(?:Smartphone|Technical|Specifications|Specification|Specs|Telefon)\b",
        "",
        value,
        flags=re.IGNORECASE,
    )
    model = " ".join(model.split()).strip(" -|")
    return model or None


def _cap_sources_by_brand(sources: list[DiscoveredSpecSource]) -> dict[str, DiscoveredSpecSource]:
    unique_sources: dict[str, DiscoveredSpecSource] = {}
    brand_counts: dict[str, int] = {}
    for source in sources:
        if brand_counts.get(source.brand, 0) >= MAX_DISCOVERED_PER_BRAND:
            continue
        if source.source_url in unique_sources:
            continue
        unique_sources[source.source_url] = source
        brand_counts[source.brand] = brand_counts.get(source.brand, 0) + 1
    return unique_sources
