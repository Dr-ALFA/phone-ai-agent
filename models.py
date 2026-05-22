from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db import Base


class Phone(Base):
    __tablename__ = "phones"

    id: Mapped[int] = mapped_column(primary_key=True)
    brand: Mapped[str] = mapped_column(Text)
    model: Mapped[str] = mapped_column(Text)
    os: Mapped[str] = mapped_column(String(20))
    chipset: Mapped[str | None] = mapped_column(Text)
    ram_gb: Mapped[int | None] = mapped_column(Integer)
    storage_gb: Mapped[int | None] = mapped_column(Integer)
    battery_mah: Mapped[int | None] = mapped_column(Integer)
    charging_watt: Mapped[int | None] = mapped_column(Integer)
    screen_type: Mapped[str | None] = mapped_column(Text)
    refresh_rate: Mapped[int | None] = mapped_column(Integer)
    camera_score: Mapped[int | None] = mapped_column(Integer)
    gaming_score: Mapped[int | None] = mapped_column(Integer)
    battery_score: Mapped[int | None] = mapped_column(Integer)
    value_score: Mapped[int | None] = mapped_column(Integer)
    source_url: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    prices: Mapped[list["PhonePrice"]] = relationship(back_populates="phone")


class PhonePrice(Base):
    __tablename__ = "phone_prices"

    id: Mapped[int] = mapped_column(primary_key=True)
    phone_id: Mapped[int] = mapped_column(ForeignKey("phones.id"))
    country: Mapped[str] = mapped_column(Text)
    store: Mapped[str | None] = mapped_column(Text)
    price: Mapped[float] = mapped_column(Numeric(10, 2))
    currency: Mapped[str] = mapped_column(String(12))
    price_usd: Mapped[float | None] = mapped_column(Numeric(10, 2))
    product_url: Mapped[str | None] = mapped_column(Text)
    scraped_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    phone: Mapped[Phone] = relationship(back_populates="prices")


class SearchCache(Base):
    __tablename__ = "search_cache"

    id: Mapped[int] = mapped_column(primary_key=True)
    query_key: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    payload_json: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
