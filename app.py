import streamlit as st

from agent import recommend_phone
from schemas import UserPreferences


PRIORITY_OPTIONS = {
    "تصوير": "camera",
    "ألعاب": "gaming",
    "بطارية": "battery",
    "شاشة": "screen",
    "شغل ودراسة": "work_study",
    "سوشيال ميديا": "social_media",
    "حجم صغير": "compact",
    "تخزين كبير": "storage",
}


st.set_page_config(page_title="Phone AI Agent", page_icon="phone")
st.title("Phone AI Agent")
st.write("اختر هاتفًا مناسبًا حسب ميزانيتك وسوقك واستخدامك.")

with st.form("phone_preferences"):
    budget = st.number_input(
        "الميزانية بالدولار",
        min_value=50,
        max_value=3000,
        value=500,
        step=25,
    )
    country = st.text_input("البلد / السوق", value="Turkey")
    os_preference = st.selectbox(
        "النظام المفضل",
        ["any", "android", "ios"],
        format_func=lambda value: {
            "any": "لا يهم",
            "android": "Android",
            "ios": "iPhone",
        }[value],
    )
    selected_priority_labels = st.multiselect(
        "أهم الاستخدامات",
        list(PRIORITY_OPTIONS),
        default=["تصوير", "بطارية"],
    )
    rejected_brands = st.text_input(
        "ماركات لا تريدها",
        placeholder="مثال: Xiaomi, Apple",
    )
    avoid_large_screen = st.checkbox("لا أريد شاشة كبيرة")
    require_fast_charging = st.checkbox("أريد شحنًا سريعًا")
    submitted = st.form_submit_button("اقترح أفضل الهواتف")

if submitted:
    preferences = UserPreferences(
        budget_usd=float(budget),
        country=country.strip() or "Unknown",
        os_preference=os_preference,
        priorities=[PRIORITY_OPTIONS[label] for label in selected_priority_labels],
        rejected_brands=[
            brand.strip()
            for brand in rejected_brands.split(",")
            if brand.strip()
        ],
        avoid_large_screen=avoid_large_screen,
        require_fast_charging=require_fast_charging,
    )

    with st.spinner("جاري ترتيب الخيارات..."):
        st.markdown(recommend_phone(preferences))
