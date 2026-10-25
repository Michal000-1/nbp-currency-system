import datetime
from textwrap import fill
from typing import cast
import pandas as pd
import requests
import streamlit as st

MIN_RATE_DATE = datetime.date(2002, 1, 2)
MAX_RANGE_DAYS = 367
CHART_COLORS = ["#16766B", "#7C9FBA"]
today = datetime.date.today()

st.set_page_config(page_title="NBP Currency System", page_icon="↗", layout="wide")
st.html("""
<style>
.stMainBlockContainer { max-width: 1440px; padding-top: 4.5rem; }
[data-testid="stSidebar"] { border-right: 1px solid #d9e4df; }
[data-testid="stSidebar"] h2 { font-size: 1.15rem; }
[data-testid="stMetric"] {
    background: var(--secondary-background-color);
    border-radius: 14px;
}
[data-testid="stMetricValue"] { font-variant-numeric: tabular-nums; }
[data-testid="stMetricLabel"] { opacity: .78; }
[data-testid="stTabs"] [role="tablist"] { gap: 1.5rem; margin-bottom: .6rem; }
[data-testid="stTabs"] [role="tab"] { padding-bottom: .8rem; }
[data-testid="stTabs"] [role="tab"] p { font-size: .9rem; font-weight: 600; }
[data-testid="stButton"] button { min-height: 2.75rem; font-weight: 600; }
.workspace-brand { display: flex; align-items: center; gap: .8rem; margin: .5rem 0 2rem; }
.workspace-brand__mark {
    background: #183b3a; color: #d5eee5; width: 44px; height: 44px;
    border-radius: 12px; display: grid; place-items: center;
    font-size: .8rem; font-weight: 750; letter-spacing: .04em;
}
.workspace-brand strong { display: block; font-size: .95rem; }
.hero {
    background: #183b3a; color: #f7fbf9; border-radius: 20px;
    padding: 2.4rem 2.6rem; display: flex; align-items: center;
    justify-content: space-between; gap: 2rem; margin-bottom: 1.2rem;
    border-top: 4px solid #79c2ad;
}
.hero h1 { color: #f7fbf9; font-size: clamp(2rem, 3.2vw, 3.3rem); letter-spacing: -.04em; padding: .55rem 0; line-height: 1.12; }
.hero__source { min-width: 155px; border-left: 1px solid #4c6b63; padding-left: 2rem; }
.hero__source span { display: block; color: #a9d6c7; font-size: .7rem; letter-spacing: .1em; margin-bottom: .45rem; }
.hero__source strong { display: block; font-size: 1.35rem; font-weight: 500; margin-bottom: .25rem; }
.hero__source small { color: #c5d9d2; font-size: .78rem; }
.workspace-footer { border-top: 1px solid #d9e4df; margin-top: 2.5rem; padding-top: 1rem; font-size: .75rem; opacity: .65; }
@media (max-width: 640px) {
    .stMainBlockContainer { padding: 4.5rem 1rem 3rem; }
    .hero { padding: 1.6rem; flex-direction: column; align-items: flex-start; gap: 1.2rem; }
    .hero__source { display: none; }
    [data-testid="stTabs"] [role="tablist"] { gap: 1rem; }
}
</style>
""")


def response_details(payload) -> None:
    with st.expander("Response details"):
        st.json(payload)


def show_rate_chart(df: pd.DataFrame, date_column: str, rate_column: str) -> None:
    minimum, maximum = float(df[rate_column].min()), float(df[rate_column].max())
    padding = max((maximum - minimum) * 0.1, maximum * 0.005, 0.0001)
    spec = {
        "mark": {"type": "line", "point": True, "color": CHART_COLORS[0]},
        "encoding": {
            "x": {
                "field": date_column, "type": "temporal", "title": "Publication date",
                "scale": {"type": "utc"},
                "axis": {"format": "%Y-%m-%d", "labelAngle": 0, "tickCount": 6,
                         "labelOverlap": "greedy", "labelFlush": True},
            },
            "y": {
                "field": rate_column, "type": "quantitative", "title": "Rate (PLN)",
                "scale": {"zero": False, "nice": False,
                          "domain": [max(0, minimum - padding), maximum + padding]},
                "axis": {"format": ".4f", "tickCount": 5},
            },
            "tooltip": [
                {"field": date_column, "type": "temporal", "title": "Publication date", "format": "%Y-%m-%d"},
                {"field": rate_column, "type": "quantitative", "title": "Rate (PLN)", "format": ".4f"},
            ],
        },
        "height": 320,
        "config": {"view": {"stroke": None}},
    }
    st.vega_lite_chart(df.sort_values(date_column), spec=spec, width="stretch")
    st.caption("The rate axis is fitted to the displayed observations and may start above zero.")


