from backend.db import SessionLocal
from backend.models import Receipt
from sqlalchemy import select, func
from datetime import date, timedelta, datetime

with SessionLocal() as s:
    count = s.scalar(select(func.count(Receipt.id)))
    max_d = s.scalar(select(func.max(Receipt.sold_at)))
    min_d = s.scalar(select(func.min(Receipt.sold_at)))
    print(f"Total receipts: {count}")
    print(f"Min date: {min_d}")
    print(f"Max date: {max_d}")
