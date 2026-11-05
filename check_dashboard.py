"""Диагностика листа «Дашборд»: печатает только типы ошибок и адреса ячеек, без значений."""
import collections
from dashboard.sheets import open_spreadsheet

ws = open_spreadsheet().worksheet("Дашборд")
vals = ws.get_all_values()
errs = collections.Counter()
first = {}
for i, row in enumerate(vals, 1):
    for j, v in enumerate(row, 1):
        if v.startswith("#") or v.startswith("Err:"):
            errs[v] += 1
            first.setdefault(v, f"R{i}C{j}")
print("Ошибки:", dict(errs), "первые:", first)
d = open_spreadsheet().worksheet("Данные").get_all_values(value_render_option="UNFORMATTED_VALUE")
print("Строк в «Данные»:", len(d), "| типы столбца даты:", collections.Counter(type(r[0]).__name__ for r in d[1:]),
      "| типы значения:", collections.Counter(type(r[5]).__name__ for r in d[1:] if len(r) > 5))
print("Строки с нечисловым значением (метрика, площадка):",
      [(r[4], r[2]) for r in d[1:] if len(r) > 5 and not isinstance(r[5], (int, float))])
