"""Заполнение БД реальными данными «Дарвина».

Запуск:  .venv/bin/python -m backend.seed
"""
from __future__ import annotations

from backend.db import SessionLocal, engine
from backend.models import Base, Business, Expense
from backend import darwin_data


def seed() -> int:
    # Для MVP пересоздаём схему с нуля (на проде — Alembic-миграции).
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)

    with SessionLocal() as session:
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


if __name__ == "__main__":
    seed()
