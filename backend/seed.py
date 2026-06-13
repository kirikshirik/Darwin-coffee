"""Заполнение БД реальными данными «Дарвина».

Запуск:  .venv/bin/python -m backend.seed

`seed()` ДЕСТРУКТИВЕН (drop_all) — для ручного пересоздания схемы.
`ensure_seeded()` идемпотентен — безопасно вызывать на старте бота (в т.ч. на
свежей облачной БД вроде Neon): создаёт схему и засевает данные только если их ещё нет.
"""
from __future__ import annotations

from sqlalchemy import select

from backend.db import SessionLocal, engine
from backend.models import Base, Business, Expense
from backend import darwin_data


def _populate(session) -> int:
    """Создать бизнес «Дарвин» и его помесячные расходы. Возвращает business_id."""
    biz = Business(
        name=darwin_data.BUSINESS["name"],
        business_value=darwin_data.BUSINESS["business_value"],
        equipment_value=darwin_data.BUSINESS["equipment_value"],
    )
    session.add(biz)
    session.flush()  # получаем biz.id

    rows = 0
    for month in darwin_data.MONTHLY:
        for category, amount in month["expenses"].items():
            session.add(
                Expense(
                    business_id=biz.id,
                    period=month["period"],
                    category=category,
                    amount=amount,
                )
            )
            rows += 1
    session.commit()
    print(
        f"✓ Засеян бизнес «{biz.name}» (id={biz.id}): "
        f"{rows} строк расходов за {len(darwin_data.MONTHLY)} мес."
    )
    return biz.id


def seed() -> int:
    # Пересоздаёт схему с нуля. СТИРАЕТ данные. Схему помечаем head-ревизией Alembic,
    # чтобы последующий upgrade_to_head() был no-op, а не пытался создавать таблицы заново.
    from backend.migrations import stamp_head

    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    stamp_head()
    with SessionLocal() as session:
        return _populate(session)


def ensure_seeded() -> int:
    """Идемпотентно подготовить БД: довести схему миграциями и засеять, если пуста.

    Безопасно дергать на каждом старте (для облачного Postgres, где нет персистентного
    диска и схему надо накатывать при первом деплое). БД, созданные до Alembic,
    upgrade_to_head() сам помечает baseline-ревизией. Если бизнес уже есть —
    данные не трогаем и возвращаем его id.
    """
    from backend.migrations import upgrade_to_head

    upgrade_to_head()
    with SessionLocal() as session:
        existing = session.scalars(select(Business)).first()
        if existing is not None:
            return existing.id
        return _populate(session)


if __name__ == "__main__":
    seed()
