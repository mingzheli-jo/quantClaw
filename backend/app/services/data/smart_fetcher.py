import logging
import random
import time
from datetime import date, timedelta

import pandas as pd

from app.services.data.providers.base import AbstractProvider

logger = logging.getLogger(__name__)

BATCH_SIZE = 500
BATCH_DELAY = 3


class SmartFetcher:
    def __init__(self, primary: AbstractProvider, fallback: AbstractProvider):
        self._primary = primary
        self._fallback = fallback

    def _try_with_fallback(
        self,
        method_name: str,
        args: tuple = (),
        kwargs: dict | None = None,
        allow_fallback: bool = True,
    ) -> pd.DataFrame | dict | None:
        kwargs = kwargs or {}
        try:
            result = getattr(self._primary, method_name)(*args, **kwargs)
            if isinstance(result, pd.DataFrame) and result.empty:
                raise ValueError(f"Primary returned empty for {method_name}")
            if isinstance(result, dict) and not result:
                raise ValueError(f"Primary returned empty dict for {method_name}")
            return result
        except Exception as e:
            logger.warning(f"Primary {method_name} failed: {e}")
            if not allow_fallback:
                return pd.DataFrame() if method_name != "fetch_market_sentiment" else {}
            try:
                result = getattr(self._fallback, method_name)(*args, **kwargs)
                logger.info(f"Fallback {method_name} succeeded")
                return result
            except Exception as e2:
                logger.error(f"Fallback {method_name} also failed: {e2}")
                return pd.DataFrame() if method_name != "fetch_market_sentiment" else {}

    def fetch_stock_basic_list(self) -> pd.DataFrame:
        result = self._try_with_fallback("fetch_stock_basic_list")
        if isinstance(result, pd.DataFrame) and len(result) < 1000:
            logger.warning(f"Primary stock list only returned {len(result)} records, trying fallback")
            try:
                fallback_result = self._fallback.fetch_stock_basic_list()
                if isinstance(fallback_result, pd.DataFrame) and len(fallback_result) > len(result):
                    logger.info(f"Fallback stock list returned {len(fallback_result)} records")
                    return fallback_result
            except Exception as e:
                logger.warning(f"Fallback stock list also failed: {e}")
        return result if isinstance(result, pd.DataFrame) else pd.DataFrame()

    def fetch_daily_klines_batch(
        self,
        codes: list[str],
        start_date: str = "",
        end_date: str = "",
    ) -> pd.DataFrame:
        if not start_date:
            start_date = (date.today() - timedelta(days=400)).strftime("%Y%m%d")
        if not end_date:
            end_date = date.today().strftime("%Y%m%d")
        all_frames: list[pd.DataFrame] = []
        source = self._primary
        failed_primary = False
        for i in range(0, len(codes), BATCH_SIZE):
            batch = codes[i : i + BATCH_SIZE]
            for code in batch:
                try:
                    df = source.fetch_daily_klines(code, start_date, end_date)
                    if df is not None and not df.empty:
                        all_frames.append(df)
                    elif not failed_primary:
                        raise ValueError("empty kline response")
                except Exception:
                    if not failed_primary:
                        logger.warning("Primary klines failing, switching to fallback")
                        source = self._fallback
                        failed_primary = True
                        try:
                            df = source.fetch_daily_klines(code, start_date, end_date)
                            if df is not None and not df.empty:
                                all_frames.append(df)
                        except Exception:
                            pass
                time.sleep(random.uniform(0.3, 0.8))
            if i + BATCH_SIZE < len(codes):
                time.sleep(BATCH_DELAY)
        if not all_frames:
            return pd.DataFrame()
        return pd.concat(all_frames, ignore_index=True)

    def fetch_north_flow(self, days: int = 30) -> pd.DataFrame:
        result = self._try_with_fallback("fetch_north_flow", kwargs={"days": days}, allow_fallback=False)
        return result if isinstance(result, pd.DataFrame) else pd.DataFrame()

    def fetch_sector_daily(self) -> pd.DataFrame:
        result = self._try_with_fallback("fetch_sector_daily", allow_fallback=False)
        return result if isinstance(result, pd.DataFrame) else pd.DataFrame()

    def fetch_market_sentiment(self) -> dict:
        result = self._try_with_fallback("fetch_market_sentiment")
        return result if isinstance(result, dict) else {}
