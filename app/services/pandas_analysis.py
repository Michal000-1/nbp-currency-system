import pandas as pd
from app.models.analysis import EventImpactItem

def build_events_dataframe(code: str, window_business_days: int, events: list[EventImpactItem]) -> pd.DataFrame:
    """Builds a pandas DataFrame from event impact items for a given currency and window size.
    Maps event metadata and calculated metrics (before/after rates, abs_change, pct_change)
    into tabular form and returns rows sorted by event date."""
    rows = []

    for item in events:
        rows.append({"code": code,
                     "window_business_days": window_business_days,
                     "event_id": item.event.event_id,
                     "event_name": item.event.name,
                     "event_date": item.event.event_date,
                     "before_rate": item.before_rate,
                     "after_rate": item.after_rate,
                     "abs_change": item.abs_change,
                     "pct_change": item.pct_change
                     })
    df = pd.DataFrame(rows)

    if df.empty:
        return df

    df = df.sort_values("event_date")
    return df

def compare_windows(df_week: pd.DataFrame, df_3weeks: pd.DataFrame) -> pd.DataFrame:
    """Compares the exchange rate change between a short and long window for the same events,
    and returns a table indicating whether the rate change effect was stronger
    in the shorter window."""
    if df_week.empty:
        return df_week

    if df_3weeks.empty:
        return df_3weeks

    df_week =  pd.DataFrame({"event_id": df_week["event_id"],
                             "event_name": df_week["event_name"],
                             "pct_change_week": df_week["pct_change"],
                             "abs_change_week": df_week["abs_change"],})

    df_3weeks = pd.DataFrame({"event_id": df_3weeks["event_id"],
                              "event_name": df_3weeks["event_name"],
                              "pct_change_3weeks": df_3weeks["pct_change"],
                              "abs_change_3weeks": df_3weeks["abs_change"]})

    merged_df = pd.merge(df_3weeks, df_week, on=["event_id", "event_name"], how="inner")

    def compare_strength(row):
        if abs(row["pct_change_week"]) > abs(row["pct_change_3weeks"]):
            return str("short")
        elif abs(row["pct_change_week"]) < abs(row["pct_change_3weeks"]):
            return str("long")
        else:
            return str("equal")

    merged_df["is_week_stronger_pct_change"] = merged_df.apply(compare_strength, axis=1)
    merged_df["is_week_stronger_abs_change"] = abs(merged_df["abs_change_week"]) > abs(merged_df["abs_change_3weeks"])

    return merged_df

