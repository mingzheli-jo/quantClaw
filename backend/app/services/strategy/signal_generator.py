import pandas as pd


def select_top_n(scored_df: pd.DataFrame, min_score: int = 65, top_n: int = 3) -> pd.DataFrame:
    filtered = scored_df[scored_df["score"] >= min_score].copy()
    filtered = filtered.sort_values("score", ascending=False)
    return filtered.head(top_n).reset_index(drop=True)


def apply_concentration_control(scored_df: pd.DataFrame, held_codes: list[str], top_n: int = 3) -> pd.DataFrame:
    df = scored_df[~scored_df["code"].isin(held_codes)].copy()
    df = df.sort_values("score", ascending=False)
    selected = []
    seen_sectors = set()
    for _, row in df.iterrows():
        sector = row.get("industry", "unknown")
        if sector in seen_sectors:
            continue
        seen_sectors.add(sector)
        selected.append(row)
        if len(selected) >= top_n:
            break
    if not selected:
        return pd.DataFrame(columns=df.columns)
    return pd.DataFrame(selected).reset_index(drop=True)


def build_signal_reason(details: dict) -> str:
    parts = []
    if details.get("tech", {}).get("ma_alignment") == "bullish":
        parts.append("均线多头排列")
    if details.get("tech", {}).get("macd") == "golden_cross":
        parts.append("MACD金叉")
    if details.get("tech", {}).get("breakout") == "20d_high":
        parts.append("突破20日新高")
    vol = details.get("tech", {}).get("volume", "")
    if "ratio" in vol:
        ratio_val = vol.replace("ratio_", "")
        try:
            if float(ratio_val) >= 1.5:
                parts.append(f"放量({ratio_val}倍)")
        except ValueError:
            pass
    if details.get("fund", {}).get("north") == "positive":
        parts.append("北向资金流入")
    if details.get("fund", {}).get("main_fund") == "inflow":
        parts.append("主力资金流入")
    if details.get("momentum", {}).get("rel_strength") == "outperform":
        parts.append("强于板块")
    if details.get("sentiment", {}).get("sector_rank", "").startswith("top_"):
        parts.append("板块领涨")
    return " + ".join(parts) if parts else "综合评分达标"
