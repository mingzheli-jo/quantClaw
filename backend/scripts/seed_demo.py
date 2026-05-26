"""
QuantClaw Demo Data Seeder — synthetic data for UI preview.
Run: cd backend && python -m scripts.seed_demo
"""
import sys
import os
import random
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DATABASE_URL", "postgresql://cptop:cptop@localhost:5432/quantclaw")
os.environ.setdefault("SECRET_KEY", "dev-secret")
os.environ.setdefault("ADMIN_PASSWORD", "admin123")

from app.database import Base, engine, SessionLocal
from app.models import (
    User, StockBasic, StockDaily, NorthFlow, SectorDaily,
    MarketSentiment, Signal, Position, TradeLog,
)
from app.services.data.indicators import calc_ma, calc_macd, calc_volume_ratio
from app.utils.security import hash_password
import pandas as pd

random.seed(42)

STOCKS = [
    ("600000", "浦发银行", "银行", "sh"),
    ("600036", "招商银行", "银行", "sh"),
    ("600519", "贵州茅台", "白酒", "sh"),
    ("601318", "中国平安", "保险", "sh"),
    ("600276", "恒瑞医药", "医药", "sh"),
    ("600887", "伊利股份", "食品饮料", "sh"),
    ("601012", "隆基绿能", "光伏", "sh"),
    ("600309", "万华化学", "化工", "sh"),
    ("600585", "海螺水泥", "建材", "sh"),
    ("601888", "中国中免", "零售", "sh"),
    ("000001", "平安银行", "银行", "sz"),
    ("000002", "万科A", "房地产", "sz"),
    ("000333", "美的集团", "家电", "sz"),
    ("000651", "格力电器", "家电", "sz"),
    ("000858", "五粮液", "白酒", "sz"),
    ("000725", "京东方A", "面板", "sz"),
    ("002415", "海康威视", "安防", "sz"),
    ("002594", "比亚迪", "新能源车", "sz"),
    ("002714", "牧原股份", "畜牧", "sz"),
    ("002475", "立讯精密", "消费电子", "sz"),
    ("300750", "宁德时代", "锂电池", "sz"),
    ("300059", "东方财富", "券商", "sz"),
    ("300015", "爱尔眼科", "医疗", "sz"),
    ("300122", "智飞生物", "疫苗", "sz"),
    ("300760", "迈瑞医疗", "医疗器械", "sz"),
    ("300274", "阳光电源", "光伏", "sz"),
    ("600031", "三一重工", "机械", "sh"),
    ("601166", "兴业银行", "银行", "sh"),
    ("600050", "中国联通", "通信", "sh"),
    ("601398", "工商银行", "银行", "sh"),
    ("000568", "泸州老窖", "白酒", "sz"),
    ("002304", "洋河股份", "白酒", "sz"),
    ("300124", "汇川技术", "工控", "sz"),
    ("002049", "紫光国微", "芯片", "sz"),
    ("600588", "用友网络", "软件", "sh"),
    ("601899", "紫金矿业", "矿业", "sh"),
    ("600900", "长江电力", "电力", "sh"),
    ("601668", "中国建筑", "建筑", "sh"),
    ("000063", "中兴通讯", "通信", "sz"),
    ("002230", "科大讯飞", "AI", "sz"),
    ("300033", "同花顺", "金融IT", "sz"),
    ("300408", "三环集团", "电子元件", "sz"),
    ("600745", "闻泰科技", "半导体", "sh"),
    ("603259", "药明康德", "CXO", "sh"),
    ("688981", "中芯国际", "半导体", "sh"),
    ("600809", "山西汾酒", "白酒", "sh"),
    ("601985", "中国核电", "核电", "sh"),
    ("002371", "北方华创", "半导体设备", "sz"),
    ("300496", "中科创达", "软件", "sz"),
    ("600436", "片仔癀", "中药", "sh"),
]

INDUSTRIES = list(set(s[2] for s in STOCKS))


def _build_trade_dates(n: int) -> list[date]:
    """Return the last n business days up to and including today."""
    trade_dates: list[date] = []
    d = date.today()
    while len(trade_dates) < n:
        if d.weekday() < 5:
            trade_dates.append(d)
        d -= timedelta(days=1)
    trade_dates.reverse()
    return trade_dates


