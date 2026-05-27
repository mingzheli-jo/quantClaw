from datetime import date


def build_post_market_card(
    trade_date: date,
    signals: list[dict],
    positions: list[dict],
    sentiment: dict,
    learn_tip: dict,
    base_url: str = "",
) -> dict:
    temp_score = sentiment.get("temperature", 50)
    temp_emoji = "🟢" if temp_score >= 70 else "🟡" if temp_score >= 40 else "🔴"
    header = {
        "title": {"tag": "plain_text", "content": f"📊 QuantClaw 盘后报告 {trade_date}"},
        "template": "blue",
    }
    elements = []
    overview_lines = [
        f"**市场温度** {temp_score}/100 {temp_emoji}",
        f"上证 {sentiment.get('sh_index_pct', 0):+.2f}% | 深证 {sentiment.get('sz_index_pct', 0):+.2f}% | 创业板 {sentiment.get('cyb_index_pct', 0):+.2f}%",
        f"涨停 {sentiment.get('limit_up', 0)} | 跌停 {sentiment.get('limit_down', 0)} | 北向 {sentiment.get('north_net', 0)/1e8:+.1f}亿",
    ]
    elements.append({"tag": "div", "text": {"tag": "lark_md", "content": "\n".join(overview_lines)}})
    elements.append({"tag": "hr"})

    if signals:
        elements.append({"tag": "div", "text": {"tag": "lark_md", "content": "**🔴 买入候选**"}})
        for i, sig in enumerate(signals):
            medal = ["🥇", "🥈", "🥉"][i] if i < 3 else f"{i+1}."
            delta_text = ""
            if sig.get("score_delta"):
                d = sig["score_delta"]
                delta_text = f" ({'↑' if d > 0 else '↓'}{abs(d):.0f})"
            sig_lines = [
                f"{medal} **{sig['stock_name']}** {sig['code']}  评分 {sig['score']}/100{delta_text}",
                f"现价 ¥{sig['close_price']:.2f} | 买入 ¥{sig.get('buy_low', 0):.2f}-{sig.get('buy_high', 0):.2f}",
                f"止损 ¥{sig.get('stop_loss', 0):.2f} | 目标 ¥{sig.get('target', 0):.2f}",
                f"📌 {sig.get('reason', '')}",
            ]
            elements.append({"tag": "div", "text": {"tag": "lark_md", "content": "\n".join(sig_lines)}})
            if base_url:
                elements.append({
                    "tag": "action",
                    "actions": [{
                        "tag": "button",
                        "text": {"tag": "plain_text", "content": f"查看 {sig['stock_name']} →"},
                        "url": f"{base_url}/stock/{sig['code']}",
                        "type": "default",
                    }],
                })
            if sig.get("ai_summary"):
                elements.append({
                    "tag": "div",
                    "text": {"tag": "lark_md", "content": f"🤖 AI: {sig['ai_summary'][:80]}"},
                })
        elements.append({"tag": "hr"})
    else:
        elements.append({"tag": "div", "text": {"tag": "lark_md", "content": "**今日无买入候选** — 耐心等待更好的机会"}})
        elements.append({"tag": "hr"})

    if positions:
        elements.append({"tag": "div", "text": {"tag": "lark_md", "content": "**🟢 持仓跟踪**"}})
        for pos in positions:
            pnl_emoji = "✅" if pos.get("pnl_pct", 0) >= 0 else "⚠️"
            pos_line = (
                f"{pos['stock_name']} {pos['code']} | 第{pos['hold_days']}天 | "
                f"{pos['pnl_pct']:+.1%} {pnl_emoji} | {pos.get('advice', '继续持有')}"
            )
            elements.append({"tag": "div", "text": {"tag": "lark_md", "content": pos_line}})
        elements.append({"tag": "hr"})

    if learn_tip:
        elements.append({
            "tag": "div",
            "text": {
                "tag": "lark_md",
                "content": f"**📖 今日学习: {learn_tip['name']}**\n{learn_tip['summary']}",
            },
        })

    return {"header": header, "elements": elements}


def build_pre_market_card(trade_date: date, positions: list[dict]) -> dict:
    header = {
        "title": {"tag": "plain_text", "content": f"🌅 QuantClaw 盘前关注 {trade_date}"},
        "template": "green",
    }
    elements = []
    if positions:
        for pos in positions:
            line = (
                f"**{pos['stock_name']}** {pos['code']} | "
                f"成本 ¥{pos['buy_price']:.2f} | "
                f"止损 ¥{pos['stop_loss']:.2f} | "
                f"止盈 ¥{pos['take_profit']:.2f}"
            )
            elements.append({"tag": "div", "text": {"tag": "lark_md", "content": line}})
    else:
        elements.append({"tag": "div", "text": {"tag": "lark_md", "content": "当前无持仓，等待买入信号"}})
    return {"header": header, "elements": elements}


def build_alert_card(title: str, message: str, level: str = "warning") -> dict:
    template = {"warning": "orange", "error": "red", "info": "blue"}.get(level, "orange")
    return {
        "header": {
            "title": {"tag": "plain_text", "content": f"⚠️ {title}"},
            "template": template,
        },
        "elements": [{"tag": "div", "text": {"tag": "lark_md", "content": message}}],
    }
