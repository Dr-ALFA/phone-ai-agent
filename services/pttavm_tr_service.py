import json
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from urllib.parse import quote_plus

import requests
from bs4 import BeautifulSoup

from schemas import PhoneCandidate, PriceObservation
from services.cache_service import get_cached_payload, set_cached_payload
from services.currency_service import to_usd


SEARCH_URL = "https://www.pttavm.com/arama?q={query}"
ACCESSORY_TERMS = {
    "kılıf",
    "kilif",
    "uyumlu",
    "koruyucu",
    "cam",
    "lens",
    "kapak",
    "aksesuar",
}


@dataclass
class PttAvmPriceResult:
    observations: list[PriceObservation]
    note: str


def search_pttavm_prices(phones: list[PhoneCandidate]) -> PttAvmPriceResult:
    observations: list[PriceObservation] = []
    origins: set[str] = set()
    with ThreadPoolExecutor(max_workers=6) as executor:
        results = list(zip(phones, executor.map(_search, phones)))
    for phone, (payload, origin) in results:
        origins.add(origin)
        observations.extend(_observations_from_payload(phone, payload))

    if "fresh" in origins:
        note = "Official specs with fresh PttAVM Turkey prices."
    elif "cache" in origins:
        note = "Official specs with Neon-cached PttAVM Turkey prices."
    else:
        note = "Official specs only. PttAVM Turkey prices are unavailable."
    return PttAvmPriceResult(observations=observations, note=note)


def _search(phone: PhoneCandidate) -> tuple[dict | None, str]:
    query = f"{phone.brand} {phone.model} akıllı telefon"
    query_key = f"pttavm-tr:{query.casefold()}"
    cached_payload = get_cached_payload(query_key)
    if cached_payload is not None:
        return cached_payload, "cache"

    try:
        response = requests.get(
            SEARCH_URL.format(query=quote_plus(query)),
            headers={"User-Agent": "Mozilla/5.0 PhoneAIAgent/0.1"},
            timeout=10,
        )
        response.raise_for_status()
    except requests.RequestException:
        return None, "failed"

    payload = _extract_json_ld(response.text)
    if payload is None:
        return None, "failed"
    set_cached_payload(query_key, payload, source="pttavm_tr_jsonld")
    return payload, "fresh"


def _extract_json_ld(html: str) -> dict | None:
    soup = BeautifulSoup(html, "html.parser")
    script = soup.find("script", attrs={"type": "application/ld+json"})
    if script is None:
        return None
    try:
        return json.loads(script.get_text())
    except json.JSONDecodeError:
        return None


def _observations_from_payload(
    phone: PhoneCandidate,
    payload: dict | None,
) -> list[PriceObservation]:
    if payload is None:
        return []

    observations: list[PriceObservation] = []
    for item in payload.get("itemListElement", []):
        product = item.get("item", {})
        title = product.get("name", "")
        title_words = set(title.casefold().replace("-", " ").split())
        offers = product.get("offers", {})
        price = offers.get("price")
        currency = offers.get("priceCurrency", "")
        if not _matches_phone(phone, title_words) or not price or not currency:
            continue
        observations.append(
            PriceObservation(
                phone_name=f"{phone.brand} {phone.model}",
                title=title,
                price=float(price),
                currency=currency,
                price_usd=to_usd(float(price), currency),
                store="PttAVM Turkey",
                product_url=product.get("url", ""),
            )
        )
    return observations[:2]


def _matches_phone(phone: PhoneCandidate, title_words: set[str]) -> bool:
    expected_words = {
        phone.brand.casefold(),
        *phone.model.casefold().replace("-", " ").split(),
    }
    return expected_words.issubset(title_words) and not ACCESSORY_TERMS.intersection(title_words)
