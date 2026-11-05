"""Яндекс.Маркет (кабинет Berton + Samley): заказы и отмены (Partner API).

Определения:
- Заказы — заказы, созданные за день (по дате создания), без отменённых и без тестовых.
- Сумма заказа = (оплата покупателем + субсидия Маркета) × количество по каждой позиции.
- Отмены — заказы дня в статусе CANCELLED.
- Бренд: лист «Справочник» (артикул → бренд); если нет — по слову Berton/Samley в названии
  или артикуле; иначе «Не определён».
- Реклама Маркета пока не собирается (берётся из отчётов по услугам, нужна проверка на кабинете).
Лог чистый: только статус HTTP.
"""
from collections import defaultdict
from datetime import date, timedelta

import requests

from ..config import secret
from .base import Row

BASE = "https://api.partner.market.yandex.ru"
TIMEOUT = 60
BRANDS = ("Berton", "Samley")


class YMError(Exception):
    pass


def _num(x) -> float:
    try:
        return float(x)
    except (TypeError, ValueError):
        return 0.0


def _brand(item, reference):
    offer = item.get("offerId", "")
    if offer in reference:
        return reference[offer]
    text = f"{item.get('offerName', '')} {offer}".lower()
    for b in BRANDS:
        if b.lower() in text:
            return b
    return "Не определён"


def _orders(day: date):
    url = f"{BASE}/v1/businesses/{secret('YM_BS_BUSINESS_ID')}/orders"
    headers = {"Api-Key": secret("YM_BS_API_KEY")}
    body = {"dates": {"creationDateFrom": day.isoformat(),
                      "creationDateTo": (day + timedelta(days=1)).isoformat()},
            "fake": False}
    campaign = secret("YM_BS_CAMPAIGN_ID")
    if campaign:
        body["campaignIds"] = [int(campaign)]
    out, token = [], None
    while True:
        params = {"limit": 50}
        if token:
            params["pageToken"] = token
        r = requests.post(url, headers=headers, params=params, json=body, timeout=TIMEOUT)
        if r.status_code != 200:
            try:
                msg = str(r.json().get("errors", [{}])[0].get("message", ""))[:150]
            except Exception:
                msg = ""
            raise YMError(f"HTTP {r.status_code} orders {msg}".strip())
        data = r.json()
        out += data.get("orders", [])
        token = (data.get("paging") or {}).get("nextPageToken")
        if not token:
            return out


def collect(cabinet_key: str, day: date, reference: dict = None) -> list:
    reference = reference or {}
    acc = defaultdict(float)
    for o in _orders(day):
        kind = "cancels" if o.get("status") == "CANCELLED" else "orders"
        for it in o.get("items", []):
            b, qty = _brand(it, reference), _num(it.get("count"))
            pr = it.get("prices") or {}
            unit = _num((pr.get("payment") or {}).get("value")) + _num((pr.get("subsidy") or {}).get("value"))
            acc[(b, f"{kind}_qty")] += qty
            acc[(b, f"{kind}_rub")] += unit * qty
    return [Row(day, cabinet_key, "yandex", b, m, round(v, 2)) for (b, m), v in acc.items()]
