"""Wildberries (кабинет Berton + Samley): заказы, отмены (Statistics API), реклама (Promotion API).

Определения:
- Заказы — заказы, созданные за день (МСК), без отменённых. Сумма — priceWithDisc.
- Отмены — заказы дня с признаком isCancel.
- Реклама — списания за день (adv/v1/upd), общей суммой по кабинету.
- Бренд берётся из строки заказа (поле brand); если пусто — лист «Справочник».
Возвраты покупателей не собираем (по решению владельца).
Лог чистый: только статус HTTP.
"""
import time
from collections import defaultdict
from datetime import date

import requests

from ..config import secret
from .base import Row

STATS = "https://statistics-api.wildberries.ru"
ADV = "https://advert-api.wildberries.ru"
TIMEOUT = 90


class WBError(Exception):
    pass


def _get(url, params):
    h = {"Authorization": secret("WB_BS_TOKEN")}
    for attempt in range(4):
        r = requests.get(url, headers=h, params=params, timeout=TIMEOUT)
        if r.status_code == 429 and attempt < 3:
            time.sleep(70)  # лимиты WB: примерно 1 запрос в минуту
            continue
        if r.status_code != 200:
            raise WBError(f"HTTP {r.status_code} {url.split('wildberries.ru')[-1]}")
        return r.json()


def _num(x) -> float:
    try:
        return float(x)
    except (TypeError, ValueError):
        return 0.0


def collect(cabinet_key: str, day: date, reference: dict = None) -> list:
    reference = reference or {}
    d = day.isoformat()
    brand_of = lambda x: x.get("brand") or reference.get(x.get("supplierArticle"), "Не определён")

    orders = _get(f"{STATS}/api/v1/supplier/orders", {"dateFrom": d, "flag": 1})

    acc = defaultdict(float)
    for o in orders:
        if not str(o.get("date", "")).startswith(d):
            continue
        b = brand_of(o)
        kind = "cancels" if o.get("isCancel") else "orders"
        acc[(b, f"{kind}_qty")] += 1
        acc[(b, f"{kind}_rub")] += _num(o.get("priceWithDisc"))

    rows = [Row(day, cabinet_key, "wb", b, m, round(v, 2)) for (b, m), v in acc.items()]

    time.sleep(2)
    upd = _get(f"{ADV}/adv/v1/upd", {"from": d, "to": d})
    spend = sum(_num(u.get("updSum")) for u in upd if str(u.get("updTime", "")).startswith(d))
    rows.append(Row(day, cabinet_key, "wb", "", "ad_spend", round(spend, 2)))
    return rows
