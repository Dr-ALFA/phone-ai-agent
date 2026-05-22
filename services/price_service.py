from dataclasses import dataclass

from schemas import PhoneCandidate, PriceObservation
from services.currency_service import to_usd
from services.mediamarkt_tr_service import search_mediamarkt_prices
from services.phone_repository import load_fresh_market_prices, save_price_observations
from services.pttavm_tr_service import search_pttavm_prices
from services.search_service import search_shopping_prices


@dataclass
class PriceCollection:
    observations: list[PriceObservation]
    note: str


def collect_price_observations(
    country: str,
    phones: list[PhoneCandidate],
) -> PriceCollection:
    observations: list[PriceObservation] = []
    notes: list[str] = []

    for phone in phones:
        query = f"{phone.brand} {phone.model} phone {country}"
        search_result = search_shopping_prices(query, country)
        notes.append(search_result.note)
        observations.extend(_matching_observations(phone, search_result.payload))

    save_price_observations(country, observations)
    return PriceCollection(
        observations=observations,
        note=_best_note(notes),
    )


def _matching_observations(
    phone: PhoneCandidate,
    payload: dict | None,
) -> list[PriceObservation]:
    if payload is None:
        return []

    expected_terms = {
        phone.brand.casefold(),
        *phone.model.casefold().replace("-", " ").split(),
    }
    matched: list[PriceObservation] = []
    for result in payload.get("shopping_results", []):
        title = result.get("title", "")
        title_terms = title.casefold().replace("-", " ").split()
        price = result.get("extracted_price")
        if (
            not price
            or result.get("second_hand_condition")
            or not expected_terms.issubset(set(title_terms))
        ):
            continue
        matched.append(
            PriceObservation(
                phone_name=f"{phone.brand} {phone.model}",
                title=title,
                price=float(price),
                currency=_currency_from_result(result),
                price_usd=to_usd(float(price), _currency_from_result(result)),
                store=result.get("source", "Unknown store"),
                product_url=result.get("product_link", ""),
            )
        )
    return matched[:2]


def _currency_from_result(result: dict) -> str:
    alternative_price = result.get("alternative_price") or {}
    if alternative_price.get("currency"):
        return alternative_price["currency"]
    price_text = result.get("price", "")
    if "₺" in price_text or "TRY" in price_text:
        return "TRY"
    if "SAR" in price_text or "ر.س" in price_text:
        return "SAR"
    if "$" in price_text:
        return "USD"
    return "LOCAL"


def _best_note(notes: list[str]) -> str:
    if any("fresh" in note for note in notes):
        return "Official specs with fresh shopping price observations."
    if any("Neon-cached" in note for note in notes):
        return "Official specs with Neon-cached shopping price observations."
    return notes[0] if notes else "Official specs only."


def get_market_prices(
    country: str,
    phones: list[PhoneCandidate],
) -> tuple[dict[str, float], PriceCollection]:
    stored_prices = load_fresh_market_prices(country, phones)
    missing_price_phones = [
        phone
        for phone in phones
        if f"{phone.brand} {phone.model}" not in stored_prices
    ]
    if not missing_price_phones:
        return stored_prices, PriceCollection(
            observations=[],
            note="Official specs with fresh Neon market prices.",
        )

    if _is_turkey(country):
        mediamarkt_result = search_mediamarkt_prices(missing_price_phones)
        pttavm_result = search_pttavm_prices(missing_price_phones)
        turkey_observations = [
            *mediamarkt_result.observations,
            *pttavm_result.observations,
        ]
        save_price_observations(country, turkey_observations)
        turkey_prices = _observed_usd_prices(turkey_observations)
        if turkey_prices:
            return {**stored_prices, **turkey_prices}, PriceCollection(
                observations=turkey_observations,
                note=f"{mediamarkt_result.note} {pttavm_result.note}",
            )

    collection = collect_price_observations(country, missing_price_phones)
    return {**stored_prices, **_observed_usd_prices(collection.observations)}, collection


def _observed_usd_prices(observations: list[PriceObservation]) -> dict[str, float]:
    observed_prices: dict[str, float] = {}
    for observation in observations:
        if observation.price_usd is None:
            continue
        observed_prices[observation.phone_name] = min(
            observed_prices.get(observation.phone_name, observation.price_usd),
            observation.price_usd,
        )
    return observed_prices


def _is_turkey(country: str) -> bool:
    return country.strip().casefold() in {"turkey", "turkiye", "türkiye", "tr"}
