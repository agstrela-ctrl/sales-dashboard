"""Лист «Дашборд»: формулы поверх листа «Данные». Данных не хранит — пересчитывается сам.

Структура:
  строка 1      — заголовок
  строка 2      — дата отчёта (B2, по умолчанию вчера; можно вписать любую)
  строки 4–5    — карточки с главными числами
  строки 7–11   — «Что горит сегодня» (светофор)
  строка 13     — шапка таблицы, дальше блоки: общий итог, кабинеты, площадки, бренды
  колонка O     — скрытые служебные ключи дат
Формулы — с разделителем «;» (таблица с русской локалью).
"""
N = 10000  # сколько строк «Данных» просматриваем

D = "Данные!"
COL = {"date": f"{D}$A$2:$A${N}", "cab": f"{D}$B$2:$B${N}", "plat": f"{D}$C$2:$C${N}",
       "brand": f"{D}$D$2:$D${N}", "metric": f"{D}$E$2:$E${N}", "val": f"{D}$F$2:$F${N}"}

# (подпись, кабинет, площадка, бренд, показывать рекламу, тип строки)
BLOCKS = [
    ("ОБЩИЙ ИТОГ", None, None, None, True, "total"),
    ("Meco (Озон)", "meco", None, None, True, "cab"),
    ("Berton + Samley — кабинет всего", "berton_samley", None, None, True, "cab"),
    ("   Озон", "berton_samley", "ozon", None, True, "sub"),
    ("   Wildberries", "berton_samley", "wb", None, True, "sub"),
    ("   Яндекс.Маркет", "berton_samley", "yandex", None, True, "sub"),
    ("BERTON — всего", "berton_samley", None, "Berton", False, "cab"),
    ("   Озон ", "berton_samley", "ozon", "Berton", False, "sub"),
    ("   Wildberries ", "berton_samley", "wb", "Berton", False, "sub"),
    ("   Яндекс.Маркет ", "berton_samley", "yandex", "Berton", False, "sub"),
    ("SAMLEY — всего", "berton_samley", None, "Samley", False, "cab"),
    ("   Озон  ", "berton_samley", "ozon", "Samley", False, "sub"),
    ("   Wildberries  ", "berton_samley", "wb", "Samley", False, "sub"),
    ("   Яндекс.Маркет  ", "berton_samley", "yandex", "Samley", False, "sub"),
]
HEAD = 13           # строка шапки таблицы
FIRST = HEAD + 1    # первая строка данных (общий итог)
LAST = HEAD + len(BLOCKS)
T = FIRST           # строка «Общий итог»
ROW = {}
for i, b in enumerate(BLOCKS):
    ROW.setdefault(b[0].strip(), FIRST + i)  # при повторе названий берём первую (кабинетную) строку


def _sum(metric, cab, plat, brand, when):
    c = {"day": f'({COL["date"]}=$O$1)', "week": f'({COL["date"]}=$O$2)',
         "month": f'(LEFT({COL["date"]};7)=$O$3)*({COL["date"]}<=$O$1)'}[when]
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


def _fix(row):
    return [c.replace(",", ";") if isinstance(c, str) and c.startswith("=") else c for c in row]


def _key(expr):
    return f'=YEAR({expr})&"-"&TEXT(MONTH({expr});"00")&"-"&TEXT(DAY({expr});"00")'


