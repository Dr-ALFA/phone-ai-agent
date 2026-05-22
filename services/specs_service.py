import re
from dataclasses import dataclass

import requests
from bs4 import BeautifulSoup

from schemas import PhoneCandidate
from services.cache_service import get_cached_payload, set_cached_payload
from services.spec_discovery_service import discover_official_spec_sources


@dataclass(frozen=True)
class OfficialSpecSource:
    brand: str
    model: str
    os: str
    source_url: str
    page_parser: str


OFFICIAL_SPEC_SOURCES = [
    OfficialSpecSource(
        brand="Samsung",
        model="Galaxy A55",
        os="android",
        source_url="https://www.samsung.com/uk/smartphones/galaxy-a/galaxy-a55-5g-awesome-navy-256gb-sm-a556bzkceub/",
        page_parser="samsung_a55",
    ),
    OfficialSpecSource(
        brand="Google",
        model="Pixel 8a",
        os="android",
        source_url="https://support.google.com/pixelphone/answer/7158570?hl=en",
        page_parser="pixel_8a",
    ),
    OfficialSpecSource(
        brand="Xiaomi",
        model="Redmi Note 13 Pro",
        os="android",
        source_url="https://www.mi.com/es/product/redmi-note-13-pro/specs/",
        page_parser="redmi_note_13_pro",
    ),
    OfficialSpecSource(
        brand="Apple",
        model="iPhone 15",
        os="ios",
        source_url="https://support.apple.com/en-mt/111831",
        page_parser="iphone_15",
    ),
    OfficialSpecSource(
        brand="Apple",
        model="iPhone 16",
        os="ios",
        source_url="https://support.apple.com/en-asia/121029",
        page_parser="iphone_generic",
    ),
    OfficialSpecSource(
        brand="OnePlus",
        model="12R",
        os="android",
        source_url="https://www.oneplus.com/us/12r/specs",
        page_parser="oneplus_12r",
    ),
    OfficialSpecSource(
        brand="OnePlus",
        model="Nord 4",
        os="android",
        source_url="https://www.oneplus.com/es/nord-4/specs",
        page_parser="oneplus_generic",
    ),
]


def collect_official_specs() -> tuple[list[PhoneCandidate], str]:
    phones: list[PhoneCandidate] = []
    fresh_count = 0
    cached_count = 0

    discovered_sources, discovery_note = discover_official_spec_sources()
    all_sources = _unique_sources([*OFFICIAL_SPEC_SOURCES, *discovered_sources])

    for source in all_sources:
        payload, origin = _load_source_payload(source)
        if payload is None:
            continue
        candidate = _candidate_from_payload(source, payload)
        if candidate is None:
            continue
        phones.append(candidate)
        if origin == "fresh":
            fresh_count += 1
        if origin == "cache":
            cached_count += 1

    if fresh_count:
        return phones, f"Official specs fetched for {fresh_count} phone pages. {discovery_note}"
    if cached_count:
        return phones, f"Official specs loaded from Neon cache. {discovery_note}"
    return [], f"Official specs are unavailable right now. {discovery_note}"


def _load_source_payload(source: OfficialSpecSource) -> tuple[dict | None, str]:
    query_key = f"official-specs:{source.brand.casefold()}:{source.model.casefold()}"
    cached_payload = get_cached_payload(query_key)
    if cached_payload is not None:
        return cached_payload, "cache"

    try:
        response = requests.get(
            source.source_url,
            headers={"User-Agent": "PhoneAIAgent/0.1"},
            timeout=15,
        )
        response.raise_for_status()
    except requests.RequestException:
        return None, "failed"

    text = BeautifulSoup(response.text, "html.parser").get_text(" ", strip=True)
    payload = {"text": text, "source_url": source.source_url}
    set_cached_payload(query_key, payload, source="official_specs")
    return payload, "fresh"


def _candidate_from_payload(
    source: OfficialSpecSource,
    payload: dict,
) -> PhoneCandidate | None:
    text = payload.get("text", "")
    parser = {
        "samsung_a55": _parse_samsung_a55,
        "pixel_8a": _parse_pixel_8a,
        "redmi_note_13_pro": _parse_redmi_note_13_pro,
        "iphone_15": _parse_iphone_15,
        "iphone_generic": _parse_iphone_generic,
        "oneplus_12r": _parse_oneplus_12r,
        "oneplus_generic": _parse_oneplus_generic,
    }[source.page_parser]
    specs = parser(text)
    if specs is None:
        return None
    scores = _derive_scores(specs, text)
    return PhoneCandidate(
        brand=source.brand,
        model=source.model,
        price_usd=None,
        country="any",
        os=source.os,
        chipset=specs["chipset"],
        ram_gb=specs["ram_gb"],
        storage_gb=specs["storage_gb"],
        battery_mah=specs["battery_mah"],
        charging_watt=specs["charging_watt"],
        screen_type=specs["screen_type"],
        refresh_rate=specs["refresh_rate"],
        screen_size_in=specs["screen_size_in"],
        weaknesses=_derive_weaknesses(specs),
        source_url=source.source_url,
        **scores,
    )


