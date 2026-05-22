from dataclasses import replace

from schemas import RecommendationResult, UserPreferences
from services.phone_repository import save_official_specs
from services.price_service import get_market_prices
from services.scoring_service import score_phones
from services.specs_service import collect_official_specs


def recommend_phones(preferences: UserPreferences, limit: int = 3) -> RecommendationResult:
    phones, specs_note = collect_official_specs()
    save_official_specs(phones)
    phones_for_pricing = _pricing_candidates(phones, preferences)
    market_prices, price_result = get_market_prices(preferences.country, phones_for_pricing)
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


def _pricing_candidates(phones, preferences, limit: int = 16):
    score_names = {
        "camera": "camera_score",
        "gaming": "gaming_score",
        "battery": "battery_score",
        "screen": "screen_score",
        "work_study": "work_score",
        "social_media": "social_score",
        "compact": "compact_score",
        "storage": "storage_score",
    }

    def relevance(phone):
        priority_scores = [
            getattr(phone, score_names[priority])
            for priority in preferences.priorities
            if priority in score_names
        ]
        priority_score = sum(priority_scores) / len(priority_scores) if priority_scores else 0
        return priority_score + phone.value_score + phone.battery_score / 4

    eligible = [
        phone
        for phone in phones
        if preferences.os_preference == "any" or phone.os == preferences.os_preference
    ]
    return sorted(eligible, key=relevance, reverse=True)[:limit]
