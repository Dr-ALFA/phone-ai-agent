from langchain_openai import ChatOpenAI

from config import OPENAI_API_KEY, OPENAI_MODEL
from schemas import RecommendationResult, ScoredPhone, UserPreferences


def explain_recommendations(
    preferences: UserPreferences,
    result: RecommendationResult,
) -> str:
    recommendations = result.phones
    if not recommendations:
        return _empty_result(preferences, result.data_note)
    if not OPENAI_API_KEY:
        return _fallback_explanation(preferences, result)

    llm = ChatOpenAI(
        model=OPENAI_MODEL,
        temperature=0.2,
        api_key=OPENAI_API_KEY,
    )
    try:
        response = llm.invoke(_build_prompt(preferences, result))
    except Exception:
        return _fallback_explanation(preferences, result)
    return response.content


def _build_prompt(preferences: UserPreferences, result: RecommendationResult) -> str:
    recommendations = result.phones
    ranked_phones = "\n".join(
        (
            f"{index}. {item.phone.brand} {item.phone.model}; "
            f"price_usd={item.phone.price_usd}; score={item.score}; "
            f"reasons={item.reasons}; weaknesses={item.phone.weaknesses}; "
            f"specs=RAM {item.phone.ram_gb}GB, storage {item.phone.storage_gb}GB, "
            f"battery {item.phone.battery_mah}mAh, charging {item.phone.charging_watt}W, "
            f"screen {item.phone.screen_type} {item.phone.refresh_rate}Hz, "
            f"chipset {item.phone.chipset}"
        )
        for index, item in enumerate(recommendations, start=1)
    )
    return f"""
أنت تشرح توصيات هواتف مبنية على فلترة وحساب نقاط من النظام.
لا تضف هاتفًا غير موجود في القائمة ولا تخترع سعرًا أو مواصفة.

تفضيلات المستخدم:
- الميزانية: {preferences.budget_usd} USD
- السوق: {preferences.country}
- النظام: {preferences.os_preference}
- الأولويات: {preferences.priorities}
- الماركات المستبعدة: {preferences.rejected_brands}
- ملاحظة البيانات: {result.data_note}

النتائج المرتبة:
{ranked_phones}

اكتب بالعربية:
1. ملخص قصير حسب الميزانية والاستخدام.
2. أفضل 3 خيارات مرتبة حسب الأفضل للميزانية.
3. سبب اختيار كل جهاز.
4. نقاط الضعف.
5. المواصفات التي ينبغي ألا ينزل عنها المستخدم.
"""


def _fallback_explanation(
    preferences: UserPreferences,
    result: RecommendationResult,
) -> str:
    recommendations = result.phones
    lines = [
        f"حسب ميزانيتك ${preferences.budget_usd:.0f} وأولوياتك الحالية، هذه أفضل الخيارات من المواصفات المتاحة:",
        f"**حالة البيانات:** {result.data_note}",
        "",
    ]
    for index, item in enumerate(recommendations, start=1):
        phone = item.phone
        lines.extend(
            [
                f"## {index}. {phone.brand} {phone.model}",
                f"**السعر التقريبي:** ${phone.price_usd:.0f}",
                f"**درجة الملاءمة:** {item.score}",
                "**السبب:**",
                *[f"- {reason}" for reason in item.reasons],
                "**نقاط الضعف:**",
                *[f"- {weakness}" for weakness in phone.weaknesses],
                (
                    f"**المواصفات المهمة:** {phone.chipset}, "
                    f"{phone.ram_gb}GB RAM, {phone.storage_gb}GB storage, "
                    f"{phone.battery_mah}mAh, {phone.charging_watt}W, "
                    f"{phone.screen_type} {phone.refresh_rate}Hz"
                ),
                "",
            ]
        )
    lines.extend(
        [
            "## الحد الأدنى المقترح للمواصفات",
            "- 8GB RAM للاستخدام المتوازن.",
            "- 128GB تخزين على الأقل، و256GB إذا كان التصوير أو الملفات مهمًا.",
            "- شاشة OLED أو AMOLED مع 120Hz إذا كانت الشاشة أولوية.",
            "- بطارية قريبة من 5000mAh إذا كانت البطارية أولوية.",
        ]
    )
    if result.price_observations:
        lines.extend(
            [
                "",
                "## ملاحظات أسعار السوق",
                "هذه الأسعار تدخل في فلترة الميزانية بعد تحويل العملة إلى الدولار عند توفر سعر صرف.",
            ]
        )
        for observation in result.price_observations[:5]:
            lines.append(
                f"- {observation.phone_name}: {observation.price:.0f} {observation.currency} "
                f"من {observation.store}"
            )
    return "\n".join(lines)


def _empty_result(preferences: UserPreferences, data_note: str) -> str:
    return (
        f"لم أجد هاتفًا بسعر سوق حقيقي ضمن ميزانيتك ${preferences.budget_usd:.0f}. "
        f"حالة البيانات: {data_note} "
        "أضف مزود أسعار جديد أو تأكد من وجود أسعار حديثة في Neon لهذا السوق."
    )
