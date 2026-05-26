from dataclasses import dataclass


@dataclass
class RiskConfig:
    stop_loss_pct: float = -0.05
    take_profit_pct: float = 0.12
    trailing_trigger: float = 0.07
    trailing_drawdown: float = 0.03
    max_hold_days: int = 5


def check_sell_signals(position: dict, config: RiskConfig) -> list[dict]:
    signals = []
    buy_price = position["buy_price"]
    current_price = position["current_price"]
    highest_price = position["highest_price"]
    hold_days = position["hold_days"]
    if current_price is None or buy_price <= 0:
        return signals
    pnl_pct = (current_price - buy_price) / buy_price

    if pnl_pct <= config.stop_loss_pct:
        signals.append({
            "rule": "stop_loss",
            "priority": 1,
            "reason": f"浮亏 {pnl_pct:.1%}，触发止损线 {config.stop_loss_pct:.0%}",
            "urgency": "immediate",
        })
        return signals

    highest_gain = (highest_price - buy_price) / buy_price
    if highest_gain >= config.trailing_trigger:
        drawdown_from_high = (highest_price - current_price) / highest_price
        if drawdown_from_high >= config.trailing_drawdown:
            signals.append({
                "rule": "trailing_stop",
                "priority": 2,
                "reason": f"最高盈利 {highest_gain:.1%}，从高点回撤 {drawdown_from_high:.1%}",
                "urgency": "immediate",
            })
            return signals

    if pnl_pct >= config.take_profit_pct:
        signals.append({
            "rule": "take_profit",
            "priority": 3,
            "reason": f"浮盈 {pnl_pct:.1%}，达到止盈目标 {config.take_profit_pct:.0%}",
            "urgency": "suggest",
        })

    if hold_days > config.max_hold_days and pnl_pct < config.take_profit_pct:
        signals.append({
            "rule": "time_stop",
            "priority": 4,
            "reason": f"持有 {hold_days} 天，超过最大持有期 {config.max_hold_days} 天",
            "urgency": "suggest",
        })

    return signals