def show_comparison_chart(df: pd.DataFrame, short_window: int, long_window: int) -> None:
    windows = {
        "pct_change_short": f"Short · {short_window} days",
        "pct_change_long": f"Long · {long_window} days",
    }
    chart_df = df.melt(
        id_vars=["event_name"], value_vars=list(windows),
        var_name="window", value_name="change",
    )
    chart_df["window"] = chart_df["window"].map(windows)
    labels = {name: fill(name, width=30) for name in df["event_name"]}
    chart_df["event_label"] = chart_df["event_name"].map(labels)
    max_lines = max(label.count("\n") + 1 for label in labels.values())
    extent = max(float(chart_df["change"].abs().max()) * 1.1, 0.01)
    spec = {
        "mark": {"type": "bar"},
        "encoding": {
            "x": {
                "field": "change", "type": "quantitative", "title": "Change (%)",
                "scale": {"domain": [-extent, extent], "nice": False, "zero": True},
                "axis": {"format": "+.2f", "tickCount": 5, "labelOverlap": "greedy",
                         "gridColor": {"condition": {"test": "datum.value === 0", "value": "#183B3A"},
                                       "value": "#D9E4DF"}},
            },
            "y": {
                "field": "event_label", "type": "nominal", "title": None,
                "sort": list(labels.values()),
                "axis": {"labelExpr": "split(datum.label, '\\n')", "labelLimit": 0,
                         "labelFontSize": 11, "labelLineHeight": 14,
                         "labelPadding": 10, "labelOverlap": False, "ticks": False},
            },
            "yOffset": {"field": "window", "sort": list(windows.values())},
            "color": {
                "field": "window", "type": "nominal", "title": None,
                "scale": {"domain": list(windows.values()), "range": CHART_COLORS},
                "legend": {"orient": "top", "direction": "vertical", "labelLimit": 0},
            },
            "tooltip": [
                {"field": "event_name", "type": "nominal", "title": "Event"},
                {"field": "window", "type": "nominal", "title": "Window"},
                {"field": "change", "type": "quantitative", "title": "Change (%)", "format": "+.2f"},
            ],
        },
        "height": max(340, len(df) * max(64, max_lines * 14 + 20)),
        "config": {"view": {"stroke": None}},
    }
    st.vega_lite_chart(chart_df, spec=spec, width="stretch")


with st.sidebar:
    st.html("""
    <div class="workspace-brand">
        <div class="workspace-brand__mark" aria-hidden="true">NBP</div>
        <div><strong>Currency System</strong></div>
    </div>
    """)
    st.divider()
    st.markdown("**Data source**")
    st.caption("National Bank of Poland · Table A\n\nAverage exchange rates quoted in PLN.")
    st.markdown("**Example currency codes**")
    st.caption("EUR · USD · CHF · GBP")
    st.divider()
    with st.expander("Connection"):
        backend_url = cast(str, st.text_input("Backend URL", value="http://nbp-app-backend:8000"))
        if st.button("Check backend", width="stretch"):
            try:
                with st.spinner("Checking connection…"):
                    response = requests.get(f"{backend_url}/", timeout=30)
                    response.raise_for_status()
                st.success("Backend connected")
            except requests.RequestException as error:
                st.error(f"Connection error: {error}")

st.html("""
<div class="hero">
    <h1>NBP Currency System</h1>
    <div class="hero__source">
        <span>DATA SOURCE</span>
        <strong>NBP · Table A</strong>
        <small>Average rates / quoted in PLN</small>
    </div>
</div>
""")

tab1, tab2, tab3, tab4 = st.tabs([
    "Current Rate", "History", "Single Event Impact", "Compare Events Impact",
])

with tab1:
    st.subheader("The latest published rate")
    with st.container(border=True):
        code_column, hint_column = st.columns([1, 2], gap="large")
        with code_column:
            current_rate = cast(str, st.text_input(
                "Currency code", value="USD", key="current_code", help="A three-letter code, for example EUR, USD or CHF.",
            )).upper()
            fetch_current = st.button("Get current rate", key="button_current_code", type="primary")
        with hint_column:
            st.caption("The latest available publication may come from an earlier business day.")

    if fetch_current:
        try:
            with st.spinner("Loading the latest rate…"):
                response = requests.get(f"{backend_url}/currencies/{current_rate}", timeout=30)
            if response.status_code != 200:
                st.error(f"Backend error ({response.status_code}): {response.text}")
            else:
                data = response.json()
                rate_column, date_column = st.columns(2)
                rate_column.metric(f"{data['code']} / PLN", f"{data['rate']:.4f} PLN", border=True)
                date_column.metric("Publication date", data["date"], border=True)
                st.caption(data["currency"].capitalize())
                response_details(data)
        except Exception as error:
            st.error(f"Could not load the rate: {error}")

