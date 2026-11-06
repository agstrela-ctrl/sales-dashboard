"""Запись в Google Таблицу через служебный аккаунт. Шаг 2 плана."""
import json

import gspread
from google.oauth2.service_account import Credentials

from .config import secret

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
DATA_SHEET = "Данные"


def open_spreadsheet():
    creds = Credentials.from_service_account_info(
        json.loads(secret("GOOGLE_SA_JSON")), scopes=SCOPES)
    return gspread.authorize(creds).open_by_key(secret("SHEET_ID"))


def _iso(v):
    """Дата из таблицы (число-серийник или текст) → 'ГГГГ-ММ-ДД'."""
    if isinstance(v, (int, float)):
        from datetime import date, timedelta
        return (date(1899, 12, 30) + timedelta(days=int(v))).isoformat()
    return str(v)


def append_rows(rows: list) -> None:
    """Пишет строки в лист «Данные». Повторный запуск за тот же день заменяет старые строки
    (день + кабинет + площадка), а не дублирует их."""
    if not rows:
        return
    ws = open_spreadsheet().worksheet(DATA_SHEET)
    old = ws.get_all_values(value_render_option="UNFORMATTED_VALUE")
    header, body = old[:1], old[1:]
    replaced = {(r.day.isoformat(), r.cabinet, r.platform) for r in rows}
    kept = [[_iso(r[0])] + r[1:] for r in body
            if len(r) > 2 and (_iso(r[0]), r[1], r[2]) not in replaced]
    new = [r.as_list() for r in rows]
    merged = sorted(kept + new, key=lambda r: str(r[0]))  # по дате, порядок внутри дня сохраняется
    ws.clear()
    ws.update(values=header + merged, range_name="A1", value_input_option="RAW")


def read_reference() -> dict:
    """Лист «Справочник»: артикул → бренд."""
    ws = open_spreadsheet().worksheet("Справочник")
    return {r[0]: r[1] for r in ws.get_all_values()[1:] if len(r) > 1 and r[0]}
