"""Загрузка истории за период. Запуск: python backfill.py ГГГГ-ММ-ДД ГГГГ-ММ-ДД [площадки через запятую]
Площадки по умолчанию: ozon,yandex (WB — осторожно из-за лимитов). В лог — только счётчики."""
import sys
from datetime import date, timedelta

from dashboard import sheets
from dashboard.config import CABINETS
from dashboard.collectors import ozon, wb, yandex

COLLECTORS = {"ozon": ozon, "wb": wb, "yandex": yandex}


def main() -> int:
    start, end = date.fromisoformat(sys.argv[1]), date.fromisoformat(sys.argv[2])
    wanted = (sys.argv[3] if len(sys.argv) > 3 else "ozon,yandex").split(",")
    try:
        reference = sheets.read_reference()
    except Exception:
        reference = {}
    rows, days, failed = [], 0, 0
    day = start
    while day <= end:
        for cab in CABINETS:
            for platform in cab.platforms:
                if platform not in wanted:
                    continue
                try:
                    rows += COLLECTORS[platform].collect(cab.key, day, reference)
                except Exception as e:
                    failed += 1
                    print(f"Ошибка {cab.key}/{platform}: {e if hasattr(e, 'args') and type(e).__name__.endswith('Error') and type(e).__name__ in ('OzonError', 'WBError', 'YMError') else type(e).__name__}")
        days += 1
        day += timedelta(days=1)
    try:
        sheets.append_rows(rows)
    except Exception as e:
        print(f"Ошибка записи в таблицу: {type(e).__name__}")
        return 1
    print(f"Готово. Дней обработано: {days}, ошибок: {failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
