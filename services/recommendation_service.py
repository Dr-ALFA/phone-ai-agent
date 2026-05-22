from dataclasses import replace

from schemas import RecommendationResult, UserPreferences
from services.phone_repository import save_official_specs
from services.price_service import get_market_prices
from services.scoring_service import score_phones
from services.specs_service import collect_official_specs


def recommend_phones(preferences: UserPreferences, limit: int = 3) -> RecommendationResult:
    phones, specs_note = collect_official_specs()
    save_official_specs(phones)
    market_prices, price_result = get_market_prices(preferences.country, phones)
    priced_phones = [
        replace(phone, price_usd=market_prices.get(f"{phone.brand} {phone.model}"))
        for phone in phones
    ]
    ranked_phones = score_phones(priced_phones, preferences)[:limit]
    return RecommendationResult(
        phones=ranked_phones,
        data_note=f"{specs_note} {price_result.note}",
        price_observations=price_result.observations,
    )
