import json
import logging
from datetime import date, datetime

from app.config import settings
from app.database import SessionLocal
from app.models.market import MarketSentiment, NorthFlow as NorthFlowModel, SectorDaily as SectorDailyModel
from app.models.signal import Signal
from app.models.stock import StockBasic, StockDaily
from app.models.system import SchedulerLog
from app.scheduler.trading_calendar import is_trading_day
from app.services.data.smart_fetcher import SmartFetcher
from app.services.data.providers.eastmoney import EastmoneyProvider
from app.services.data.providers.baostock_provider import BaostockProvider
from app.services.data.maintenance import purge_old_data, update_stock_basic
from app.services.notify.feishu import FeishuBot
from app.services.notify.messages import build_alert_card, build_post_market_card, build_pre_market_card
from app.services.position.manager import get_active_positions

logger = logging.getLogger(__name__)


def _get_fetcher() -> SmartFetcher:
    return SmartFetcher(primary=EastmoneyProvider(), fallback=BaostockProvider())


def _log_job(
    db,
    job_name: str,
    status: str,
    message: str = "",
    started_at: datetime | None = None,
    records_collected: int = 0,
    details: str | None = None,
    error_message: str | None = None,
):
    db.add(
        SchedulerLog(
            job_name=job_name,
            status=status,
            message=message,
            records_collected=records_collected,
            details=details,
            error_message=error_message,
            started_at=started_at or datetime.now(),
            finished_at=datetime.now(),
        )
    )
    db.commit()


def job_pre_market():
    if not is_trading_day():
        return
    started = datetime.now()
    db = SessionLocal()
    try:
        positions = get_active_positions(db)
        pos_data = [
            {
                "stock_name": p.stock_name,
                "code": p.code,
                "buy_price": p.buy_price,
                "stop_loss": p.stop_loss_price,
                "take_profit": p.take_profit_price,
            }
            for p in positions
        ]
        card = build_pre_market_card(date.today(), pos_data)
        bot = FeishuBot(settings.feishu_webhook_url)
        bot.send_card(card)
        _log_job(db, "pre_market", "success", started_at=started)
    except Exception as e:
        logger.error(f"Pre-market job failed: {e}")
        _log_job(db, "pre_market", "failed", str(e), started_at=started)
    finally:
        db.close()


def job_intraday_check():
    if not is_trading_day():
        return
    started = datetime.now()
    db = SessionLocal()
    try:
        positions = get_active_positions(db)
        if not positions:
            _log_job(db, "intraday_check", "success", "No positions", started_at=started)
            return
        fetcher = _get_fetcher()
        spot_df = fetcher.fetch_stock_basic_list()
        if spot_df.empty:
            return
        price_map = dict(zip(spot_df["code"], spot_df["price"]))
        bot = FeishuBot(settings.feishu_webhook_url)
        from app.services.position.risk import check_sell_signals, RiskConfig

        cfg = RiskConfig()
        for pos in positions:
            live_price = price_map.get(pos.code)
            if live_price is None:
                continue
            pos.current_price = live_price
            if live_price > pos.highest_price:
                pos.highest_price = live_price
            hold_days = (date.today() - pos.buy_date).days
            signals = check_sell_signals(
                {
                    "buy_price": pos.buy_price,
                    "current_price": live_price,
                    "highest_price": pos.highest_price,
                    "hold_days": hold_days,
                },
                cfg,
            )
            if any(s["urgency"] == "immediate" for s in signals):
                msg = f"⚠️ {pos.stock_name} {pos.code} 触发卖出信号: {signals[0]['reason']}"
                bot.send_card(build_alert_card("盘中异动", msg, "warning"))
        db.commit()
        _log_job(db, "intraday_check", "success", started_at=started)
    except Exception as e:
        logger.error(f"Intraday check failed: {e}")
        _log_job(db, "intraday_check", "failed", str(e), started_at=started)
    finally:
        db.close()


