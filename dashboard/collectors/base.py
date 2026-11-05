"""Общий формат строки данных и интерфейс сборщика."""
from dataclasses import dataclass
from datetime import date


@dataclass
class Row:
    """Одна строка листа «Данные»: дата, кабинет, площадка, бренд, метрика, значение."""
    day: date
    cabinet: str
    platform: str
    brand: str       # "" если разбивки по брендам нет
    metric: str      # orders_qty, orders_rub, cancels_qty, returns_qty, ad_spend ...
    value: float

    def as_list(self):
        return [self.day.isoformat(), self.cabinet, self.platform,
                self.brand, self.metric, self.value]


def collect(cabinet_key: str, day: date) -> list:
    """Каждый сборщик реализует collect() и возвращает список Row."""
    raise NotImplementedError
