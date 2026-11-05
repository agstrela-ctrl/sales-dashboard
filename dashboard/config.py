"""Настройки. Все ключи берутся ТОЛЬКО из переменных окружения (GitHub Secrets)."""
import os
from dataclasses import dataclass


def _env(name: str) -> str:
    return os.environ.get(name, "").strip()


@dataclass(frozen=True)
class Cabinet:
    key: str            # "meco" или "berton_samley"
    title: str          # название кабинета для таблицы
    platforms: tuple    # какие площадки собираем


CABINETS = (
    Cabinet("meco", "Meco", ("ozon",)),
    Cabinet("berton_samley", "Berton + Samley", ("ozon", "wb", "yandex")),
)

# Названия секретов (значения живут только в GitHub Secrets)
SECRET_NAMES = (
    "OZON_MECO_CLIENT_ID", "OZON_MECO_API_KEY",
    "OZON_MECO_PERF_CLIENT_ID", "OZON_MECO_PERF_SECRET",
    "OZON_BS_CLIENT_ID", "OZON_BS_API_KEY",
    "OZON_BS_PERF_CLIENT_ID", "OZON_BS_PERF_SECRET",
    "WB_BS_TOKEN",
    "YM_BS_API_KEY", "YM_BS_CAMPAIGN_ID", "YM_BS_BUSINESS_ID",
    "GOOGLE_SA_JSON", "SHEET_ID",
)


def secret(name: str) -> str:
    return _env(name)
