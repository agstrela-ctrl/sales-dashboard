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


def append_rows(rows: list) -> None:
    """Дописывает строки в лист «Данные»."""
    if not rows:
        return
    ws = open_spreadsheet().worksheet(DATA_SHEET)
    ws.append_rows([r.as_list() for r in rows], value_input_option="USER_ENTERED")


def read_reference() -> dict:
    """Лист «Справочник»: артикул → бренд."""
    ws = open_spreadsheet().worksheet("Справочник")
    return {r[0]: r[1] for r in ws.get_all_values()[1:] if len(r) > 1 and r[0]}
