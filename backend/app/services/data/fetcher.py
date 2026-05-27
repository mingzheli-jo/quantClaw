import logging
import random
import time
from datetime import date, timedelta

import pandas as pd

from app.services.data.providers.base import DataSourceManager

logger = logging.getLogger(__name__)

BATCH_SIZE = 500
BATCH_DELAY = 3


def fetch_stock_basic_list() -> pd.DataFrame:
    provider = DataSourceManager.get_provider()
    df = provider.fetch_stock_basic_list()
    if df is None:
        return pd.DataFrame()
    return df


def fetch_daily_klines_batch(
    codes: list[str],
    start_date: str = "",
    end_date: str = "",
) -> pd.DataFrame:
    if not start_date:
        start_date = (date.today() - timedelta(days=400)).strftime("%Y%m%d")
    if not end_date:
        end_date = date.today().strftime("%Y%m%d")

    provider = DataSourceManager.get_provider()
    all_frames = []
    for i in range(0, len(codes), BATCH_SIZE):
        batch = codes[i:i + BATCH_SIZE]
        for code in batch:
            df = provider.fetch_daily_klines(code, start_date, end_date)
            if df is not None and not df.empty:
                all_frames.append(df)
            time.sleep(random.uniform(0.3, 0.8))
        if i + BATCH_SIZE < len(codes):
            time.sleep(BATCH_DELAY)

    if not all_frames:
        return pd.DataFrame()
    return pd.concat(all_frames, ignore_index=True)


def fetch_north_flow(days: int = 30) -> pd.DataFrame:
    provider = DataSourceManager.get_provider()
    df = provider.fetch_north_flow(days)
    if df is None:
        return pd.DataFrame()
    return df


def fetch_sector_daily() -> pd.DataFrame:
    provider = DataSourceManager.get_provider()
    df = provider.fetch_sector_daily()
    if df is None:
        return pd.DataFrame()
    return df


def fetch_market_sentiment() -> dict:
    provider = DataSourceManager.get_provider()
    result = provider.fetch_market_sentiment()
    if result is None:
        return {}
    return result
