from datetime import date, timedelta
import pandas as pd

def hard_filter(df: pd.DataFrame, config: dict) -> pd.DataFrame:
    min_amount = config.get("min_amount_20d", 50_000_000)
    max_price = config.get("max_price", 50)
    min_list_days = config.get("min_list_days", 60)
    cutoff_date = date.today() - timedelta(days=min_list_days)

    mask = (
        (~df["is_st"])
        & (~df["is_suspended"])
        & (~df["is_limit_up"])
        & (~df["is_limit_down"])
        & (df["close"] <= max_price)
        & (df["avg_amount_20d"] >= min_amount)
        & (df["list_date"] <= cutoff_date)
        & (df["market"] != "bj")
    )
    return df[mask].reset_index(drop=True)
