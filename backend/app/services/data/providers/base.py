import abc
import logging
from datetime import date

import pandas as pd

from app.database import SessionLocal
from app.models.config import SystemConfig

logger = logging.getLogger(__name__)

_DATA_SOURCE_KEY = "data_source"
_DEFAULT_SOURCE = "eastmoney"


class AbstractProvider(abc.ABC):
    @abc.abstractmethod
    def fetch_stock_basic_list(self) -> pd.DataFrame:
        """Return DataFrame with columns: code, name, price, market, is_st, list_date, industry"""

    @abc.abstractmethod
    def fetch_daily_klines(self, code: str, start_date: str, end_date: str) -> pd.DataFrame:
        """Return DataFrame with columns: code, trade_date, open, high, low, close, volume, amount, change_pct"""

    @abc.abstractmethod
    def fetch_north_flow(self, days: int = 30) -> pd.DataFrame:
        """Return DataFrame with columns: trade_date, buy_amount, sell_amount, net_amount"""

    @abc.abstractmethod
    def fetch_sector_daily(self) -> pd.DataFrame:
        """Return DataFrame with columns: sector, trade_date, change_pct, volume, net_fund_flow"""

    @abc.abstractmethod
    def fetch_market_sentiment(self) -> dict:
        """Return dict with keys: trade_date, up_count, down_count, flat_count, limit_up, limit_down"""


class DataSourceManager:
    _providers: dict[str, AbstractProvider] = {}
    _current: str | None = None

    @classmethod
    def register(cls, name: str, provider: AbstractProvider) -> None:
        cls._providers[name] = provider

    @classmethod
    def get_source_name(cls) -> str:
        if cls._current:
            return cls._current
        db = SessionLocal()
        try:
            row = db.query(SystemConfig).filter(SystemConfig.key == _DATA_SOURCE_KEY).first()
            cls._current = row.value if row else _DEFAULT_SOURCE
        finally:
            db.close()
        return cls._current

    @classmethod
    def set_source(cls, name: str) -> None:
        if name not in cls._providers:
            raise ValueError(f"Unknown data source: {name}. Available: {list(cls._providers.keys())}")
        db = SessionLocal()
        try:
            row = db.query(SystemConfig).filter(SystemConfig.key == _DATA_SOURCE_KEY).first()
            if row:
                row.value = name
            else:
                db.add(SystemConfig(key=_DATA_SOURCE_KEY, value=name))
            db.commit()
        finally:
            db.close()
        cls._current = name

    @classmethod
    def get_provider(cls) -> AbstractProvider:
        name = cls.get_source_name()
        if name not in cls._providers:
            logger.warning(f"Provider '{name}' not registered, falling back to '{_DEFAULT_SOURCE}'")
            name = _DEFAULT_SOURCE
        return cls._providers[name]

    @classmethod
    def available_sources(cls) -> list[str]:
        return list(cls._providers.keys())

    @classmethod
    def reset(cls) -> None:
        cls._current = None