with tab2:
    st.subheader("Historical exchange rates")
    with st.container(border=True):
        code_column, start_column, end_column = st.columns([1, 1.5, 1.5])
        with code_column:
            history_code = cast(str, st.text_input("Currency code", value="USD", key="history_code")).upper()
        with start_column:
            start_date = cast(datetime.date, st.date_input(
                "Start date", value=today - datetime.timedelta(days=30), min_value=MIN_RATE_DATE,
                max_value=today, key="start_date", format="YYYY-MM-DD",
            ))
        with end_column:
            end_date = cast(datetime.date, st.date_input(
                "End date", value=today, min_value=MIN_RATE_DATE,
                max_value=today, key="end_date", format="YYYY-MM-DD",
            ))
        valid_history = True
        if end_date < start_date:
            st.error("End date cannot be earlier than start date")
            valid_history = False
        elif (end_date - start_date).days > MAX_RANGE_DAYS:
            st.error(f"Date range cannot exceed {MAX_RANGE_DAYS} days")
            valid_history = False
        fetch_history = st.button("Get historical rates", type="primary", disabled=not valid_history)

    if fetch_history:
        try:
            with st.spinner("Loading historical rates…"):
                response = requests.get(
                    f"{backend_url}/currencies/{history_code}/history",
                    params={"start_date": start_date.isoformat(), "end_date": end_date.isoformat()}, timeout=30,
                )
            if response.status_code != 200:
                st.error(f"Backend error ({response.status_code}): {response.text}")
            else:
                data = response.json()
                if not data or not data.get("rates"):
                    st.warning("No data returned for selected parameters")
                else:
                    df = pd.DataFrame(data["rates"])
                    df["effectiveDate"] = pd.to_datetime(df["effectiveDate"])
                    df = df.sort_values("effectiveDate")
                    first, last, count = st.columns(3)
                    first.metric("First available rate", f"{df.iloc[0]['mid']:.4f} PLN", border=True)
                    last.metric("Last available rate", f"{df.iloc[-1]['mid']:.4f} PLN", border=True)
                    count.metric("Published observations", len(df), border=True)
                    with st.container(border=True):
                        st.markdown(f"**{history_code} / PLN · Rate history**")
                        show_rate_chart(df, "effectiveDate", "mid")
                    with st.expander("Daily publications"):
                        st.dataframe(
                            df, hide_index=True, width="stretch",
                            column_order=["effectiveDate", "mid", "no"],
                            column_config={
                                "effectiveDate": st.column_config.DateColumn("Publication date", format="YYYY-MM-DD"),
                                "mid": st.column_config.NumberColumn("Rate (PLN)", format="%.4f"),
                                "no": "NBP table",
                            },
                        )
                    response_details(data)
        except Exception as error:
            st.error(f"Could not load the history: {error}")

with tab3:
    st.subheader("Single event analysis")
    st.caption("Compare the last available rate before an event with the last rate in the selected period after it.")
    with st.container(border=True):
        code_column, event_column, before_column, after_column = st.columns([1, 1.5, 1, 1])
        with code_column:
            single_code = cast(str, st.text_input("Currency code", value="USD", key="single_code")).upper()
        with event_column:
            single_event_date = cast(datetime.date, st.date_input(
                "Single Event Date", value=datetime.date(2022, 2, 24), min_value=MIN_RATE_DATE,
                max_value=today, key="single_event_date", format="YYYY-MM-DD",
            ))
        with before_column:
            single_days_before = cast(int, st.number_input("Days Before", min_value=1, max_value=MAX_RANGE_DAYS, value=7, step=1))
        with after_column:
            single_days_after = cast(int, st.number_input("Days after", min_value=1, max_value=MAX_RANGE_DAYS, value=7, step=1))
        st.caption(f"Days are business days. The complete window must fit within the available dates and a {MAX_RANGE_DAYS}-day date span.")
        analyze_single = st.button("Run single event analysis", key="single_event_analysis", type="primary")

    if analyze_single:
        try:
            params = {"code": single_code, "event_date": single_event_date.isoformat(), "days_before": single_days_before, "days_after": single_days_after}
            with st.spinner("Analyzing the event window..."):
                response = requests.get(f"{backend_url}/analysis/event-impact", params=params, timeout=30)
            if response.status_code != 200:
                st.error(f"Backend error ({response.status_code}): {response.text}")
            else:
                data = response.json()
                before, after, nominal, percentage = st.columns(4)
                before.metric("Before rate", f"{data['before_rate']:.4f} PLN", border=True)
                before.caption(data["before_date"])
                after.metric("After rate", f"{data['after_rate']:.4f} PLN", border=True)
                after.caption(data["after_date"])
                nominal.metric("Rate change (PLN)", f"{data['abs_change']:+.3f}", border=True)
                percentage.metric("Percentage change", f"{data['pct_change']:+.2f}%", border=True)
                if data.get("window_rates"):
                    df = pd.DataFrame(data["window_rates"])
                    df["date"] = pd.to_datetime(df["date"])
                    with st.container(border=True):
                        st.markdown(f"**{single_code} / PLN · Event window**")
                        st.caption(f"Event date: {data['event_date']}")
                        show_rate_chart(df, "date", "rate")
                st.caption("Positive values indicate a rise in the currency's PLN rate; negative values indicate a fall. These observations alone do not establish causation.")
                response_details(data)
        except Exception as error:
            st.error(f"Could not complete the analysis: {error}")

