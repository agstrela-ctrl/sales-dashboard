"""Лист «Дашборд»: формулы поверх листа «Данные». Данных не хранит — пересчитывается сам.

B1 — дата отчёта (по умолчанию вчера; можно вписать любую дату).
Колонки: заказы шт/₽, средний чек, отмены шт/₽, реклама ₽, ДРР,
         заказы ₽ в тот же день прошлой недели и разница, месяц нарастающим и прогноз.
"""
N = 10000  # сколько строк «Данных» просматриваем

D = "Данные!"
COL = {"date": f"{D}$A$2:$A${N}", "cab": f"{D}$B$2:$B${N}", "plat": f"{D}$C$2:$C${N}",
       "brand": f"{D}$D$2:$D${N}", "metric": f"{D}$E$2:$E${N}", "val": f"{D}$F$2:$F${N}"}

# (подпись, кабинет, площадка, бренд, показывать рекламу)
BLOCKS = [
    ("ОБЩИЙ ИТОГ", None, None, None, True),
    ("Meco (Озон)", "meco", None, None, True),
    ("Berton + Samley — всего", "berton_samley", None, None, True),
    ("   Озон", "berton_samley", "ozon", None, True),
    ("   Wildberries", "berton_samley", "wb", None, True),
    ("   Яндекс.Маркет", "berton_samley", "yandex", None, True),
    ("   Бренд Berton (все площадки)", "berton_samley", None, "Berton", False),
    ("   Бренд Samley (все площадки)", "berton_samley", None, "Samley", False),
]


def _sum(metric, cab, plat, brand, when):
    """SUMPRODUCT по условиям. when: 'day' | 'week' | 'month'."""
    c = {"day": f'({COL["date"]}=$B$2)', "week": f'({COL["date"]}=$B$3)',
         "month": f'(LEFT({COL["date"]},7)=$B$4)*({COL["date"]}<=$B$2)'}[when]
    parts = [c, f'({COL["metric"]}="{metric}")']
    if cab:
        parts.append(f'({COL["cab"]}="{cab}")')
    if plat:
        parts.append(f'({COL["plat"]}="{plat}")')
    if brand:
        parts.append(f'(UPPER({COL["brand"]})="{brand.upper()}")')
    return "SUMPRODUCT(" + "*".join(parts) + f'; {COL["val"]})'


HEADERS = ["", "Заказы, шт", "Заказы, ₽", "Средний чек, ₽", "Отмены, шт", "Отмены, ₽",
           "Реклама, ₽", "ДРР", "Заказы ₽ — тот же день прошлой недели", "К прошлой неделе",
           "Заказы ₽ с начала месяца", "Прогноз на конец месяца, ₽"]


def build_values():
    rows = [
        ["Дата отчёта:", "=TODAY()-1"],
        ["(ключ дня)", '=YEAR(B1)&"-"&TEXT(MONTH(B1),"00")&"-"&TEXT(DAY(B1),"00")'],
        ["(ключ недели назад)", '=YEAR(B1-7)&"-"&TEXT(MONTH(B1-7),"00")&"-"&TEXT(DAY(B1-7),"00")'],
        ["(ключ месяца)", '=YEAR(B1)&"-"&TEXT(MONTH(B1),"00")'],
        [],
        HEADERS,
    ]
    r = len(rows) + 1
    for label, cab, plat, brand, ads in BLOCKS:
        s = lambda m, w="day": _sum(m, cab, plat, brand, w)
        rows.append([
            label,
            "=" + s("orders_qty"),
            "=" + s("orders_rub"),
            f'=IF(B{r}>0,C{r}/B{r},"")',
            "=" + s("cancels_qty"),
            "=" + s("cancels_rub"),
            ("=" + s("ad_spend")) if ads else "",
            f'=IF(AND(G{r}<>"",C{r}>0),G{r}/C{r},"")' if ads else "",
            "=" + s("orders_rub", "week"),
            f'=IF(I{r}>0,C{r}/I{r}-1,"")',
            "=" + s("orders_rub", "month"),
            f'=IF(K{r}>0,K{r}/DAY($B$1)*DAY(EOMONTH($B$1,0)),"")',
        ])
        r += 1
    # Таблица с русской локалью: разделитель аргументов формул — «;», а не «,»
    rows = [[c.replace(",", ";") if isinstance(c, str) and c.startswith("=") else c for c in row]
            for row in rows]
    rows += [[], ["Примечания:"],
             ["• Заказы — созданные за день, без отменённых. Отмены — до получения. Возвраты покупателей пока не считаем."],
             ["• Реклама Озона и Яндекс.Маркета пока не подключена; по брендам реклама не делится."],
             ["• Прогноз = месяц нарастающим / номер дня × число дней в месяце (грубая оценка)."]]
    return rows


def apply(ws):
    ws.clear()
    ws.update(values=build_values(), range_name="A1", value_input_option="USER_ENTERED")
    n = 6 + len(BLOCKS)
    ws.format("B1", {"numberFormat": {"type": "DATE", "pattern": "dd.mm.yyyy"}})
    ws.format("A6:L6", {"textFormat": {"bold": True}, "wrapStrategy": "WRAP",
                        "backgroundColor": {"red": 0.9, "green": 0.93, "blue": 0.98}})
    ws.format("A7:A7", {"textFormat": {"bold": True}})
    ws.format(f"B7:G{n}", {"numberFormat": {"type": "NUMBER", "pattern": "#,##0"}})
    ws.format(f"I7:I{n}", {"numberFormat": {"type": "NUMBER", "pattern": "#,##0"}})
    ws.format(f"K7:L{n}", {"numberFormat": {"type": "NUMBER", "pattern": "#,##0"}})
    ws.format(f"H7:H{n}", {"numberFormat": {"type": "PERCENT", "pattern": "0.0%"}})
    ws.format(f"J7:J{n}", {"numberFormat": {"type": "PERCENT", "pattern": "+0%;-0%;0%"}})
    ws.format("A2:A4", {"textFormat": {"foregroundColor": {"red": 0.6, "green": 0.6, "blue": 0.6}}})
    ws.format("B2:B4", {"textFormat": {"foregroundColor": {"red": 0.6, "green": 0.6, "blue": 0.6}}})
    ws.freeze(rows=6, cols=1)
    ws.columns_auto_resize(0, 12)