def _parse_pixel_8a(text: str) -> dict | None:
    section = _between(text, "Pixel 8a phone (2024)", "Pixel Fold")
    return _build_specs(
        section,
        chipset="Google Tensor G3",
        screen_type="OLED",
        refresh_rate=_number(section, r"up to\s+(\d+)\s*Hz", 120),
        screen_size_in=_number(section, r"(\d\.\d)-inch Actua", 6.1),
        ram_gb=_number(section, r"(\d+)\s*GB LPDDR5x RAM", 8),
        storage_gb=_largest_number(section, r"((?:128|256))\s*GB", 256),
        battery_mah=_number(section, r"Typical\s+(\d+)\s*mAh", 4492),
        charging_watt=18,
    )


def _parse_oneplus_12r(text: str) -> dict | None:
    return _build_specs(
        text,
        chipset="Snapdragon 8 Gen 2",
        screen_type="AMOLED",
        refresh_rate=_number(text, r"Refresh Rate:\s*1-(\d+)\s*Hz", 120),
        screen_size_in=_number(text, r"(\d\.\d+)\"", 6.78),
        ram_gb=_largest_number(text, r"(\d+)GB LPDDR5X", 16),
        storage_gb=_largest_number(text, r"(\d+)GB UFS", 256),
        battery_mah=_number(text, r"Battery:\s*([\d,]+)\s*mAh", 5500),
        charging_watt=_number(text, r"(\d+)W SUPERVOOC", 80),
    )


def _parse_oneplus_generic(text: str) -> dict | None:
    return _build_specs(
        text,
        chipset=_chipset_name(text, "Snapdragon 7 Plus Gen 3"),
        screen_type="AMOLED",
        refresh_rate=_number(text, r"(?:Refresh Rate|Frecuencia de actualización):?\s*(?:up to|hasta)?\s*(\d+)\s*Hz", 120),
        screen_size_in=_number(text, r"(\d\.\d+)\"", 6.74),
        ram_gb=_largest_number(text, r"(\d+)GB(?:/\d+GB)? LPDDR", 12),
        storage_gb=_largest_number(text, r"(\d+)GB(?:\s*/\s*\d+GB)? UFS", 256),
        battery_mah=_number(text, r"(?:Battery|Batería):?\s*([\d.,]+)\s*mAh", 5500),
        charging_watt=_number(text, r"(\d+)W SUPERVOOC", 100),
    )


def _parse_redmi_note_13_pro(text: str) -> dict | None:
    return _build_specs(
        text,
        chipset="Snapdragon 7s Gen 2",
        screen_type="AMOLED",
        refresh_rate=_bounded_refresh_rate(_number(text, r"(\d+)\s*Hz", 120)),
        screen_size_in=_number(text, r"(\d\.\d+)\"", 6.67),
        ram_gb=_largest_number(text, r"(\d+)\s*GB RAM", 12),
        storage_gb=_largest_number(text, r"(\d+)\s*GB", 512),
        battery_mah=_number(text, r"([\d,]+)\s*mAh", 5100),
        charging_watt=_number(text, r"(\d+)\s*W", 67),
    )


def _parse_iphone_15(text: str) -> dict | None:
    return _build_specs(
        text,
        chipset="A16 Bionic",
        screen_type="OLED",
        refresh_rate=60,
        screen_size_in=_number(text, r"(\d\.\d)-inch.*OLED", 6.1),
        ram_gb=6,
        storage_gb=_largest_number(text, r"(\d+)\s*GB", 512),
        battery_mah=3349,
        charging_watt=20,
    )


def _parse_iphone_generic(text: str) -> dict | None:
    is_iphone_16 = "a18 chip" in text.casefold()
    return _build_specs(
        text,
        chipset="A18" if is_iphone_16 else "Apple A-series",
        screen_type="OLED",
        refresh_rate=60,
        screen_size_in=_number(text, r"(\d\.\d).{0,20}inch.*OLED", 6.1),
        ram_gb=8 if is_iphone_16 else 6,
        storage_gb=_largest_number(text, r"(\d+)\s*GB", 512),
        battery_mah=3561 if is_iphone_16 else 3349,
        charging_watt=20,
    )