def _gen_klines(base_price: float, days: int) -> list[dict]:
    """Generate a realistic random-walk K-line series."""
    rows = []
    price = base_price
    for _ in range(days):
        change = random.gauss(0.001, 0.025)
        price = max(price * (1 + change), 1.0)
        high = price * (1 + random.uniform(0, 0.03))
        low = price * (1 - random.uniform(0, 0.03))
        open_ = low + random.uniform(0, 1) * (high - low)
        vol = int(random.uniform(5_000_000, 50_000_000))
        rows.append({
            "open": round(open_, 2),
            "high": round(high, 2),
            "low": round(low, 2),
            "close": round(price, 2),
            "volume": vol,
            "amount": round(price * vol, 2),
            "change_pct": round(change * 100, 2),
        })
    return rows


def seed_demo() -> None:
    print("=== QuantClaw Demo Data Seeder ===")
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        # Admin user
        if not db.query(User).filter(User.username == "admin").first():
            db.add(User(username="admin", hashed_password=hash_password("admin123")))
            db.commit()
            print("Admin user created")
        else:
            print("Admin user already exists")

        # Clear old demo data in dependency order
        db.query(TradeLog).delete()
        db.query(Position).delete()
        db.query(Signal).delete()
        db.query(StockDaily).delete()
        db.query(NorthFlow).delete()
        db.query(SectorDaily).delete()
        db.query(MarketSentiment).delete()
        db.query(StockBasic).delete()
        db.commit()
        print("Cleared old data")

        today = date.today()
        trade_dates = _build_trade_dates(60)

        # --- Stock basics ---
        for code, name, industry, market in STOCKS:
            db.add(StockBasic(
                code=code, name=name, industry=industry, market=market,
                list_date=date(2015, 1, 1), is_st=False,
            ))
        db.commit()
        print(f"Inserted {len(STOCKS)} stocks")

        # --- K-lines (60 days × 50 stocks) ---
        kline_count = 0
        for code, _name, _industry, _market in STOCKS:
            base = random.uniform(8.0, 42.0)
            klines = _gen_klines(base, 60)
            for i, kl in enumerate(klines):
                db.add(StockDaily(code=code, trade_date=trade_dates[i], **kl))
                kline_count += 1
        db.commit()
        print(f"Inserted {kline_count} K-line rows")

        # --- North flow (30 days) ---
        for td in trade_dates[-30:]:
            net = random.uniform(-5e9, 8e9)
            db.add(NorthFlow(
                trade_date=td,
                buy_amount=round(abs(net) if net > 0 else 0, 2),
                sell_amount=round(abs(net) if net < 0 else 0, 2),
                net_amount=round(net, 2),
            ))
        db.commit()
        print("Inserted 30 days of north flow")

        # --- Sectors (today) ---
        for ind in INDUSTRIES:
            db.add(SectorDaily(
                sector=ind, trade_date=today,
                change_pct=round(random.uniform(-3.0, 5.0), 2),
                volume=random.randint(1_000_000, 100_000_000),
                net_fund_flow=round(random.uniform(-5e8, 5e8), 2),
            ))
        db.commit()
        print(f"Inserted {len(INDUSTRIES)} sector records")

        # --- Market sentiment (today) ---
        up = random.randint(2000, 3500)
        down = random.randint(1000, 2500)
        db.add(MarketSentiment(
            trade_date=today,
            up_count=up,
            down_count=down,
            flat_count=random.randint(100, 300),
            limit_up=random.randint(30, 80),
            limit_down=random.randint(5, 20),
            sh_index_pct=round(random.uniform(-1.0, 2.0), 2),
            sz_index_pct=round(random.uniform(-1.0, 2.5), 2),
            cyb_index_pct=round(random.uniform(-1.5, 3.0), 2),
        ))
        db.commit()
        print("Inserted market sentiment")

        # --- Signals (today) ---
        signals_count = 0
        for code, name, _industry, _market in STOCKS:
            klines = (
                db.query(StockDaily)
                .filter(StockDaily.code == code)
                .order_by(StockDaily.trade_date)
                .all()
            )
            if len(klines) < 20:
                continue

            close_series = pd.Series([k.close for k in klines])
            vol_series = pd.Series([k.volume for k in klines])
            latest = klines[-1]

            # Technical scoring
            tech = 0
            ma5 = calc_ma(close_series, 5).iloc[-1]
            ma10 = calc_ma(close_series, 10).iloc[-1]
            ma20 = calc_ma(close_series, 20).iloc[-1]
            if ma5 > ma10 > ma20:
                tech += 10
            elif ma5 > ma10:
                tech += 5

            _dif, _dea, hist = calc_macd(close_series)
            if hist.iloc[-1] > 0:
                tech += 8 if hist.iloc[-2] <= 0 else 4

            vr = calc_volume_ratio(vol_series, 20)
            if vr >= 1.5:
                tech += 5

            if latest.close >= close_series.tail(20).max():
                tech += 5
            tech = min(tech, 40)

            fund = random.randint(5, 25)
            momentum = random.randint(3, 18)
            sentiment_sc = random.randint(2, 9)
            total = tech + fund + momentum + sentiment_sc

            reasons = []
            if ma5 > ma10 > ma20:
                reasons.append("均线多头排列")
            if hist.iloc[-1] > 0 and hist.iloc[-2] <= 0:
                reasons.append("MACD金叉")
            if vr >= 1.5:
                reasons.append(f"放量({vr:.1f}倍)")
            if fund > 15:
                reasons.append("北向资金流入")
            if momentum > 12:
                reasons.append("强于板块")
            reason = " + ".join(reasons) if reasons else "综合评分达标"

            db.add(Signal(
                code=code, stock_name=name, trade_date=today,
                direction="buy", score=total,
                tech_score=tech, fund_score=fund,
                momentum_score=momentum, sentiment_score=sentiment_sc,
                reason=reason, close_price=latest.close,
                suggested_buy_low=round(latest.close * 0.99, 2),
                suggested_buy_high=round(latest.close * 1.01, 2),
                stop_loss_price=round(latest.close * 0.95, 2),
                target_price=round(latest.close * 1.12, 2),
            ))
            signals_count += 1
        db.commit()
        print(f"Generated {signals_count} signals")

        # --- Demo open position (贵州茅台) ---
        demo_code, demo_name = STOCKS[2][0], STOCKS[2][1]
        recent_klines = (
            db.query(StockDaily)
            .filter(StockDaily.code == demo_code)
            .order_by(StockDaily.trade_date.desc())
            .limit(5)
            .all()
        )
        if recent_klines:
            buy_price = recent_klines[-1].close   # oldest of the 5
            current_price = recent_klines[0].close
            highest = max(k.close for k in recent_klines)
            buy_date = trade_dates[-3]

            pos = Position(
                code=demo_code, stock_name=demo_name,
                buy_date=buy_date, buy_price=buy_price, shares=100,
                cost_amount=round(buy_price * 100, 2),
                stop_loss_price=round(buy_price * 0.95, 2),
                take_profit_price=round(buy_price * 1.12, 2),
                highest_price=highest,
                current_price=current_price,
                status="open", executed=True,
            )
            db.add(pos)
            db.flush()  # get pos.id

            db.add(TradeLog(
                code=demo_code, stock_name=demo_name,
                trade_date=buy_date, action="buy",
                price=buy_price, shares=100,
                amount=round(buy_price * 100, 2),
                fee=5.0, reason="买入建仓",
                position_id=pos.id,
            ))
            db.commit()
            print(f"Created demo position: {demo_name} @ {buy_price:.2f}")

        # --- Summary ---
        print("\n=== Demo data ready! ===")
        print(f"  Stocks:     {db.query(StockBasic).count()}")
        print(f"  K-lines:    {db.query(StockDaily).count()}")
        print(f"  Signals:    {db.query(Signal).count()}")
        print(f"  Sectors:    {db.query(SectorDaily).count()}")
        print(f"  North flow: {db.query(NorthFlow).count()}")
        print(f"  Positions:  {db.query(Position).filter(Position.status == 'open').count()}")

    finally:
        db.close()


if __name__ == "__main__":
    seed_demo()
