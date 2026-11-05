"""Точка входа. В лог выводим ТОЛЬКО статусы и тексты ошибок — никаких сумм, штук, артикулов."""
import sys
from datetime import date, timedelta
from zoneinfo import ZoneInfo
from datetime import datetime

from dashboard.config import CABINETS
from dashboard.collectors import ozon, wb, yandex
from dashboard import sheets

COLLECTORS = {"ozon": ozon, "wb": wb, "yandex": yandex}


def yesterday_msk() -> date:
    return (datetime.now(ZoneInfo("Europe/Moscow")) - timedelta(days=1)).date()


def main() -> int:
    day = yesterday_msk()
    try:
        reference = sheets.read_reference()
    except Exception:
        reference = {}
    rows, done, failed = [], 0, 0
    for cab in CABINETS:
        try:
            for platform in cab.platforms:
                rows += COLLECTORS[platform].collect(cab.key, day, reference)
            done += 1
        except Exception as e:  # текст ошибки без данных
            failed += 1
            print(f"Ошибка в кабинете {cab.key}: {type(e).__name__}")
    try:
        sheets.append_rows(rows)
    except Exception as e:
        print(f"Ошибка записи в таблицу: {type(e).__name__}")
        return 1
    print(f"Готово. Кабинетов обработано: {done}, с ошибкой: {failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
