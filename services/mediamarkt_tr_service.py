import json
from dataclasses import dataclass
from urllib.parse import quote_plus

import requests
from bs4 import BeautifulSoup

from schemas import PhoneCandidate, PriceObservation
from services.cache_service import get_cached_payload, set_cached_payload
from services.currency_service import to_usd


SEARCH_URL = "https://www.mediamarkt.com.tr/tr/search.html?query={query}"
PHONE_TERMS = {"akıllı", "telefon"}
ACCESSORY_TERMS = {"kılıf", "kapak", "uyumlu", "koruyucu", "aksesuar"}


@dataclass
class MediaMarktPriceResult:
    observations: list[PriceObservation]
    note: str


def search_mediamarkt_prices(phones: list[PhoneCandidate]) -> MediaMarktPriceResult:
    observations: list[PriceObservation] = []
    origins: set[str] = set()
    for phone in phones:
        payload, origin = _search(phone)
        origins.add(origin)
        observations.extend(_observations_from_payload(phone, payload))

    if "fresh" in origins:
        note = "Official specs with fresh MediaMarkt Turkey prices."
    elif "cache" in origins:
        note = "Official specs with Neon-cached MediaMarkt Turkey prices."
    else:
        note = "Official specs only. MediaMarkt Turkey prices are unavailable."
    return MediaMarktPriceResult(observations=observations, note=note)


def _search(phone: PhoneCandidate) -> tuple[dict | None, str]:
    query = f"{phone.brand} {phone.model}"
    query_key = f"mediamarkt-tr:{query.casefold()}"
    cached_payload = get_cached_payload(query_key)
    if cached_payload is not None:
        return cached_payload, "cache"

    try:
        response = requests.get(
            SEARCH_URL.format(query=quote_plus(query)),
            headers={"User-Agent": "Mozilla/5.0 PhoneAIAgent/0.1"},
            timeout=20,
        )
        response.raise_for_status()
    except requests.RequestException:
        return None, "failed"

    payload = _extract_json_ld(response.text)
    if payload is None:
        return None, "failed"
    set_cached_payload(query_key, payload, source="mediamarkt_tr_jsonld")
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
        currency = offers.get("priceCurrency", "")
        price = offers.get("price")
        if not _is_matching_phone(phone, title_words) or not price or not currency:
            continue
        observations.append(
            PriceObservation(
                phone_name=f"{phone.brand} {phone.model}",
                title=title,
                price=float(price),
                currency=currency,
                price_usd=to_usd(float(price), currency),
                store="MediaMarkt Turkey",
                product_url=product.get("url", ""),
            )
        )
    return observations[:2]


def _is_matching_phone(phone: PhoneCandidate, title_words: set[str]) -> bool:
    expected_words = {
        phone.brand.casefold(),
        *phone.model.casefold().replace("-", " ").split(),
    }
    has_phone_terms = PHONE_TERMS.issubset(title_words)
    has_accessory_terms = bool(ACCESSORY_TERMS.intersection(title_words))
    return expected_words.issubset(title_words) and has_phone_terms and not has_accessory_terms
