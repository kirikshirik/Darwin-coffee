"""Демо: динамические тех-карты и управление потерями (без БД).

Запуск:
    .venv/bin/python -m backend.costing.demo

Что показывает:
  1. Динамическую себестоимость базовых позиций (считается из закупочных цен) и
     сверку с замороженным контролем Excel → расхождение раскладывается по
     компонентам (автоматически вскрывает Находку 3: округление зерна, спор по корице).
  2. Пересчёт фуд-коста при удорожании молока на 10% — каждая позиция обновляется сама.
  3. Управление потерями: оценка списаний (пролив на калибровке, скисшее молоко) в ₽
     и их доля в выручке/COGS — деньги, которых сейчас нет в P&L.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal as D, ROUND_HALF_UP

from backend.costing import ingredients as ing
from backend.costing import techcard as tc
from backend.costing import writeoffs as wo
from backend.costing.writeoffs import WriteOffReason
from backend.financial.profit_calculator import rub


def kop(value) -> str:
    s = f"{D(value).quantize(D('0.01'), rounding=ROUND_HALF_UP):,.2f}"
    return s.replace(",", " ").replace(".", ",") + " ₽"


def main() -> None:
    print("\n☕ Динамические тех-карты «Дарвина» (себестоимость из закупочных цен)\n")

    # --- 1. Динамический фуд-кост + сверка с замороженным контролем ---
    print("Себестоимость базовых позиций (считается на лету из прайса):")
    print(f"  {'Объём':<8}{'Динамич.':>12}{'Excel-контроль':>16}{'δ':>10}")
    print("  " + "-" * 46)
    all_match = True
    recs = []
    for vol in sorted(tc.BASE_CARDS):
        r = tc.reconcile(vol)
        recs.append(r)
        mark = "✅" if r.delta == 0 else "⚠️"
        print(f"  {str(vol) + ' мл':<8}{kop(r.dynamic):>12}{kop(r.documented):>16}"
              f"{(('+' if r.delta > 0 else '') + kop(r.delta)):>10} {mark}")
        if r.delta != 0:
            all_match = False
    if all_match:
        print("  => ✅ динамический расчёт совпал с контролем Excel")
    else:
        print("  => ⚠️ есть расхождение — раскладка по компонентам ниже (это Находка 3):")
        for r in recs:
            for cd in r.component_deltas:
                sign = "+" if cd["delta"] > 0 else "−"
                print(f"     {r.volume_ml} мл · {cd['ingredient']}: динамич. {kop(cd['dynamic'])} "
                      f"vs Excel {kop(cd['documented'])} ({sign}{kop(abs(cd['delta']))})")

    # --- 2. Пересчёт при удорожании молока на 10% ---
    print("\nДинамический пересчёт: молоко дорожает на 10% (94 → 103.40 ₽/л):")
    print(f"  {'Объём':<8}{'Было':>12}{'Стало':>12}{'Δ':>10}")
    print("  " + "-" * 42)
    for row in tc.recompute_on_price_change("молоко", D("10")):
        print(f"  {str(row['volume_ml']) + ' мл':<8}{kop(row['was']):>12}"
              f"{kop(row['now']):>12}{('+' + kop(row['delta'])):>10}")
    print("  (то же сработает для зерна, сахара и любого ингредиента из справочника)")

    # --- 2b. Допы: динамическая себестоимость + сверка с Excel ---
    print("\nДопы — себестоимость порции из закупки/фасовки (лист «Добавки»):")
    print(f"  {'Доп':<18}{'Динамич.':>12}{'Excel':>12}   {'δ / статус'}")
    print("  " + "-" * 62)
    for r in tc.reconcile_addons():
        if r["frozen"] is None:
            tail = "➕ " + r["status"]
            frozen_str = "—"
        elif r["delta"] == 0:
            tail, frozen_str = "✅ совпало", kop(r["frozen"])
        else:
            sign = "+" if r["delta"] > 0 else "−"
            tail = f"⚠️ {sign}{kop(abs(r['delta']))}"
            frozen_str = kop(r["frozen"])
        print(f"  {r['addon']:<18}{kop(r['dynamic']):>12}{frozen_str:>12}   {tail}")
    print("  ✔ матча: доза 3 г подтверждена владельцем → верно 6.47 ₽, в Excel стояло "
          "10.75 ₽ (завышение 4.28 ₽/порцию). Сливки/арахис в Excel не считались — движок добил.")

    # --- 3. Управление потерями (списание) ---
    print("\n🗑  Управление потерями (списание) — перевод потерь в деньги:")
    period = date(2026, 5, 1)
    losses = [
        wo.estimate_calibration(period, shots_per_day=D("4"), days=30),   # пролив на помоле
        wo.estimate_soured_milk(period, liters=D("8")),                   # скисшее молоко
        wo.WriteOff(period, "стакан_350", D("40"), WriteOffReason.BREAKAGE, "бой/брак упаковки"),
    ]
    for l in losses:
        print(f"  {l.reason.value:<38}{l.ingredient:<14}{kop(l.cost()):>12}")

    # доля в реальных майских цифрах (выручка 306 497 ₽, food cost 25 000 ₽)
    summary = wo.summarize(losses, revenue=D("306497"), cogs=D("25000"))
    print("  " + "-" * 64)
    print(f"  Итого потерь за месяц: {rub(summary.total)} "
          f"({summary.share_of_revenue_pct}% выручки, {summary.share_of_cogs_pct}% COGS)")
    print("  По причинам:")
    for reason, amount in summary.by_reason.items():
        print(f"     • {reason.value}: {kop(amount)}")
    print("\n  => эти деньги сейчас не видны в P&L; подняв их, показываем честную картину.")
    print("\n✅ Тех-карты и списания работают (динамический фуд-кост из закупочных цен).")


if __name__ == "__main__":
    main()
