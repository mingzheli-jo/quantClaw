import logging
from datetime import date, timedelta

import pandas as pd

from app.services.data.providers.base import AbstractProvider

logger = logging.getLogger(__name__)


class BaostockProvider(AbstractProvider):
    def _query_stock_list(self) -> pd.DataFrame:
        import baostock as bs
        bs.login()
        try:
            rs = bs.query_stock_basic()
            rows = []
            while rs.error_code == "0" and rs.next():
                rows.append(rs.get_row_data())
            return pd.DataFrame(rows, columns=rs.fields)
        finally:
            bs.logout()

    def fetch_stock_basic_list(self) -> pd.DataFrame:
        try:
            df = self._query_stock_list()
        except Exception as e:
            logger.error(f"BaoStock fetch_stock_basic_list failed: {e}")
            return pd.DataFrame()
        if df.empty:
            return pd.DataFrame()
        df = df[df["status"] == "1"].copy()
        df["code"] = df["code"].str.replace("sh.", "").str.replace("sz.", "").str.replace("bj.", "")
        df["market"] = df["code"].apply(
            lambda c: "bj" if c.startswith(("8", "4")) else "sh" if c.startswith("6") else "sz"
        )
        df["name"] = df.get("code_name", "")
        df["is_st"] = df["name"].str.contains(r"ST|退市", case=False, na=False)
        df["list_date"] = pd.to_datetime(df.get("ipoDate"), errors="coerce").dt.date
        df["price"] = 0
        df["industry"] = df.get("industry", "")
        return df[["code", "name", "price", "market", "is_st", "list_date", "industry"]].copy()

    def fetch_daily_klines(self, code: str, start_date: str, end_date: str) -> pd.DataFrame:
        import baostock as bs
        market = "sh" if code.startswith("6") else "sz"
        bs_code = f"{market}.{code}"
        start_fmt = f"{start_date[:4]}-{start_date[4:6]}-{start_date[6:]}"
        end_fmt = f"{end_date[:4]}-{end_date[4:6]}-{end_date[6:]}"
        bs.login()
        try:
            rs = bs.query_history_k_data_plus(
                bs_code, "date,open,high,low,close,volume,amount,pctChg",
                start_date=start_fmt, end_date=end_fmt,
                frequency="d", adjustflag="2",
            )
            rows = []
            while rs.error_code == "0" and rs.next():
                rows.append(rs.get_row_data())
            if not rows:
                return pd.DataFrame()
            df = pd.DataFrame(rows, columns=rs.fields)
            df = df.rename(columns={"date": "trade_date", "pctChg": "change_pct"})
            df["code"] = code
            df["trade_date"] = pd.to_datetime(df["trade_date"]).dt.date
            for col in ["open", "high", "low", "close", "amount", "change_pct"]:
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
            df["volume"] = pd.to_numeric(df["volume"], errors="coerce").fillna(0).astype(int)
            return df[["code", "trade_date", "open", "high", "low", "close", "volume", "amount", "change_pct"]]
        except Exception as e:
            logger.error(f"BaoStock fetch_daily_klines failed for {code}: {e}")
            return pd.DataFrame()
        finally:
            bs.logout()

    def fetch_north_flow(self, days: int = 30) -> pd.DataFrame:
        return pd.DataFrame()

    def fetch_sector_daily(self) -> pd.DataFrame:
        return pd.DataFrame()

    def _fetch_klines_for_sentiment(self) -> pd.DataFrame:
        import baostock as bs
        today = date.today()
        yesterday = today - timedelta(days=7)
        bs.login()
        try:
            stock_df = self.fetch_stock_basic_list()
            if stock_df.empty:
                return pd.DataFrame()
            codes = stock_df["code"].head(500).tolist()
            records = []
            today_str = today.strftime("%Y-%m-%d")
            for code in codes:
                market = "sh" if code.startswith("6") else "sz"
                bs_code = f"{market}.{code}"
                rs = bs.query_history_k_data_plus(
                    bs_code, "date,pctChg",
                    start_date=yesterday.strftime("%Y-%m-%d"),
                    end_date=today_str,
                    frequency="d", adjustflag="2",
                )
                while rs.error_code == "0" and rs.next():
                    row = rs.get_row_data()
                    if row[0] == today_str:
                        pct = float(row[1]) if row[1] else 0
                        records.append({"code": code, "change_pct": pct})
                        break
            return pd.DataFrame(records)
        except Exception as e:
            logger.error(f"BaoStock sentiment klines failed: {e}")
            return pd.DataFrame()
        finally:
            bs.logout()

    def fetch_market_sentiment(self) -> dict:
        df = self._fetch_klines_for_sentiment()
        if df.empty or "change_pct" not in df.columns:
            return {}
        up = int((df["change_pct"] > 0).sum())
        down = int((df["change_pct"] < 0).sum())
        flat = int((df["change_pct"] == 0).sum())
        limit_up = int((df["change_pct"] >= 9.9).sum())
        limit_down = int((df["change_pct"] <= -9.9).sum())
        return {
            "trade_date": date.today(),
            "up_count": up, "down_count": down, "flat_count": flat,
            "limit_up": limit_up, "limit_down": limit_down,
        }
