from dataclasses import dataclass, field


@dataclass
class UserPreferences:
    budget_usd: float
    country: str
    os_preference: str = "any"
    priorities: list[str] = field(default_factory=list)
    rejected_brands: list[str] = field(default_factory=list)
    avoid_large_screen: bool = False
    require_fast_charging: bool = False


@dataclass
class PhoneCandidate:
    brand: str
    model: str
    price_usd: float | None
    country: str
    os: str
    chipset: str
    ram_gb: int
    storage_gb: int
    battery_mah: int
    charging_watt: int
    screen_type: str
    refresh_rate: int
    screen_size_in: float
    camera_score: int
    gaming_score: int
    battery_score: int
    screen_score: int
    work_score: int
    social_score: int
    compact_score: int
    storage_score: int
    value_score: int
    weaknesses: list[str]
    source_url: str = ""


@dataclass
class ScoredPhone:
    phone: PhoneCandidate
    score: float
    reasons: list[str]


@dataclass
class PriceObservation:
    phone_name: str
    title: str
    price: float
    currency: str
    price_usd: float | None
    store: str
    product_url: str


@dataclass
class RecommendationResult:
    phones: list[ScoredPhone]
    data_note: str
    price_observations: list[PriceObservation] = field(default_factory=list)
