import logging
from datetime import datetime, time, date
from typing import Any

import httpx

from app.scheduler.trading_calendar import is_trading_day

logger = logging.getLogger(__name__)

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://quote.eastmoney.com/",
}
_TIMEOUT = 10


def _get(url: str, params: dict | None = None) -> dict | None:
    try:
        resp = httpx.get(url, params=params, headers=_HEADERS, timeout=_TIMEOUT)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        logger.warning(f"Realtime fetch failed: {e}")
        return None


class RealtimeService:
    def __init__(self):
        self._indices: list[dict] = []
        self._north_flow: dict = {}
        self._sectors_top: list[dict] = []
        self._sectors_fund_top: list[dict] = []
        self._positions: list[dict] = []
        self._last_refresh: datetime | None = None
        self._fail_count: int = 0

    def _is_trading_time(self, t: time | None = None) -> bool:
        if t is None:
            t = datetime.now().time()
        morning = time(9, 15) <= t <= time(11, 35)
        afternoon = time(12, 55) <= t <= time(15, 5)
        return morning or afternoon

    def should_refresh(self) -> bool:
        if not is_trading_day():
            return False
        if not self._is_trading_time():
            return False
        if self._fail_count >= 5:
            return False
        return True

    def refresh_indices(self) -> None:
        url = "http://push2.eastmoney.com/api/qt/ulist.np/get"
        params = {
            "fltt": "2", "invt": "2",
            "fields": "f2,f3,f4,f6,f12,f14",
            "secids": "1.000001,0.399001,0.399006",
        }
        data = _get(url, params)
        if not data or "data" not in data or not data["data"]:
            self._fail_count += 1
            return
        rows = data["data"].get("diff", [])
        self._indices = [
            {
                "code": r.get("f12", ""),
                "name": r.get("f14", ""),
                "price": float(r.get("f2", 0)),
                "change_pct": float(r.get("f3", 0)),
                "change_amount": float(r.get("f4", 0)),
                "turnover": float(r.get("f6", 0)),
            }
            for r in rows
        ]
        self._fail_count = 0

    def refresh_north_flow(self) -> None:
        url = "http://push2.eastmoney.com/api/qt/kamt.rtmin/get"
        params = {"fields1": "f1,f2,f3", "fields2": "f51,f52,f54,f56"}
        data = _get(url, params)
        if not data or "data" not in data or not data["data"]:
            return
        s2n = data["data"].get("s2n", [])
        if s2n:
            latest = s2n[-1]
            parts = latest.split(",")
            if len(parts) >= 4:
                net = float(parts[1]) if parts[1] != "-" else 0
                self._north_flow = {
                    "time": parts[0],
                    "net_amount": net,
                    "sh_net": float(parts[2]) if parts[2] != "-" else 0,
                    "sz_net": float(parts[3]) if parts[3] != "-" else 0,
                }
        timeline = []
        if s2n:
            for line in s2n:
                parts = line.split(",")
                if len(parts) >= 2 and parts[1] != "-":
                    timeline.append({"time": parts[0], "net": float(parts[1])})
        self._north_flow["timeline"] = timeline

    def refresh_sectors(self) -> None:
        url = "http://push2.eastmoney.com/api/qt/clist/get"
        params_gain = {
            "pn": "1", "pz": "10", "po": "1", "np": "1",
            "fltt": "2", "invt": "2", "fid": "f3",
            "fs": "m:90+t:2", "fields": "f3,f14,f62,f104,f105",
        }
        data = _get(url, params_gain)
        if data and data.get("data"):
            self._sectors_top = [
                {
                    "name": r.get("f14", ""),
                    "change_pct": float(r.get("f3", 0)),
                    "net_fund_flow": float(r.get("f62", 0)) if r.get("f62") and r.get("f62") != "-" else 0,
                    "up_count": int(r.get("f104", 0)),
                    "down_count": int(r.get("f105", 0)),
                }
                for r in data["data"].get("diff", [])
            ]
        params_fund = {
            "pn": "1", "pz": "10", "po": "1", "np": "1",
            "fltt": "2", "invt": "2", "fid": "f62",
            "fs": "m:90+t:2", "fields": "f3,f14,f62",
        }
        data = _get(url, params_fund)
        if data and data.get("data"):
            self._sectors_fund_top = [
                {
                    "name": r.get("f14", ""),
                    "change_pct": float(r.get("f3", 0)),
                    "net_fund_flow": float(r.get("f62", 0)) if r.get("f62") and r.get("f62") != "-" else 0,
                }
                for r in data["data"].get("diff", [])
            ]

    def refresh_positions(self, position_codes: list[str]) -> None:
        if not position_codes:
            self._positions = []
            return
        secids = ",".join(
            f"{'1' if c.startswith('6') else '0'}.{c}" for c in position_codes
        )
        url = "http://push2.eastmoney.com/api/qt/ulist.np/get"
        params = {
            "fltt": "2", "invt": "2",
            "fields": "f2,f3,f4,f12,f14",
            "secids": secids,
        }
        data = _get(url, params)
        if not data or "data" not in data or not data["data"]:
            return
        self._positions = [
            {
                "code": r.get("f12", ""),
                "name": r.get("f14", ""),
                "price": float(r.get("f2", 0)),
                "change_pct": float(r.get("f3", 0)),
            }
            for r in data["data"].get("diff", [])
        ]

    def refresh_all(self, position_codes: list[str] | None = None) -> None:
        if not self.should_refresh():
            return
        self.refresh_indices()
        self.refresh_north_flow()
        self.refresh_sectors()
        self.refresh_positions(position_codes or [])
        self._last_refresh = datetime.now()
        logger.info("Realtime data refreshed")

    def get_indices(self) -> list[dict]:
        return self._indices

    def get_north_flow(self) -> dict:
        return self._north_flow

    def get_sectors(self) -> dict:
        return {"gainers": self._sectors_top, "fund_inflow": self._sectors_fund_top}

    def get_positions(self) -> list[dict]:
        return self._positions

    def get_summary(self) -> dict:
        return {
            "indices": self._indices,
            "north_flow": self._north_flow,
            "sectors": {"gainers": self._sectors_top[:5], "fund_inflow": self._sectors_fund_top[:5]},
            "is_trading": self._is_trading_time(),
            "last_refresh": self._last_refresh.isoformat() if self._last_refresh else None,
        }


realtime_service = RealtimeService()
