"""Озон: заказы, отмены, возвраты (Seller API) и рекламные расходы (Performance API).

Правила:
- Лог чистый: ошибки сообщают только статус/тип, без тел ответов (там могут быть данные).
- «Заказы» — отправления, созданные за день (МСК). Отмены — отправления в статусе cancelled,
  созданные за день. Возвраты — по дате оформления возврата, а не по дате заказа.
- Бренд: для Meco фиксированный; для Berton + Samley — из атрибута «Бренд» (id 85) карточки,
  запасной вариант — лист «Справочник» (артикул → бренд).
"""
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import requests

from ..config import secret
from .base import Row

SELLER = "https://api-seller.ozon.ru"
PERF = "https://api-performance.ozon.ru"
MSK = ZoneInfo("Europe/Moscow")
BRAND_ATTR_ID = 85
TIMEOUT = 60

PREFIX = {"meco": "OZON_MECO", "berton_samley": "OZON_BS"}
FIXED_BRAND = {"meco": "Meco"}


class OzonError(Exception):
    pass


def _post(url, headers, body):
    r = requests.post(url, headers=headers, json=body, timeout=TIMEOUT)
    if r.status_code != 200:
        try:  # пояснение Озона об ошибке запроса (текст проверки полей, без данных)
            msg = str(r.json().get("message", ""))[:200]
        except Exception:
            msg = ""
        raise OzonError(f"HTTP {r.status_code} {url.split('ozon.ru')[-1]} {msg}".strip())
    return r.json()


def _bounds(day: date):
    start = datetime(day.year, day.month, day.day, tzinfo=MSK)
    end = start + timedelta(days=1) - timedelta(seconds=1)
    f = lambda d: d.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return f(start), f(end)


def _num(x) -> float:
    try:
        if isinstance(x, dict):
            x = x.get("amount", x.get("price", 0))
        return float(x)
    except (TypeError, ValueError):
        return 0.0


def _postings(headers, path, since, to, limit):
    """Постранично читает отправления FBO/FBS (лимит страницы зависит от метода)."""
    out, offset = [], 0
    while True:
        body = {"dir": "ASC", "filter": {"since": since, "to": to},
                "limit": limit, "offset": offset,
                "with": {"analytics_data": False, "financial_data": False}}
        data = _post(f"{SELLER}{path}", headers, body).get("result", {})
        batch = data if isinstance(data, list) else data.get("postings", [])
        out += batch
        if len(batch) < limit:
            return out
        offset += len(batch)


def _postings_v4(headers, since, to):
    """FBS: метод v4, страницы по 100 через cursor (v3 Озон отключил)."""
    out, cursor = [], ""
    while True:
        body = {"filter": {"since": since, "to": to}, "limit": 100, "cursor": cursor}
        data = _post(f"{SELLER}/v4/posting/fbs/list", headers, body)
        out += data.get("postings", [])
        new = data.get("cursor", "")
        if not data.get("has_next") or not new or new == cursor:
            return out
        cursor = new


def _returns(headers, since, to):
    out, last_id = [], 0
    while True:
        body = {"filter": {"visual_status_change_moment": {"time_from": since, "time_to": to}},
                "limit": 500, "last_id": last_id}
        data = _post(f"{SELLER}/v1/returns/list", headers, body)
        batch = data.get("returns", [])
        out += batch
        if not data.get("has_next") or not batch:
            return out
        last_id = batch[-1].get("id", 0)


def _brands(headers, offer_ids, reference):
    """offer_id → бренд: атрибут карточки, иначе справочник."""
    result, ids = {}, sorted(set(offer_ids))
    for i in range(0, len(ids), 500):
        chunk = ids[i:i + 500]
        body = {"filter": {"offer_id": chunk, "visibility": "ALL"}, "limit": 1000}
        for item in _post(f"{SELLER}/v4/product/info/attributes", headers, body).get("result", []):
            for a in item.get("attributes", []):
                if a.get("id") == BRAND_ATTR_ID and a.get("values"):
                    result[item.get("offer_id")] = a["values"][0].get("value", "")
    for oid in ids:
        if not result.get(oid):
            result[oid] = reference.get(oid, "Не определён")
    return result


def _ad_spend(cab_key, day):
    cid = secret(f"{PREFIX[cab_key]}_PERF_CLIENT_ID")
    sec = secret(f"{PREFIX[cab_key]}_PERF_SECRET")
    tok = requests.post(f"{PERF}/api/client/token", timeout=TIMEOUT, json={
        "client_id": cid, "client_secret": sec, "grant_type": "client_credentials"})
    if tok.status_code != 200:
        raise OzonError(f"HTTP {tok.status_code} perf token")
    h = {"Authorization": f"Bearer {tok.json()['access_token']}"}
    r = requests.get(f"{PERF}/api/client/statistics/daily/json", headers=h, timeout=TIMEOUT,
                     params={"dateFrom": day.isoformat(), "dateTo": day.isoformat()})
    if r.status_code != 200:
        raise OzonError(f"HTTP {r.status_code} perf daily")
    rows = r.json().get("rows", [])
    return sum(_num(x.get("moneySpent", 0)) for x in rows)


def collect(cabinet_key: str, day: date, reference: dict = None) -> list:
    reference = reference or {}
    p = PREFIX[cabinet_key]
    headers = {"Client-Id": secret(f"{p}_CLIENT_ID"), "Api-Key": secret(f"{p}_API_KEY")}
    since, to = _bounds(day)

    postings = _postings(headers, "/v3/posting/fbo/list", since, to, 100)
    postings += _postings_v4(headers, since, to)
    returns = _returns(headers, since, to)

    offers = [pr.get("offer_id") for po in postings for pr in po.get("products", [])]
    offers += [(r.get("product") or {}).get("offer_id") for r in returns]
    offers = [o for o in offers if o]
    fixed = FIXED_BRAND.get(cabinet_key)
    brand_of = (lambda o: fixed) if fixed else (lambda o, m=_brands(headers, offers, reference): m.get(o, "Не определён"))

    acc = defaultdict(float)  # (бренд, метрика) → значение
    for po in postings:
        cancelled = po.get("status") == "cancelled"
        for pr in po.get("products", []):
            b, qty = brand_of(pr.get("offer_id")), float(pr.get("quantity", 0))
            rub = _num(pr.get("price")) * qty
            if cancelled:
                acc[(b, "cancels_qty")] += qty
                acc[(b, "cancels_rub")] += rub
            else:
                acc[(b, "orders_qty")] += qty
                acc[(b, "orders_rub")] += rub
    for r in returns:
        pr = r.get("product") or {}
        b, qty = brand_of(pr.get("offer_id")), float(pr.get("quantity", 1) or 1)
        acc[(b, "returns_qty")] += qty
        acc[(b, "returns_rub")] += _num(pr.get("price")) * qty

    rows = [Row(day, cabinet_key, "ozon", b, m, round(v, 2)) for (b, m), v in acc.items()]
    # Реклама Озона не делится по брендам — общей суммой по кабинету (бренд пустой).
    # Если ключей Performance API нет — рекламу пропускаем (остальное собирается).
    if secret(f"{p}_PERF_CLIENT_ID") and secret(f"{p}_PERF_SECRET"):
        rows.append(Row(day, cabinet_key, "ozon", "", "ad_spend", round(_ad_spend(cabinet_key, day), 2)))
    return rows
