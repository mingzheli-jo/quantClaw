import logging
from datetime import date
from dataclasses import dataclass

import pandas as pd
import numpy as np

from app.services.data.indicators import calc_volume_ratio
from app.services.strategy.scoring import score_technical, score_fund, score_momentum, score_sentiment, compute_total_score

logger = logging.getLogger(__name__)


@dataclass
class _Position:
    code: str
    name: str
    buy_date: date
    buy_price: float
    shares: int
    highest_price: float = 0.0

    def __post_init__(self):
        self.highest_price = self.buy_price


class BacktestEngine:
    def __init__(
        self,
        stocks_df: pd.DataFrame,
        kline_df: pd.DataFrame,
        strategy_config: dict,
        start_date: date,
        end_date: date,
        initial_capital: float = 50000,
    ):
        self.stocks_df = stocks_df
        self.kline_df = kline_df
        self.config = strategy_config
        self.start_date = start_date
        self.end_date = end_date
        self.initial_capital = initial_capital

        self.cash = initial_capital
        self.positions: list[_Position] = []
        self.trades: list[dict] = []
        self.daily_values: list[dict] = []

    def _get_trade_dates(self) -> list[date]:
        dates = sorted(self.kline_df["trade_date"].unique())
        return [d for d in dates if self.start_date <= d <= self.end_date]

    def _get_day_data(self, trade_date: date) -> pd.DataFrame:
        return self.kline_df[self.kline_df["trade_date"] == trade_date]

    def _get_kline_window(self, code: str, trade_date: date, window: int = 30) -> pd.DataFrame:
        stock_data = self.kline_df[
            (self.kline_df["code"] == code) & (self.kline_df["trade_date"] <= trade_date)
        ].sort_values("trade_date").tail(window)
        return stock_data

    def _score_stock(self, code: str, trade_date: date) -> int | None:
        klines = self._get_kline_window(code, trade_date, 30)
        if len(klines) < 20:
            return None
        kline_df = klines[["open", "high", "low", "close", "volume"]].reset_index(drop=True)

        tech_score, _ = score_technical(kline_df)

        vol_ratio = calc_volume_ratio(kline_df["volume"], 20) if len(kline_df) >= 21 else 1.0
        fund_score, _ = score_fund({
            "north_net_3d": 0, "main_net": 0,
            "super_large_pct": 0, "volume_ratio": vol_ratio,
        })

        pct_5d = 0
        if len(klines) >= 5:
            pct_5d = (klines.iloc[-1]["close"] - klines.iloc[-5]["close"]) / klines.iloc[-5]["close"] * 100
        momentum_score, _ = score_momentum({
            "pct_5d": pct_5d,
            "relative_strength": pct_5d,
            "is_20d_high": klines.iloc[-1]["close"] >= klines["close"].tail(20).max(),
        })

        sentiment_score, _ = score_sentiment({
            "sector_rank_pct": 50, "limit_up": 40,
            "limit_down": 15, "sector_net_flow": 0,
        })

        score_cfg = self.config.get("score_config")
        total = compute_total_score(
            {"tech": tech_score, "fund": fund_score, "momentum": momentum_score, "sentiment": sentiment_score},
            score_cfg,
        )
        return total

    def _check_sell(self, pos: _Position, current_price: float, trade_date: date) -> str | None:
        risk = self.config.get("risk_config", {})
        pnl_pct = (current_price - pos.buy_price) / pos.buy_price

        if pnl_pct <= risk.get("stop_loss_pct", -0.05):
            return "stop_loss"
        if pnl_pct >= risk.get("take_profit_pct", 0.12):
            return "take_profit"

        hold_days = (trade_date - pos.buy_date).days
        if hold_days >= risk.get("max_hold_days", 5):
            return "max_hold_days"

        if pos.highest_price > pos.buy_price:
            gain_from_buy = (pos.highest_price - pos.buy_price) / pos.buy_price
            if gain_from_buy >= risk.get("trailing_trigger", 0.07):
                drawdown = (pos.highest_price - current_price) / pos.highest_price
                if drawdown >= risk.get("trailing_drawdown", 0.03):
                    return "trailing_stop"
        return None

    def _portfolio_value(self, day_data: pd.DataFrame) -> float:
        price_map = dict(zip(day_data["code"], day_data["close"]))
        stock_value = sum(
            price_map.get(p.code, p.buy_price) * p.shares for p in self.positions
        )
        return self.cash + stock_value

    def run(self) -> dict:
        trade_dates = self._get_trade_dates()
        if not trade_dates:
            return {"summary": {}, "daily_values": [], "trades": []}

        signal_cfg = self.config.get("signal_config", {})
        max_positions = signal_cfg.get("top_n", 3)
        peak_value = self.initial_capital
        max_drawdown = 0.0

        for td in trade_dates:
            day_data = self._get_day_data(td)
            if day_data.empty:
                continue
            price_map = dict(zip(day_data["code"], day_data["close"]))

            for pos in self.positions:
                cp = price_map.get(pos.code, pos.buy_price)
                if cp > pos.highest_price:
                    pos.highest_price = cp

            to_sell = []
            for pos in self.positions:
                cp = price_map.get(pos.code)
                if cp is None:
                    continue
                reason = self._check_sell(pos, cp, td)
                if reason:
                    to_sell.append((pos, cp, reason))

            for pos, sell_price, reason in to_sell:
                pnl = (sell_price - pos.buy_price) * pos.shares
                self.cash += sell_price * pos.shares
                self.trades.append({
                    "code": pos.code, "name": pos.name,
                    "buy_date": pos.buy_date.isoformat(),
                    "buy_price": round(pos.buy_price, 2),
                    "sell_date": td.isoformat(),
                    "sell_price": round(sell_price, 2),
                    "shares": pos.shares,
                    "pnl": round(pnl, 2),
                    "pnl_pct": round((sell_price - pos.buy_price) / pos.buy_price * 100, 2),
                    "hold_days": (td - pos.buy_date).days,
                    "sell_reason": reason,
                })
                self.positions.remove(pos)

            if len(self.positions) < max_positions:
                held_codes = {p.code for p in self.positions}
                available_codes = set(price_map.keys()) - held_codes
                scored = []
                for code in available_codes:
                    s = self._score_stock(code, td)
                    if s is not None and s >= signal_cfg.get("min_score", 65):
                        name_row = self.stocks_df[self.stocks_df["code"] == code]
                        name = name_row.iloc[0]["name"] if not name_row.empty else code
                        scored.append((code, name, s, price_map[code]))
                scored.sort(key=lambda x: x[2], reverse=True)

                slots = max_positions - len(self.positions)
                bought = 0
                for code, name, score, buy_price in scored[:slots]:
                    if buy_price <= 0 or self.cash <= 0:
                        continue
                    per_position = self.cash / max(slots - bought, 1)
                    shares = int(per_position / buy_price / 100) * 100
                    if shares <= 0:
                        continue
                    cost = buy_price * shares
                    if cost > self.cash:
                        continue
                    self.cash -= cost
                    self.positions.append(_Position(
                        code=code, name=name,
                        buy_date=td, buy_price=buy_price, shares=shares,
                    ))
                    bought += 1

            portfolio_val = self._portfolio_value(day_data)
            if portfolio_val > peak_value:
                peak_value = portfolio_val
            dd = (peak_value - portfolio_val) / peak_value if peak_value > 0 else 0
            if dd > max_drawdown:
                max_drawdown = dd

            self.daily_values.append({
                "date": td.isoformat(),
                "value": round(portfolio_val, 2),
            })

        final_value = self.daily_values[-1]["value"] if self.daily_values else self.initial_capital
        total_return = (final_value - self.initial_capital) / self.initial_capital
        trading_days = len(self.daily_values)
        annual_return = total_return * (250 / trading_days) if trading_days > 0 else 0

        wins = [t for t in self.trades if t["pnl"] > 0]
        losses = [t for t in self.trades if t["pnl"] <= 0]
        win_rate = len(wins) / len(self.trades) if self.trades else 0
        avg_win = sum(t["pnl"] for t in wins) / len(wins) if wins else 0
        avg_loss = abs(sum(t["pnl"] for t in losses) / len(losses)) if losses else 1
        profit_loss_ratio = avg_win / avg_loss if avg_loss > 0 else 0

        if len(self.daily_values) >= 2:
            values = [d["value"] for d in self.daily_values]
            returns = [(values[i] - values[i - 1]) / values[i - 1] for i in range(1, len(values))]
            avg_ret = np.mean(returns)
            std_ret = np.std(returns)
            sharpe = (avg_ret / std_ret) * np.sqrt(250) if std_ret > 0 else 0
        else:
            sharpe = 0

        summary = {
            "total_return": round(total_return, 4),
            "annual_return": round(annual_return, 4),
            "max_drawdown": round(-max_drawdown, 4),
            "win_rate": round(win_rate, 4),
            "sharpe_ratio": round(float(sharpe), 2),
            "profit_loss_ratio": round(profit_loss_ratio, 2),
            "total_trades": len(self.trades),
            "final_value": round(final_value, 2),
        }
        return {"summary": summary, "daily_values": self.daily_values, "trades": self.trades}
