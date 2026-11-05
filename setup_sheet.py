"""Одноразовая подготовка таблицы: создаёт листы «Дашборд», «Данные», «Справочник» с заголовками.
Безопасно запускать повторно — существующие листы не трогает.
Запуск: из GitHub Actions (workflow «Подготовка таблицы») или локально с теми же переменными окружения."""
import sys

from dashboard.sheets import open_spreadsheet
from dashboard import layout

SHEETS = {
    "Дашборд": None,
    "Данные": ["Дата", "Кабинет", "Площадка", "Бренд", "Метрика", "Значение"],
    "Справочник": ["Артикул", "Бренд"],
}


def main() -> int:
    try:
        sp = open_spreadsheet()
        existing = {ws.title for ws in sp.worksheets()}
        for title, header in SHEETS.items():
            if title in existing:
                continue
            ws = sp.add_worksheet(title=title, rows=1000, cols=12)
            if header:
                ws.append_row(header)
                ws.freeze(rows=1)
        data = sp.worksheet("Данные")  # убрать остатки временной диагностики
        allv = data.get_all_values(value_render_option="UNFORMATTED_VALUE")
        clean = [r for r in allv if not (len(r) > 4 and str(r[4]).startswith("debug_"))]
        if len(clean) != len(allv):
            data.clear()
            data.update(values=clean, range_name="A1", value_input_option="RAW")
        layout.apply(sp.worksheet("Дашборд"))
    except Exception as e:
        print(f"Ошибка: {type(e).__name__}")
        return 1
    print("Готово: таблица подготовлена")
    return 0


if __name__ == "__main__":
    sys.exit(main())