with tab4:
    st.subheader("Comparison of short and long analysis windows")
    with st.container(border=True):
        code_column, short_column, long_column = st.columns([1, 1.5, 1.5])
        with code_column:
            compare_code = cast(str, st.text_input("Enter currency code", value="USD")).upper()
        with short_column:
            short_window = cast(int, st.number_input("Short window (business days)", min_value=1, max_value=MAX_RANGE_DAYS, value=7, step=1))
        with long_column:
            long_window = cast(int, st.number_input("Long window (business days)", min_value=1, max_value=MAX_RANGE_DAYS, value=21, step=1))
        st.caption("Each window extends this many business days before and after every event.")
        if long_window <= short_window:
            st.error("Long window must be greater than short window")
        compare_events = st.button("Run compare analysis", disabled=long_window <= short_window, type="primary")

    if compare_events:
        try:
            params = {"code": compare_code, "short_window": short_window, "long_window": long_window}
            with st.spinner("Comparing the event windows…"):
                response = requests.get(f"{backend_url}/analysis/events-impact-compare", params=params, timeout=300)
            if response.status_code != 200:
                st.error(f"Backend error ({response.status_code}): {response.text}")
            else:
                data = response.json()
                if not data:
                    st.warning("No data returned for selected parameters")
                else:
                    df = pd.DataFrame(data)
                    events_count, short_count, long_count, equal_count = st.columns(4)
                    events_count.metric("Events compared", len(df), border=True)
                    short_count.metric("Short window stronger", int((df["is_short_stronger_pct"] == "short").sum()), border=True)
                    long_count.metric("Long window stronger", int((df["is_short_stronger_pct"] == "long").sum()), border=True)
                    equal_count.metric("Equal movements", int((df["is_short_stronger_pct"] == "equal").sum()), border=True)
                    st.caption("Strength uses the magnitude of the percentage change, regardless of direction.")
                    with st.container(border=True):
                        st.markdown(f"**{compare_code} / PLN · Changes by event**")
                        show_comparison_chart(df, short_window, long_window)
                    st.markdown("**Comparison results**")
                    display_df = df.copy()
                    display_df["is_short_stronger_pct"] = display_df["is_short_stronger_pct"].map({"short": "Short window", "long": "Long window", "equal": "Equal"})
                    st.dataframe(
                        display_df, hide_index=True, width="stretch", row_height=72,
                        column_order=["event_name", "pct_change_short", "pct_change_long", "abs_change_short", "abs_change_long", "is_short_stronger_pct"],
                        column_config={
                            "event_name": st.column_config.TextColumn("Event", width="large"),
                            "pct_change_short": st.column_config.NumberColumn(f"Short {short_window}d (%)", format="%+.2f"),
                            "pct_change_long": st.column_config.NumberColumn(f"Long {long_window}d (%)", format="%+.2f"),
                            "abs_change_short": st.column_config.NumberColumn("Short change (PLN)", format="%+.3f"),
                            "abs_change_long": st.column_config.NumberColumn("Long change (PLN)", format="%+.3f"),
                            "is_short_stronger_pct": "Stronger window (%)",
                        },
                    )
                    response_details(data)
        except Exception as error:
            st.error(f"Could not compare the events: {error}")

st.html('<div class="workspace-footer">NBP Currency System · National Bank of Poland data</div>')
