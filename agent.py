from llm.explainer import explain_recommendations
from schemas import UserPreferences
from services.recommendation_service import recommend_phones


def recommend_phone(preferences: UserPreferences) -> str:
    result = recommend_phones(preferences)
    return explain_recommendations(preferences, result)