def job_post_market_collect():
    if not is_trading_day():
        return
    started = datetime.now()
    db = SessionLocal()
    try:
        fetcher = _get_fetcher()
        counts = {"stocks": 0, "klines": 0, "north": 0, "sectors": 0, "sentiment": 0}
        errors = []

        stock_list = fetcher.fetch_stock_basic_list()
        if stock_list.empty:
            raise RuntimeError("Failed to fetch stock list")
        codes = stock_list["code"].tolist()
        counts["stocks"] = len(codes)

        today_str = date.today().strftime("%Y%m%d")
        kline_df = fetcher.fetch_daily_klines_batch(codes, start_date=today_str, end_date=today_str)
        if not kline_df.empty:
            for _, row in kline_df.iterrows():
                existing = (
                    db.query(StockDaily)
                    .filter(StockDaily.code == row["code"], StockDaily.trade_date == row["trade_date"])
                    .first()
                )
                if not existing:
                    db.add(StockDaily(**row.to_dict()))
                    counts["klines"] += 1
            db.commit()

        north_df = fetcher.fetch_north_flow(days=5)
        if not north_df.empty:
            for _, row in north_df.iterrows():
                existing = (
                    db.query(NorthFlowModel)
                    .filter(NorthFlowModel.trade_date == row["trade_date"])
                    .first()
                )
                if not existing:
                    db.add(
                        NorthFlowModel(
                            trade_date=row["trade_date"],
                            buy_amount=row["buy_amount"],
                            sell_amount=row["sell_amount"],
                            net_amount=row["net_amount"],
                        )
                    )
                    counts["north"] += 1
            db.commit()
        else:
            errors.append("north_flow: no data")

        sector_df = fetcher.fetch_sector_daily()
        if not sector_df.empty:
            for _, row in sector_df.iterrows():
                existing = (
                    db.query(SectorDailyModel)
                    .filter(
                        SectorDailyModel.sector == row["sector"],
                        SectorDailyModel.trade_date == row["trade_date"],
                    )
                    .first()
                )
                if not existing:
                    db.add(
                        SectorDailyModel(
                            sector=row["sector"],
                            trade_date=row["trade_date"],
                            change_pct=row["change_pct"],
                            volume=row.get("volume", 0),
                            net_fund_flow=row.get("net_fund_flow", 0),
                        )
                    )
                    counts["sectors"] += 1
            db.commit()
        else:
            errors.append("sector_daily: no data")

        sentiment = fetcher.fetch_market_sentiment()
        if sentiment:
            existing = (
                db.query(MarketSentiment)
                .filter(MarketSentiment.trade_date == sentiment["trade_date"])
                .first()
            )
            if not existing:
                db.add(MarketSentiment(**sentiment))
                db.commit()
                counts["sentiment"] = 1
        else:
            errors.append("market_sentiment: no data")

        status = "partial" if errors else "success"
        _log_job(
            db,
            "post_market_collect",
            status,
            f"Collected {len(codes)} stocks",
            started_at=started,
            records_collected=sum(counts.values()),
            details=json.dumps({"counts": counts, "errors": errors}),
        )
        if errors:
            FeishuBot(settings.feishu_webhook_url).send_card(
                build_alert_card("数据采集部分失败", "; ".join(errors), "warning")
            )
    except Exception as e:
        logger.error(f"Post-market collect failed: {e}")
        _log_job(db, "post_market_collect", "failed", str(e), started_at=started)
        FeishuBot(settings.feishu_webhook_url).send_card(build_alert_card("数据采集失败", str(e), "error"))
    finally:
        db.close()


