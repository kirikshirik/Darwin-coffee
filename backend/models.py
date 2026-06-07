"""SQLAlchemy 2.0 модели «Дарвина».

Схема построена под реальные данные кофейни (см. backend/darwin_data.py):
выручка и чеки приходят из Эвотора, расходы и себестоимость ведутся вручную,
а ProfitCalculator превращает всё это в чистую прибыль.
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import List, Optional

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

MONEY = Numeric(12, 2)  # деньги храним как Decimal, без float-погрешностей


class Base(DeclarativeBase):
    pass


class ExpenseCategory(str, Enum):
    """Статьи расходов — ровно как в Excel владельца «Дарвина».

    COGS (себестоимость) добавлена отдельно: в Excel её НЕТ как столбца,
    она спрятана внутри «Прочее». Это ключевой пробел в учёте кофейни.
    """

    COGS = "Себестоимость (закупка товара)"
    RENT = "Аренда"
    UTILITIES = "Коммунальные"
    PAYROLL = "Затраты на персонал"
    TAXES = "Налоги"
    MARKETING = "Маркетинг и реклама"
    ACQUIRING = "Эквайринг и QR-комиссия банка"
    SOFTWARE = "ПО (CRM, ERP, ОФД)"
    COMMS_SECURITY = "Телефония, интернет, охрана"
    OTHER = "Прочее"
    DEPRECIATION = "Амортизация и ремонт оборудования"


class Business(Base):
    __tablename__ = "businesses"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    evotor_store_uuid: Mapped[Optional[str]] = mapped_column(
        String(100), unique=True, index=True, nullable=True
    )
    business_value: Mapped[Optional[Decimal]] = mapped_column(MONEY, nullable=True)
    equipment_value: Mapped[Optional[Decimal]] = mapped_column(MONEY, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    products: Mapped[List["Product"]] = relationship(
        back_populates="business", cascade="all, delete-orphan"
    )
    receipts: Mapped[List["Receipt"]] = relationship(
        back_populates="business", cascade="all, delete-orphan"
    )
    expenses: Mapped[List["Expense"]] = relationship(
        back_populates="business", cascade="all, delete-orphan"
    )


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True)
    business_id: Mapped[int] = mapped_column(ForeignKey("businesses.id"))
    evotor_uuid: Mapped[Optional[str]] = mapped_column(String(100), index=True, nullable=True)
    name: Mapped[str] = mapped_column(String(255))
    category: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    sell_price: Mapped[Decimal] = mapped_column(MONEY, default=0)
    # Себестоимость: Эвотор обычно не хранит -> ведём свой справочник (рецепты).
    cost_price: Mapped[Decimal] = mapped_column(MONEY, default=0)
    active: Mapped[bool] = mapped_column(Boolean, default=True)

    business: Mapped["Business"] = relationship(back_populates="products")


class Receipt(Base):
    __tablename__ = "receipts"

    id: Mapped[int] = mapped_column(primary_key=True)
    business_id: Mapped[int] = mapped_column(ForeignKey("businesses.id"))
    receipt_uuid: Mapped[Optional[str]] = mapped_column(
        String(100), unique=True, index=True, nullable=True
    )
    sold_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    total_sum: Mapped[Decimal] = mapped_column(MONEY)
    payment_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    business: Mapped["Business"] = relationship(back_populates="receipts")
    items: Mapped[List["ReceiptItem"]] = relationship(
        back_populates="receipt", cascade="all, delete-orphan"
    )


class ReceiptItem(Base):
    __tablename__ = "receipt_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    receipt_id: Mapped[int] = mapped_column(ForeignKey("receipts.id"))
    product_id: Mapped[Optional[int]] = mapped_column(ForeignKey("products.id"), nullable=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 3))
    price: Mapped[Decimal] = mapped_column(MONEY)
    revenue: Mapped[Decimal] = mapped_column(MONEY)
    cost: Mapped[Decimal] = mapped_column(MONEY, default=0)
    profit: Mapped[Decimal] = mapped_column(MONEY, default=0)

    receipt: Mapped["Receipt"] = relationship(back_populates="items")
    product: Mapped[Optional["Product"]] = relationship()


class Expense(Base):
    __tablename__ = "expenses"

    id: Mapped[int] = mapped_column(primary_key=True)
    business_id: Mapped[int] = mapped_column(ForeignKey("businesses.id"))
    period: Mapped[date] = mapped_column(Date, index=True)  # первое число месяца
    category: Mapped[ExpenseCategory] = mapped_column(SAEnum(ExpenseCategory))
    amount: Mapped[Decimal] = mapped_column(MONEY)
    comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    business: Mapped["Business"] = relationship(back_populates="expenses")


class DailyMetric(Base):
    """Готовые дневные агрегаты — то, что бот шлёт каждое утро."""

    __tablename__ = "daily_metrics"

    id: Mapped[int] = mapped_column(primary_key=True)
    business_id: Mapped[int] = mapped_column(ForeignKey("businesses.id"))
    metric_date: Mapped[date] = mapped_column(Date, index=True)
    revenue: Mapped[Decimal] = mapped_column(MONEY, default=0)
    cogs: Mapped[Decimal] = mapped_column(MONEY, default=0)
    gross_profit: Mapped[Decimal] = mapped_column(MONEY, default=0)
    operating_expenses: Mapped[Decimal] = mapped_column(MONEY, default=0)
    net_profit: Mapped[Decimal] = mapped_column(MONEY, default=0)
    avg_check: Mapped[Decimal] = mapped_column(MONEY, default=0)
    checks_count: Mapped[int] = mapped_column(Integer, default=0)
