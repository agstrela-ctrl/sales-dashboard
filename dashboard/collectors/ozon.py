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


def _postings_cursor(headers, path, since, to):
    """FBO v3 и FBS v4: страницы по 100 через cursor; ответ — {postings, has_next, cursor}
    (на случай старого формата читаем и из result)."""
    out, cursor = [], ""
    while True:
        body = {"filter": {"since": since, "to": to}, "limit": 100, "cursor": cursor}
        data = _post(f"{SELLER}{path}", headers, body)
        data = data["result"] if isinstance(data.get("result"), dict) else data
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

    fbo = _postings_cursor(headers, "/v3/posting/fbo/list", since, to)
    fbs = _postings_cursor(headers, "/v4/posting/fbs/list", since, to)
    n_fbo, n_fbs = len(fbo), len(fbs)
    postings = fbo + fbs
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
    # ВРЕМЕННАЯ диагностика (удалить после проверки): число отправлений по типам
    def _rng(vals):
        vals = sorted(v for v in vals if v) or [""]
        return f"{vals[0]} .. {vals[-1]}"
    rows += [
        Row(day, cabinet_key, "ozon", "", "debug_ret_status_moment",
            _rng([str((r.get("visual") or {}).get("change_moment") or "") for r in returns])),
        Row(day, cabinet_key, "ozon", "", "debug_ret_logistic_date",
            _rng([str((r.get("logistic") or {}).get("return_date") or "") for r in returns])),
        Row(day, cabinet_key, "ozon", "", "debug_ret_keys",
            ",".join(sorted(returns[0].keys())) if returns else ""),
    ]
    ts = sorted(str(x.get("created_at") or x.get("in_process_at") or "") for x in fbo) or [""]
    rows += [Row(day, cabinet_key, "ozon", "", "debug_fbo_first_created", ts[0]),
             Row(day, cabinet_key, "ozon", "", "debug_fbo_last_created", ts[-1]),
             Row(day, cabinet_key, "ozon", "", "debug_window_utc", f"{since} .. {to}"),
             Row(day, cabinet_key, "ozon", "", "debug_fbo_postings", n_fbo),
             Row(day, cabinet_key, "ozon", "", "debug_fbs_postings", n_fbs)]
    # Реклама Озона не делится по брендам — общей суммой по кабинету (бренд пустой).
    # Если ключей Performance API нет — рекламу пропускаем (остальное собирается).
    if secret(f"{p}_PERF_CLIENT_ID") and secret(f"{p}_PERF_SECRET"):
        rows.append(Row(day, cabinet_key, "ozon", "", "ad_spend", round(_ad_spend(cabinet_key, day), 2)))
    return rows
