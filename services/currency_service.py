import requests

from services.cache_service import get_cached_payload, set_cached_payload


FRANKFURTER_RATE_URL = "https://api.frankfurter.dev/v1/latest"


def to_usd(amount: float, currency: str) -> float | None:
    if currency == "USD":
        return round(amount, 2)
    if currency in {"LOCAL", ""}:
        return None

    payload = _load_usd_rate(currency)
    rate = payload.get("rates", {}).get("USD") if payload else None
    if rate is None:
        return None
    return round(amount * float(rate), 2)


def _load_usd_rate(currency: str) -> dict | None:
    query_key = f"fx:{currency}:USD"
    cached_payload = get_cached_payload(query_key)
    if cached_payload is not None:
        return cached_payload

    try:
        response = requests.get(
            FRANKFURTER_RATE_URL,
            params={"base": currency, "symbols": "USD"},
            timeout=10,
        )
        response.raise_for_status()
    except requests.RequestException:
        return None

    payload = response.json()
    set_cached_payload(query_key, payload, source="frankfurter_fx")
    return payload