def _parse_samsung_a55(text: str) -> dict | None:
    return _build_specs(
        text,
        chipset="Exynos 1480",
        screen_type="Super AMOLED",
        refresh_rate=_number(text, r"(\d+)\s*Hz", 120),
        screen_size_in=_number(text, r"(\d\.\d)\".*display", 6.6),
        ram_gb=_largest_number(text, r"(\d+)\s*GB RAM", 8),
        storage_gb=_largest_number(text, r"(\d+)\s*GB", 256),
        battery_mah=_number(text, r"([\d,]+)\s*mAh", 5000),
        charging_watt=_number(text, r"(\d+)\s*W", 25),
    )


def _build_specs(text: str, **specs) -> dict | None:
    if not text.strip():
        return None
    return specs


def _bounded_refresh_rate(refresh_rate: int) -> int:
    return refresh_rate if 60 <= refresh_rate <= 240 else 120


def _derive_scores(specs: dict, text: str) -> dict[str, int]:
    text_folded = text.casefold()
    gaming = _chipset_score(specs["chipset"])
    camera = 68
    if "ois" in text_folded or "optical image stabilization" in text_folded:
        camera += 10
    if "48" in text_folded or "50" in text_folded:
        camera += 5
    if "pixel" in text_folded or "photonic engine" in text_folded:
        camera += 8
    battery = min(96, 45 + specs["battery_mah"] // 100 + min(specs["charging_watt"], 80) // 4)
    screen = min(96, 58 + specs["refresh_rate"] // 5 + (8 if "oled" in specs["screen_type"].casefold() else 0))
    storage = min(96, 50 + specs["storage_gb"] // 8)
    work = min(96, gaming - 4 + specs["ram_gb"] * 2)
    social = min(96, round((camera + screen) / 2))
    compact = max(20, round(130 - specs["screen_size_in"] * 13))
    value = min(96, max(55, round((gaming + battery + screen + camera) / 4)))
    return {
        "camera_score": camera,
        "gaming_score": gaming,
        "battery_score": battery,
        "screen_score": screen,
        "work_score": work,
        "social_score": social,
        "compact_score": compact,
        "storage_score": storage,
        "value_score": value,
    }


def _derive_weaknesses(specs: dict) -> list[str]:
    weaknesses = []
    if specs["charging_watt"] < 30:
        weaknesses.append("الشحن ليس سريعًا مقارنة ببعض المنافسين")
    if specs["refresh_rate"] < 120:
        weaknesses.append("الشاشة أقل سلاسة من خيارات 120Hz")
    if specs["screen_size_in"] > 6.5:
        weaknesses.append("الحجم كبير لمن يريد هاتفًا صغيرًا")
    if specs["storage_gb"] <= 128:
        weaknesses.append("نسخة التخزين الأساسية قد تضيق مع الصور والفيديو")
    return weaknesses or ["لا توجد نقطة ضعف واضحة من المواصفات الأساسية فقط"]


def _chipset_score(chipset: str) -> int:
    tiers = {
        "snapdragon 8 gen 2": 95,
        "a16 bionic": 92,
        "a18": 95,
        "google tensor g3": 84,
        "exynos 1480": 76,
        "snapdragon 7s gen 2": 74,
        "snapdragon 7 plus gen 3": 86,
    }
    return tiers.get(chipset.casefold(), 70)


def _number(text: str, pattern: str, fallback: float | int):
    match = re.search(pattern, text, flags=re.IGNORECASE)
    if match is None:
        return fallback
    value = match.group(1).replace(",", "")
    return float(value) if "." in value else int(value)


def _largest_number(text: str, pattern: str, fallback: int) -> int:
    values = [int(value) for value in re.findall(pattern, text, flags=re.IGNORECASE)]
    return max(values) if values else fallback


def _between(text: str, start: str, end: str) -> str:
    if start not in text:
        return text
    remainder = text.split(start, maxsplit=1)[1]
    return remainder.split(end, maxsplit=1)[0] if end in remainder else remainder


def _unique_sources(sources) -> list[OfficialSpecSource]:
    unique_sources = {}
    for source in sources:
        unique_sources.setdefault((source.brand, source.model), source)
    return list(unique_sources.values())


def _chipset_name(text: str, fallback: str) -> str:
    match = re.search(r"(Snapdragon[^.]{0,40}?(?:Gen\s*\d|Mobile Platform))", text, re.IGNORECASE)
    if match is None:
        return fallback
    normalized = match.group(1).encode("ascii", "ignore").decode().strip()
    return normalized or fallback
