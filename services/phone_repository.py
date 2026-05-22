from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from config import CACHE_TTL_HOURS
from db import create_tables, get_session_factory
from models import Phone, PhonePrice
from schemas import PhoneCandidate, PriceObservation


def save_official_specs(phones: list[PhoneCandidate]) -> None:
    session_factory = _ready_session_factory()
    if session_factory is None:
        return

    with session_factory() as session:
        for candidate in phones:
            phone = _get_phone(session, candidate.brand, candidate.model)
            if phone is None:
                phone = Phone(brand=candidate.brand, model=candidate.model)
                session.add(phone)
            phone.os = candidate.os
            phone.chipset = candidate.chipset
            phone.ram_gb = candidate.ram_gb
            phone.storage_gb = candidate.storage_gb
            phone.battery_mah = candidate.battery_mah
            phone.charging_watt = candidate.charging_watt
            phone.screen_type = candidate.screen_type
            phone.refresh_rate = candidate.refresh_rate
            phone.camera_score = candidate.camera_score
            phone.gaming_score = candidate.gaming_score
            phone.battery_score = candidate.battery_score
            phone.value_score = candidate.value_score
            phone.source_url = candidate.source_url
        session.commit()


def save_price_observations(
    country: str,
    observations: list[PriceObservation],
) -> None:
    session_factory = _ready_session_factory()
    if session_factory is None:
        return

    with session_factory() as session:
        for observation in observations:
            brand, model = _split_phone_name(observation.phone_name)
            phone = _get_phone(session, brand, model)
            if phone is None:
                continue
            session.add(
                PhonePrice(
                    phone=phone,
                    country=country,
                    store=observation.store,
                    price=observation.price,
                    currency=observation.currency,
                    price_usd=observation.price_usd,
                    product_url=observation.product_url,
                )
            )
        session.commit()


def load_fresh_market_prices(
    country: str,
    phones: list[PhoneCandidate],
) -> dict[str, float]:
    session_factory = _ready_session_factory()
    if session_factory is None:
        return {}

    cutoff = datetime.now(timezone.utc) - timedelta(hours=CACHE_TTL_HOURS)
    names = {(phone.brand, phone.model) for phone in phones}
    prices: dict[str, float] = {}
    with session_factory() as session:
        statement = (
            select(Phone, PhonePrice)
            .join(PhonePrice)
            .where(PhonePrice.country == country)
            .where(PhonePrice.scraped_at >= cutoff)
            .where(PhonePrice.price_usd.is_not(None))
        )
        for phone, price in session.execute(statement):
            if (phone.brand, phone.model) not in names:
                continue
            key = f"{phone.brand} {phone.model}"
            observed_price = float(price.price_usd)
            prices[key] = min(prices.get(key, observed_price), observed_price)
    return prices


def _get_phone(session, brand: str, model: str):
    return session.scalar(
        select(Phone).where(Phone.brand == brand).where(Phone.model == model)
    )


def _ready_session_factory():
    session_factory = get_session_factory()
    if session_factory is None:
        return None
    create_tables()
    return session_factory


def _split_phone_name(phone_name: str) -> tuple[str, str]:
    brand, model = phone_name.split(" ", maxsplit=1)
    return brand, model
