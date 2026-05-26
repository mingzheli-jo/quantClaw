import logging
import time
from datetime import date

import httpx
import pandas as pd

from app.services.data.providers.base import AbstractProvider

logger = logging.getLogger(__name__)

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://quote.eastmoney.com/",
}
_TIMEOUT = 15
_MAX_RETRIES = 3
_RETRY_DELAY = 15


def _get(url: str, params: dict | None = None) -> dict | None:
    for attempt in range(_MAX_RETRIES):
        try:
            resp = httpx.get(url, params=params, headers=_HEADERS, timeout=_TIMEOUT)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.warning(f"EastMoney request attempt {attempt + 1} failed: {e}")
            if attempt < _MAX_RETRIES - 1:
                time.sleep(_RETRY_DELAY)
    return None


class EastmoneyProvider(AbstractProvider):
    def fetch_stock_basic_list(self) -> pd.DataFrame:
        url = "http://push2.eastmoney.com/api/qt/clist/get"
        params = {
            "pn": "1", "pz": "6000", "po": "1", "np": "1",
            "fltt": "2", "invt": "2", "fid": "f3",
            "fs": "m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23,m:0+t:81+s:2048",
            "fields": "f2,f3,f12,f14,f100",
        }
        data = _get(url, params)
        if not data or "data" not in data or not data["data"]:
            return pd.DataFrame()
        rows = data["data"].get("diff", [])
        if not rows:
            return pd.DataFrame()
        records = []
        for r in rows:
            code = str(r.get("f12", ""))
            name = str(r.get("f14", ""))
            price = r.get("f2")
            change_pct = r.get("f3")
            industry = r.get("f100", "")
            if not code or price == "-":
                continue
            market = "bj" if code.startswith(("8", "4")) else "sh" if code.startswith("6") else "sz"
            is_st = "ST" in name or "退市" in name
            records.append({
                "code": code, "name": name, "price": float(price) if price else 0,
                "change_pct": float(change_pct) if change_pct and change_pct != "-" else 0,
                "market": market, "is_st": is_st, "list_date": None, "industry": industry,
            })
        df = pd.DataFrame(records)
        if len(df) < 1000:
            logger.warning(f"Stock list only returned {len(df)} records, may be rate-limited")
        return df

    def fetch_daily_klines(self, code: str, start_date: str, end_date: str) -> pd.DataFrame:
        market = "1" if code.startswith("6") else "0"
        secid = f"{market}.{code}"
        url = "http://push2his.eastmoney.com/api/qt/stock/kline/get"
        params = {
            "secid": secid, "klt": "101", "fqt": "1",
            "beg": start_date, "end": end_date,
            "fields1": "f1,f2,f3,f4,f5,f6",
            "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
        }
        data = _get(url, params)
        if not data or "data" not in data or not data["data"]:
            return pd.DataFrame()
        klines = data["data"].get("klines", [])
        if not klines:
            return pd.DataFrame()
        records = []
        for line in klines:
            parts = line.split(",")
            if len(parts) < 8:
                continue
            records.append({
                "code": code,
                "trade_date": pd.to_datetime(parts[0]).date(),
                "open": float(parts[1]),
                "close": float(parts[2]),
                "high": float(parts[3]),
                "low": float(parts[4]),
                "volume": int(float(parts[5])),
                "amount": float(parts[6]),
                "change_pct": float(parts[7]) if parts[7] != "-" else 0,
            })
        return pd.DataFrame(records)

    def fetch_north_flow(self, days: int = 30) -> pd.DataFrame:
        url = "http://push2his.eastmoney.com/api/qt/kamt.kline/get"
        params = {
            "fields1": "f1,f3,f5", "fields2": "f51,f52",
            "klt": "101", "lmt": str(days),
        }
        data = _get(url, params)
        if not data or "data" not in data or not data["data"]:
            return pd.DataFrame()
        s2n = data["data"].get("s2n", [])
        if not s2n:
            return pd.DataFrame()
        records = []
        for line in s2n:
            parts = line.split(",")
            if len(parts) < 2:
                continue
            net = float(parts[1]) if parts[1] != "-" else 0
            records.append({
                "trade_date": pd.to_datetime(parts[0]).date(),
                "net_amount": net,
                "buy_amount": net if net > 0 else 0,
                "sell_amount": abs(net) if net < 0 else 0,
            })
        return pd.DataFrame(records)

    def fetch_sector_daily(self) -> pd.DataFrame:
        url = "http://push2.eastmoney.com/api/qt/clist/get"
        params = {
            "pn": "1", "pz": "100", "po": "1", "np": "1",
            "fltt": "2", "invt": "2", "fid": "f3",
            "fs": "m:90+t:2",
            "fields": "f3,f12,f14,f62",
        }
        data = _get(url, params)
        if not data or "data" not in data or not data["data"]:
            return pd.DataFrame()
        rows = data["data"].get("diff", [])
        records = []
        for r in rows:
            sector = r.get("f14", "")
            change_pct = r.get("f3", 0)
            net_fund = r.get("f62", 0)
            if not sector:
                continue
            records.append({
                "sector": sector,
                "trade_date": date.today(),
                "change_pct": float(change_pct) if change_pct != "-" else 0,
                "volume": 0,
                "net_fund_flow": float(net_fund) if net_fund and net_fund != "-" else 0,
            })
        return pd.DataFrame(records)

    def fetch_market_sentiment(self) -> dict:
        df = self.fetch_stock_basic_list()
        if df.empty or "change_pct" not in df.columns:
            return {}
        up = (df["change_pct"] > 0).sum()
        down = (df["change_pct"] < 0).sum()
        flat = (df["change_pct"] == 0).sum()
        limit_up = (df["change_pct"] >= 9.9).sum()
        limit_down = (df["change_pct"] <= -9.9).sum()
        return {
            "trade_date": date.today(),
            "up_count": int(up), "down_count": int(down), "flat_count": int(flat),
            "limit_up": int(limit_up), "limit_down": int(limit_down),
        }
