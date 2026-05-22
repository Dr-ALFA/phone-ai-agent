from schemas import PhoneCandidate, ScoredPhone, UserPreferences


BASE_WEIGHTS = {
    "camera": 0.14,
    "gaming": 0.10,
    "battery": 0.12,
    "screen": 0.08,
    "work_study": 0.08,
    "social_media": 0.06,
    "compact": 0.04,
    "storage": 0.08,
    "value": 0.30,
}

SCORE_FIELDS = {
    "camera": "camera_score",
    "gaming": "gaming_score",
    "battery": "battery_score",
    "screen": "screen_score",
    "work_study": "work_score",
    "social_media": "social_score",
    "compact": "compact_score",
    "storage": "storage_score",
    "value": "value_score",
}

PRIORITY_REASON = {
    "camera": "الكاميرا مناسبة لأولوية التصوير",
    "gaming": "الأداء مناسب للألعاب",
    "battery": "البطارية مناسبة للاستخدام الطويل",
    "screen": "الشاشة قوية للمشاهدة والاستخدام اليومي",
    "work_study": "الذاكرة والأداء مناسبين للشغل والدراسة",
    "social_media": "التجربة مناسبة للتصوير والنشر والسوشيال",
    "compact": "الحجم أقرب لطلب الهاتف الصغير",
    "storage": "التخزين مناسب للملفات والصور",
}


def score_phones(
    phones: list[PhoneCandidate],
    preferences: UserPreferences,
) -> list[ScoredPhone]:
    filtered_phones = [phone for phone in phones if _matches_filters(phone, preferences)]
    weights = _build_weights(preferences.priorities)
    scored = [
        ScoredPhone(
            phone=phone,
            score=_weighted_score(phone, weights),
            reasons=_build_reasons(phone, preferences),
        )
        for phone in filtered_phones
    ]
    return sorted(scored, key=lambda candidate: candidate.score, reverse=True)


def _matches_filters(phone: PhoneCandidate, preferences: UserPreferences) -> bool:
    rejected = {brand.casefold() for brand in preferences.rejected_brands}
    brand_allowed = phone.brand.casefold() not in rejected
    os_allowed = preferences.os_preference == "any" or phone.os == preferences.os_preference
    budget_allowed = phone.price_usd is not None and phone.price_usd <= preferences.budget_usd
    screen_allowed = not preferences.avoid_large_screen or phone.screen_size_in <= 6.3
    charging_allowed = not preferences.require_fast_charging or phone.charging_watt >= 45
    return brand_allowed and os_allowed and budget_allowed and screen_allowed and charging_allowed


def _build_weights(priorities: list[str]) -> dict[str, float]:
    weights = BASE_WEIGHTS.copy()
    for priority in priorities:
        if priority in weights:
            weights[priority] += 0.18
    total_weight = sum(weights.values())
    return {key: weight / total_weight for key, weight in weights.items()}


def _weighted_score(phone: PhoneCandidate, weights: dict[str, float]) -> float:
    return round(
        sum(getattr(phone, SCORE_FIELDS[key]) * weight for key, weight in weights.items()),
        2,
    )


def _build_reasons(phone: PhoneCandidate, preferences: UserPreferences) -> list[str]:
    reasons = [PRIORITY_REASON[priority] for priority in preferences.priorities if priority in PRIORITY_REASON]
    reasons.append(f"سعر السوق المتاح نحو ${phone.price_usd:.0f}")
    if phone.refresh_rate >= 120:
        reasons.append("معدل تحديث 120Hz")
    if phone.battery_mah >= 5000:
        reasons.append("بطارية 5000mAh أو أكثر")
    return reasons[:4]