def job_post_market_analyze():
    if not is_trading_day():
        return
    started = datetime.now()
    db = SessionLocal()
    try:
        import pandas as pd

        from app.services.strategy.filters import hard_filter
        from app.services.strategy.scoring import score_technical, score_fund, score_momentum, score_sentiment, compute_total_score
        from app.services.strategy.signal_generator import select_top_n, apply_concentration_control, build_signal_reason
        from app.services.data.indicators import calc_volume_ratio
        from app.services.position.risk import check_sell_signals, RiskConfig
        from app.learn.indicators import INDICATOR_GUIDES

        today = date.today()
        from app.models.strategy import StrategyTemplate
        active = db.query(StrategyTemplate).filter(StrategyTemplate.is_active == True).first()
        if not active:
            logger.warning("No active strategy template, using defaults")
            filter_cfg = {"min_amount_20d": 50_000_000, "max_price": 50, "min_list_days": 60}
            score_cfg = {"tech_weight": 0.4, "fund_weight": 0.3, "momentum_weight": 0.2, "sentiment_weight": 0.1}
            signal_cfg = {"min_score": 65, "top_n": 3, "concentration_control": True}
            risk_cfg = {"stop_loss_pct": -0.05, "take_profit_pct": 0.12, "trailing_trigger": 0.07, "trailing_drawdown": 0.03, "max_hold_days": 5}
        else:
            filter_cfg = active.filter_config
            score_cfg = active.score_config
            signal_cfg = active.signal_config
            risk_cfg = active.risk_config

        basics = db.query(StockBasic).all()
        if not basics:
            _log_job(db, "post_market_analyze", "failed", "No stock_basic data", started_at=started)
            return

        stocks = []
        for b in basics:
            last_20 = (
                db.query(StockDaily)
                .filter(StockDaily.code == b.code)
                .order_by(StockDaily.trade_date.desc())
                .limit(20)
                .all()
            )
            if len(last_20) < 5:
                continue
            latest = last_20[0]
            avg_amount = sum(d.amount for d in last_20) / len(last_20)
            pct_5d = (
                (latest.close - last_20[min(4, len(last_20) - 1)].close)
                / last_20[min(4, len(last_20) - 1)].close
                * 100
            ) if len(last_20) >= 5 else 0
            stocks.append(
                {
                    "code": b.code,
                    "name": b.name,
                    "close": latest.close,
                    "avg_amount_20d": avg_amount,
                    "list_date": b.list_date,
                    "market": b.market,
                    "is_st": b.is_st,
                    "is_suspended": False,
                    "is_limit_up": (latest.change_pct or 0) >= 9.9,
                    "is_limit_down": (latest.change_pct or 0) <= -9.9,
                    "industry": b.industry or "未知",
                    "pct_5d": pct_5d,
                }
            )

        if not stocks:
            _log_job(db, "post_market_analyze", "success", "No eligible stocks", started_at=started)
            return
        universe_df = pd.DataFrame(stocks)
        filtered = hard_filter(universe_df, filter_cfg)

        scored_rows = []
        for _, row in filtered.iterrows():
            klines = (
                db.query(StockDaily)
                .filter(StockDaily.code == row["code"])
                .order_by(StockDaily.trade_date)
                .limit(60)
                .all()
            )
            kline_df = pd.DataFrame(
                [{"open": k.open, "high": k.high, "low": k.low, "close": k.close, "volume": k.volume} for k in klines]
            )
            if len(kline_df) < 20:
                continue
            tech_score, tech_details = score_technical(kline_df)
            vol_ratio = calc_volume_ratio(kline_df["volume"], 20)
            fund_data = {"north_net_3d": 0, "main_net": 0, "super_large_pct": 0, "volume_ratio": vol_ratio}
            fund_score, fund_details = score_fund(fund_data)
            sector_row = (
                db.query(SectorDailyModel)
                .filter(SectorDailyModel.sector == row["industry"], SectorDailyModel.trade_date == today)
                .first()
            )
            all_sectors = db.query(SectorDailyModel).filter(SectorDailyModel.trade_date == today).count()
            sector_rank_pct = 50
            if sector_row and all_sectors > 0:
                above = (
                    db.query(SectorDailyModel)
                    .filter(
                        SectorDailyModel.trade_date == today,
                        SectorDailyModel.change_pct >= sector_row.change_pct,
                    )
                    .count()
                )
                sector_rank_pct = int(above / all_sectors * 100)
            sentiment_row = (
                db.query(MarketSentiment).filter(MarketSentiment.trade_date == today).first()
            )
            momentum_data = {
                "pct_5d": row["pct_5d"],
                "relative_strength": (sector_row.change_pct if sector_row else 0) - row["pct_5d"],
                "is_20d_high": row["close"] >= kline_df["close"].tail(20).max(),
            }
            momentum_score, momentum_details = score_momentum(momentum_data)
            sentiment_data = {
                "sector_rank_pct": sector_rank_pct,
                "limit_up": sentiment_row.limit_up if sentiment_row else 0,
                "limit_down": sentiment_row.limit_down if sentiment_row else 0,
                "sector_net_flow": sector_row.net_fund_flow if sector_row else 0,
            }
            sentiment_score, sentiment_details = score_sentiment(sentiment_data)
            total = compute_total_score(
                {"tech": tech_score, "fund": fund_score, "momentum": momentum_score, "sentiment": sentiment_score},
                score_cfg,
            )
            all_details = {
                "tech": tech_details,
                "fund": fund_details,
                "momentum": momentum_details,
                "sentiment": sentiment_details,
            }
            reason = build_signal_reason(all_details)
            scored_rows.append(
                {
                    "code": row["code"],
                    "stock_name": row["name"],
                    "close": row["close"],
                    "industry": row["industry"],
                    "score": total,
                    "tech_score": tech_score,
                    "fund_score": fund_score,
                    "momentum_score": momentum_score,
                    "sentiment_score": sentiment_score,
                    "reason": reason,
                }
            )

        if not scored_rows:
            _log_job(db, "post_market_analyze", "success", "No stocks scored above threshold", started_at=started)
            return
        scored_df = pd.DataFrame(scored_rows)
        held_codes = [p.code for p in get_active_positions(db)]
        top = apply_concentration_control(
            select_top_n(scored_df, min_score=signal_cfg.get("min_score", 65), top_n=signal_cfg.get("top_n", 3)),
            held_codes,
        )

        for _, sig in scored_df.iterrows():
            db.add(
                Signal(
                    code=sig["code"],
                    stock_name=sig["stock_name"],
                    trade_date=today,
                    direction="buy",
                    score=sig["score"],
                    tech_score=sig["tech_score"],
                    fund_score=sig["fund_score"],
                    momentum_score=sig["momentum_score"],
                    sentiment_score=sig["sentiment_score"],
                    reason=sig["reason"],
                    close_price=sig["close"],
                    suggested_buy_low=round(sig["close"] * 0.99, 2),
                    suggested_buy_high=round(sig["close"] * 1.01, 2),
                    stop_loss_price=round(sig["close"] * 0.95, 2),
                    target_price=round(sig["close"] * 1.12, 2),
                )
            )
        db.commit()

        risk_cfg_obj = RiskConfig(
            stop_loss_pct=risk_cfg.get("stop_loss_pct", -0.05),
            take_profit_pct=risk_cfg.get("take_profit_pct", 0.12),
            trailing_trigger=risk_cfg.get("trailing_trigger", 0.07),
            trailing_drawdown=risk_cfg.get("trailing_drawdown", 0.03),
            max_hold_days=risk_cfg.get("max_hold_days", 5),
        )
        positions = get_active_positions(db)
        pos_report = []
        for pos in positions:
            hold_days = (today - pos.buy_date).days
            pnl_pct = (
                (pos.current_price - pos.buy_price) / pos.buy_price
                if pos.current_price and pos.buy_price
                else 0
            )
            sell_signals = check_sell_signals(
                {
                    "buy_price": pos.buy_price,
                    "current_price": pos.current_price,
                    "highest_price": pos.highest_price,
                    "hold_days": hold_days,
                },
                risk_cfg_obj,
            )
            advice = sell_signals[0]["reason"] if sell_signals else "继续持有"
            pos_report.append(
                {
                    "stock_name": pos.stock_name,
                    "code": pos.code,
                    "hold_days": hold_days,
                    "pnl_pct": pnl_pct,
                    "advice": advice,
                }
            )

        sentiment_dict = {}
        if sentiment_row:
            north = db.query(NorthFlowModel).filter(NorthFlowModel.trade_date == today).first()
            sentiment_dict = {
                "temperature": 50,
                "sh_index_pct": sentiment_row.sh_index_pct,
                "sz_index_pct": sentiment_row.sz_index_pct,
                "cyb_index_pct": sentiment_row.cyb_index_pct,
                "limit_up": sentiment_row.limit_up,
                "limit_down": sentiment_row.limit_down,
                "north_net": north.net_amount if north else 0,
            }
        top_signals = []
        for _, sig in top.iterrows():
            top_signals.append(
                {
                    "code": sig["code"],
                    "stock_name": sig["stock_name"],
                    "score": sig["score"],
                    "close_price": sig["close"],
                    "reason": sig["reason"],
                    "buy_low": round(sig["close"] * 0.99, 2),
                    "buy_high": round(sig["close"] * 1.01, 2),
                    "stop_loss": round(sig["close"] * 0.95, 2),
                    "target": round(sig["close"] * 1.12, 2),
                }
            )
        from datetime import timedelta as td
        yesterday = today - td(days=1)
        for sig in top_signals:
            prev = db.query(Signal).filter(
                Signal.code == sig["code"],
                Signal.trade_date < today,
            ).order_by(Signal.trade_date.desc()).first()
            sig["score_delta"] = sig["score"] - prev.score if prev else 0
        from app.models.ai import AIAnalysis
        for sig in top_signals:
            ai = db.query(AIAnalysis).filter(
                AIAnalysis.code == sig["code"], AIAnalysis.trade_date == today
            ).first()
            sig["ai_summary"] = ai.summary if ai else ""
        day_idx = today.timetuple().tm_yday % len(INDICATOR_GUIDES)
        learn_tip = INDICATOR_GUIDES[day_idx]
        card = build_post_market_card(today, top_signals, pos_report, sentiment_dict, learn_tip, settings.base_url)
        FeishuBot(settings.feishu_webhook_url).send_card(card)
        _log_job(
            db,
            "post_market_analyze",
            "success",
            f"Generated {len(scored_rows)} scores, top {len(top)} signals",
            started_at=started,
        )
    except Exception as e:
        logger.error(f"Post-market analyze failed: {e}", exc_info=True)
        _log_job(db, "post_market_analyze", "failed", str(e), started_at=started)
        FeishuBot(settings.feishu_webhook_url).send_card(build_alert_card("策略分析失败", str(e), "error"))
    finally:
        db.close()


