import logging
import time
from datetime import date, timedelta

import akshare as ak
import pandas as pd

logger = logging.getLogger(__name__)

BATCH_SIZE = 500
BATCH_DELAY = 3
MAX_RETRIES = 3
RETRY_DELAY = 30


def _retry(fn, *args, **kwargs):
    for attempt in range(MAX_RETRIES):
        try:
            return fn(*args, **kwargs)
        except Exception as e:
            logger.warning(f"Attempt {attempt + 1} failed: {e}")
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY)
    logger.error(f"All {MAX_RETRIES} attempts failed for {fn.__name__}")
    return None


def fetch_stock_basic_list() -> pd.DataFrame:
    df = _retry(ak.stock_zh_a_spot_em)
    if df is None or df.empty:
        return pd.DataFrame()
    result = df.rename(columns={
        "代码": "code", "名称": "name", "最新价": "price",
        "总市值": "market_cap", "所属行业": "industry",
    })
    result["market"] = result["code"].apply(
        lambda c: "bj" if c.startswith(("8", "4")) else "sh" if c.startswith("6") else "sz"
    )
    result["is_st"] = result["name"].str.contains(r"ST|退市", case=False, na=False)
    result["list_date"] = None
    cols = ["code", "name", "price", "market", "is_st", "list_date"]
    if "industry" in result.columns:
        cols.append("industry")
    return result[cols].copy()


def fetch_daily_klines_batch(
    codes: list[str],
    start_date: str = "",
    end_date: str = "",
) -> pd.DataFrame:
    if not start_date:
        start_date = (date.today() - timedelta(days=400)).strftime("%Y%m%d")
    if not end_date:
        end_date = date.today().strftime("%Y%m%d")

    all_frames = []
    for i in range(0, len(codes), BATCH_SIZE):
        batch = codes[i:i + BATCH_SIZE]
        for code in batch:
            df = _retry(ak.stock_zh_a_hist, symbol=code, period="daily", start_date=start_date, end_date=end_date, adjust="qfq")
            if df is not None and not df.empty:
                df = df.rename(columns={
                    "日期": "trade_date", "开盘": "open", "最高": "high",
                    "最低": "low", "收盘": "close", "成交量": "volume",
                    "成交额": "amount", "涨跌幅": "change_pct",
                })
                df["code"] = code
                df["trade_date"] = pd.to_datetime(df["trade_date"]).dt.date
                all_frames.append(df[["code", "trade_date", "open", "high", "low", "close", "volume", "amount", "change_pct"]])
        if i + BATCH_SIZE < len(codes):
            time.sleep(BATCH_DELAY)

    if not all_frames:
        return pd.DataFrame()
    return pd.concat(all_frames, ignore_index=True)


def fetch_north_flow(days: int = 30) -> pd.DataFrame:
    df = _retry(ak.stock_hsgt_north_net_flow_in_em)
    if df is None or df.empty:
        return pd.DataFrame()
    df = df.rename(columns={"date": "trade_date", "value": "net_amount"})
    df["trade_date"] = pd.to_datetime(df["trade_date"]).dt.date
    df["buy_amount"] = 0.0
    df["sell_amount"] = 0.0
    return df.tail(days)


def fetch_sector_daily() -> pd.DataFrame:
    df = _retry(ak.stock_board_industry_name_em)
    if df is None or df.empty:
        return pd.DataFrame()
    result = df.rename(columns={
        "板块名称": "sector", "板块涨跌幅": "change_pct",
        "总成交量": "volume", "净流入": "net_fund_flow",
    })
    cols_available = [c for c in ["sector", "change_pct", "volume", "net_fund_flow"] if c in result.columns]
    result = result[cols_available].copy()
    result["trade_date"] = date.today()
    for col in ["change_pct", "volume", "net_fund_flow"]:
        if col not in result.columns:
            result[col] = 0
    return result


def fetch_market_sentiment() -> dict:
    df = _retry(ak.stock_zh_a_spot_em)
    if df is None or df.empty:
        return {}
    change_col = "涨跌幅" if "涨跌幅" in df.columns else None
    if change_col is None:
        return {}
    up = (df[change_col] > 0).sum()
    down = (df[change_col] < 0).sum()
    flat = (df[change_col] == 0).sum()
    limit_up = (df[change_col] >= 9.9).sum()
    limit_down = (df[change_col] <= -9.9).sum()
    return {
        "trade_date": date.today(),
        "up_count": int(up),
        "down_count": int(down),
        "flat_count": int(flat),
        "limit_up": int(limit_up),
        "limit_down": int(limit_down),
    }