def build_values():
    rows = [[""] * 16 for _ in range(LAST + 8)]

    def put(r, c, v):  # r, c — с единицы
        rows[r - 1][c - 1] = v

    put(1, 1, "Утренний дашборд продаж")
    put(2, 1, "Дата отчёта (можно изменить):")
    put(2, 2, "=TODAY()-1")
    put(1, 15, _key("B2"))
    put(2, 15, _key("(B2-7)"))
    put(3, 15, '=YEAR(B2)&"-"&TEXT(MONTH(B2);"00")')

    # Карточки (подписи — строка 4, значения — строка 5)
    cards = [(1, "Заказы за день, ₽", f"=C{T}"), (2, "Заказы, шт", f"=B{T}"),
             (4, "Средний чек, ₽", f"=D{T}"), (6, "Отмены, шт", f"=E{T}"),
             (8, "К прошлой неделе", f"=J{T}"), (10, "Прогноз на конец месяца, ₽", f"=L{T}")]
    for c, label, f in cards:
        put(4, c, label)
        put(5, c, f)

    # Что горит сегодня
    put(7, 1, "ЧТО ГОРИТ СЕГОДНЯ")
    put(8, 1, f'=IF(J{T}="";"⚪ Нет данных за прошлую неделю для сравнения";'
              f'IF(J{T}<=-20/100;"🔴 Заказы упали на "&ROUND(-J{T}*100;0)&"% к прошлой неделе";'
              f'IF(J{T}<0;"🟡 Заказы ниже прошлой недели на "&ROUND(-J{T}*100;0)&"%";'
              f'"🟢 Заказы не ниже прошлой недели (+"&ROUND(J{T}*100;0)&"%)")))')
    put(9, 1, f'=IF(B{T}+E{T}=0;"⚪ Нет заказов и отмен за день";'
              f'IF(E{T}/(B{T}+E{T})>=15/100;"🔴 Много отмен: "&ROUND(E{T}/(B{T}+E{T})*100;0)&"% от всех заказов";'
              f'"🟢 Отмены в норме: "&ROUND(E{T}/(B{T}+E{T})*100;0)&"%"))')
    put(10, 1, f'=IF(H{T}="";"⚪ Реклама не подключена или расхода нет";'
               f'IF(H{T}>=15/100;"🔴 ДРР высокий: ";"🟢 ДРР в норме: ")&ROUND(H{T}*100;1)&"%")')
    m, o, w, y = ROW["Meco (Озон)"], ROW["Озон"], ROW["Wildberries"], ROW["Яндекс.Маркет"]
    names = (f'IF(B{m}=0;"Meco, ";"")&IF(B{o}=0;"Озон Berton/Samley, ";"")'
             f'&IF(B{w}=0;"WB, ";"")&IF(B{y}=0;"Яндекс.Маркет, ";"")')
    put(11, 1, f'=IF({names}="";"🟢 Заказы есть на всех площадках";"🟡 Нет заказов: "&{names})')

    # Таблица
    for i, h in enumerate(HEADERS, 1):
        put(HEAD, i, h)
    r = FIRST
    for label, cab, plat, brand, ads, _ in BLOCKS:
        s = lambda mt, wh="day": _sum(mt, cab, plat, brand, wh)
        vals = [label, "=" + s("orders_qty"), "=" + s("orders_rub"),
                f'=IF(B{r}>0;C{r}/B{r};"")', "=" + s("cancels_qty"), "=" + s("cancels_rub"),
                ("=" + s("ad_spend")) if ads else "",
                f'=IF(AND(G{r}<>"";C{r}>0);G{r}/C{r};"")' if ads else "",
                "=" + s("orders_rub", "week"), f'=IF(I{r}>0;C{r}/I{r}-1;"")',
                "=" + s("orders_rub", "month"),
                f'=IF(K{r}>0;K{r}/DAY($B$2)*DAY(EOMONTH($B$2;0));"")']
        for c, v in enumerate(vals, 1):
            put(r, c, v)
        r += 1

    notes = ["Примечания:",
             "• Заказы — созданные за день, без отменённых. Отмены — до получения. Возвраты покупателей пока не считаем.",
             "• Реклама Озона и Яндекс.Маркета пока не подключена; реклама показана по кабинету и площадкам, по брендам не делится.",
             "• Прогноз = месяц нарастающим / номер дня × число дней в месяце (грубая оценка).",
             "• Светофор: 🔴 заказы упали на 20% и больше, или отмены от 15%, или ДРР от 15%; 🟡 внимание; 🟢 норма."]
    for i, t in enumerate(notes):
        put(LAST + 2 + i, 1, t)
    return [_fix(r) for r in rows]


def _rgb(h):
    h = h.lstrip("#")
    return {"red": int(h[0:2], 16) / 255, "green": int(h[2:4], 16) / 255, "blue": int(h[4:6], 16) / 255}