def job_maintenance():
    db = SessionLocal()
    try:
        purge_old_data(db)
        update_stock_basic(db)
        _log_job(db, "maintenance", "success")
    except Exception as e:
        logger.error(f"Maintenance failed: {e}")
        _log_job(db, "maintenance", "failed", str(e))
    finally:
        db.close()


def job_ai_analysis():
    if not is_trading_day():
        return
    if not settings.deepseek_api_key and not settings.qwen_api_key:
        logger.info("AI analysis skipped: no LLM API key configured")
        return
    started = datetime.now()
    db = SessionLocal()
    try:
        from app.models.ai import AIAnalysis
        from app.models.watchlist import Watchlist
        from app.services.ai.analyzer import analyze_stock

        today = date.today()
        codes = set()

        top_signals = (
            db.query(Signal)
            .filter(Signal.trade_date == today)
            .order_by(Signal.score.desc())
            .limit(3)
            .all()
        )
        for s in top_signals:
            codes.add(s.code)

        positions = get_active_positions(db)
        for p in positions:
            codes.add(p.code)

        watchlist = db.query(Watchlist).all()
        for w in watchlist:
            codes.add(w.code)

        generated = 0
        for code in codes:
            existing = db.query(AIAnalysis).filter(
                AIAnalysis.code == code, AIAnalysis.trade_date == today
            ).first()
            if existing:
                continue
            result = analyze_stock(db, code)
            db.add(AIAnalysis(
                code=code,
                trade_date=today,
                summary=result["summary"],
                risk=result["risk"],
                suggestion=result["suggestion"],
                market_comment=result["market_comment"],
                llm_provider=settings.llm_provider,
            ))
            db.commit()
            generated += 1

        _log_job(db, "ai_analysis", "success",
                 f"Generated {generated} AI analyses for {len(codes)} stocks",
                 started_at=started, records_collected=generated)
    except Exception as e:
        logger.error(f"AI analysis job failed: {e}", exc_info=True)
        _log_job(db, "ai_analysis", "failed", str(e), started_at=started, error_message=str(e))
    finally:
        db.close()