def apply(ws):
    sp = ws.spreadsheet
    ws.clear()
    ws.freeze(rows=0, cols=0)  # иначе нельзя объединять ячейки через замороженный столбец
    sp.batch_update({"requests": [{"unmergeCells": {"range": {"sheetId": ws.id}}}]})
    ws.update(values=build_values(), range_name="A1", value_input_option="USER_ENTERED")

    navy, white, light = _rgb("1F3A5F"), _rgb("FFFFFF"), _rgb("EEF2F8")
    card, grey = _rgb("F4F7FB"), _rgb("8A94A6")
    fmt = []
    add = lambda rng, f: fmt.append({"range": rng, "format": f})

    add("A1", {"textFormat": {"bold": True, "fontSize": 20, "foregroundColor": navy}})
    add("A2:B2", {"textFormat": {"foregroundColor": grey}})
    add("B2", {"numberFormat": {"type": "DATE", "pattern": "dd.mm.yyyy"}, "horizontalAlignment": "LEFT"})
    # карточки
    add("A4:K4", {"textFormat": {"fontSize": 9, "foregroundColor": grey}, "backgroundColor": card,
                  "horizontalAlignment": "CENTER"})
    add("A5:K5", {"textFormat": {"bold": True, "fontSize": 18, "foregroundColor": navy},
                  "backgroundColor": card, "horizontalAlignment": "CENTER",
                  "numberFormat": {"type": "NUMBER", "pattern": "#,##0"}})
    add("H5:I5", {"numberFormat": {"type": "PERCENT", "pattern": "+0%;-0%;0%"}})
    # светофор
    add("A7:K7", {"textFormat": {"bold": True, "foregroundColor": white}, "backgroundColor": navy})
    add("A8:K11", {"textFormat": {"fontSize": 11}, "backgroundColor": card})
    # таблица
    add(f"A{HEAD}:L{HEAD}", {"textFormat": {"bold": True, "foregroundColor": white},
                             "backgroundColor": navy, "wrapStrategy": "WRAP",
                             "horizontalAlignment": "CENTER", "verticalAlignment": "MIDDLE"})
    add(f"A{HEAD}", {"horizontalAlignment": "LEFT"})
    add(f"B{FIRST}:G{LAST}", {"numberFormat": {"type": "NUMBER", "pattern": "#,##0"}})
    add(f"I{FIRST}:I{LAST}", {"numberFormat": {"type": "NUMBER", "pattern": "#,##0"}})
    add(f"K{FIRST}:L{LAST}", {"numberFormat": {"type": "NUMBER", "pattern": "#,##0"}})
    add(f"H{FIRST}:H{LAST}", {"numberFormat": {"type": "PERCENT", "pattern": "0.0%"}})
    add(f"J{FIRST}:J{LAST}", {"numberFormat": {"type": "PERCENT", "pattern": "+0%;-0%;0%"}})
    add(f"B{FIRST}:L{LAST}", {"horizontalAlignment": "RIGHT"})
    for i, b in enumerate(BLOCKS):
        r, kind = FIRST + i, b[5]
        if kind == "total":
            add(f"A{r}:L{r}", {"textFormat": {"bold": True, "fontSize": 11}, "backgroundColor": _rgb("DCE6F4")})
        elif kind == "cab":
            add(f"A{r}:L{r}", {"textFormat": {"bold": True}, "backgroundColor": light})
    add(f"A{LAST + 2}:A{LAST + 7}", {"textFormat": {"fontSize": 9, "foregroundColor": grey}})
    ws.batch_format(fmt)

    # объединения для карточек и светофора
    for rng in ("B4:C4", "B5:C5", "D4:E4", "D5:E5", "F4:G4", "F5:G5", "H4:I4", "H5:I5", "J4:K4", "J5:K5"):
        ws.merge_cells(rng)
    for r in range(7, 12):
        ws.merge_cells(f"A{r}:K{r}")

    reqs = []
    width = lambda a, b, px: reqs.append({"updateDimensionProperties": {
        "range": {"sheetId": ws.id, "dimension": "COLUMNS", "startIndex": a, "endIndex": b},
        "properties": {"pixelSize": px}, "fields": "pixelSize"}})
    width(0, 1, 300)
    width(1, 12, 115)
    reqs.append({"updateDimensionProperties": {
        "range": {"sheetId": ws.id, "dimension": "COLUMNS", "startIndex": 14, "endIndex": 15},
        "properties": {"hiddenByUser": True}, "fields": "hiddenByUser"}})
    height = lambda a, b, px: reqs.append({"updateDimensionProperties": {
        "range": {"sheetId": ws.id, "dimension": "ROWS", "startIndex": a, "endIndex": b},
        "properties": {"pixelSize": px}, "fields": "pixelSize"}})
    height(4, 5, 46)      # значения карточек
    height(HEAD - 1, HEAD, 52)
    height(7, 11, 26)
    # цвета для «К прошлой неделе»: зелёный выше нуля, красный ниже
    for cond, color in (("NUMBER_GREATER", "1E8E3E"), ("NUMBER_LESS", "D93025")):
        reqs.append({"addConditionalFormatRule": {"index": 0, "rule": {
            "ranges": [{"sheetId": ws.id, "startRowIndex": FIRST - 1, "endRowIndex": LAST,
                        "startColumnIndex": 9, "endColumnIndex": 10}],
            "booleanRule": {"condition": {"type": cond, "values": [{"userEnteredValue": "0"}]},
                            "format": {"textFormat": {"foregroundColor": _rgb(color), "bold": True}}}}}})
    sp.batch_update({"requests": reqs})
    ws.freeze(rows=2)
