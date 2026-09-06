import streamlit as st
import requests
import pandas as pd
import datetime

st.set_page_config(page_title="Currency Analysis App", layout="wide")
st.title("Currency Analysis App")
st.caption(""" Welcome to the application for analyzing how major macroeconomic events affect currency rates.

    You can use this tool app:
    - check the current exchange rate
    - view historical rates for a selected date range
    - analyze the impact of a single event
    - compare short-term vs long-term event impact windows

    Data source: National Bank of Poland (NBP) API""")

tab1, tab2, tab3, tab4 = st.tabs([
    "Current Rate",
    "History",
    "Single Event Impact",
    "Compare Events Impact",
])
with st.sidebar:
    backend_url = st.text_input("Backend URL", value="http://127.0.0.1:8000")
    if st.button("Check backend"):
        try:
            response = requests.get(f"{backend_url}/", timeout=5)
            response.raise_for_status()
            st.success(f"Connected! {response.status_code}")
            st.json(response.json())
        except Exception as e:
            st.error(f"Connection Error! {e}")

with tab1:
    st.header("Current Rate")
    current_rate = st.text_input("Code (USD, EUR, CHF ect.)", value="USD", key="current_code").upper()

    if st.button("Get current rate", key="button_current_code"):
        try:
            response = requests.get(f"{backend_url}/currencies/{current_rate.upper()}", timeout=5)
            if response.status_code != 200:
                st.error(f"Backend Error! {response.status_code}: {response.text}")
            else:
                data = response.json()
                st.json(data)
                st.success("Current rate loaded!")
                st.dataframe(pd.DataFrame([data]), use_container_width=True, hide_index=True)
        except Exception as e:
            st.error(f"Connection Error! {e}")

with tab2:
    st.header("History")
    history_code = st.text_input("Code", value="USD").upper()
    start_date = st.date_input("Start date", value=datetime.date(2000, 1, 1),
                               min_value=datetime.date(2000, 1, 1),
                               max_value=datetime.date(2030, 1, 1), key="start_date", format="YYYY-MM-DD")
    end_date = st.date_input("End date", value=datetime.date(2025, 12, 31),
                               min_value=datetime.date(2000, 1, 1),
                               max_value=datetime.date(2030, 1, 1), key="end_date", format="YYYY-MM-DD")

    if end_date < start_date:
        st.error("End date must be after start date")
    elif (end_date - start_date).days > 367:
            st.error("Data range cannot exceed 367 days")
    else:
        if st.button("Get historical rates"):
            try:
                params = {"start_date": start_date.isoformat(),
                          "end_date": end_date.isoformat()}

                response = requests.get(f"{backend_url}/currencies/{history_code.upper()}/history", params=params, timeout=5)

                if response.status_code != 200:
                    st.error(f"Backend Error! {response.status_code}: {response.text}")
                else:
                    data = response.json()
                    st.json(data)
                    if not data:
                        st.warning("No data returned for selected parameters")
                    else:
                        st.success(f"Loaded! {response.status_code}")
                        df = pd.DataFrame(data["rates"])
                        st.dataframe(df, use_container_width=True, hide_index=True)
                        df["effectiveDate"] = pd.to_datetime(df["effectiveDate"])
                        st.line_chart(df.set_index("effectiveDate")[["mid"]], use_container_width=True)

            except Exception as e:
                st.error(f"Connection Error! {e}")

with tab3:
    st.header("Single Event Impact Analysis")
    single_code = st.text_input("Code", value="USD", key="single_code").upper()
    single_event_date = st.date_input("Single Event Date", value=datetime.date(2000, 1, 1),
                                      min_value=datetime.date(2000, 1, 1),
                                      max_value=datetime.date(2030, 1, 1), key="single_event_date", format="YYYY-MM-DD")
    single_days_before = st.number_input("Days Before", min_value=0, value=7, step=1)
    single_days_after = st.number_input("Days after", min_value=0, value=7, step=1)

    if single_days_before == 0 and single_days_after == 0:
        st.error("Single Event Impact Analysis must have at least one day")

    elif st.button("Run single event analysis", key="single_event_analysis"):
        try:
            params = {"code": single_code,
                      "event_date": single_event_date.isoformat(),
                      "days_before": int(single_days_before),
                      "days_after": int(single_days_after)}
            response = requests.get(f"{backend_url}/analysis/event-impact", params=params, timeout=5)

            if response.status_code != 200:
                st.error(f"Connection Error! {response.status_code}: {response.text}")
            else:
                st.success(f"Loaded! {response.status_code}")
                data = response.json()

                col1, col2, col3, col4 = st.columns(4)

                with col1:
                    st.metric("Before rate", round(data["before_rate"], 2))
                with col2:
                    st.metric("After rate", round(data["after_rate"], 2))
                with col3:
                    st.metric("Absolut change", round(data["abs_change"], 2))
                with col4:
                    st.metric("Percentage change", round(data["pct_change"], 2))

                st.json(data)


        except Exception as e:
            st.error(f"Connection Error! {e}")

with tab4:
    st.header("Compare Events Impact")
    compare_code = st.text_input("Enter currency code", value="USD").upper()
    short_window = st.number_input("Short window (business days)", min_value=1, value=7, step=1)
    long_window = st.number_input("Long window (business days)", min_value=1, value=21, step=1)

    if long_window <= short_window:
        st.error("Long window must be greater than short window")

    if st.button("Run compare analysis"):
        try:
            params = {"code": compare_code,
                      "short_window": int(short_window),
                      "long_window": int(long_window),
            }
            response = requests.get(f"{backend_url}/analysis/events-impact-compare", params=params, timeout=5)

            if response.status_code != 200:
                st.error(f"Connection Error! {response.status_code}: {response.text}")
            else:
                data = response.json()
                st.json(data)
                if not data:
                    st.warning("No data returned for selected parameters")
                else:
                    st.success(f"Loaded! {response.status_code}")

                    df = pd.DataFrame(data)
                    float_cols = df.select_dtypes(include="float").columns.tolist()
                    column_config = {
                        col: st.column_config.NumberColumn(format="%.2f")
                        for col in float_cols
                    }

                    st.dataframe(df, use_container_width=True, column_config=column_config)
                    st.json(df.round(2).to_dict(orient="records"))
        except Exception as e:
            st.error(f"Connection Error! {e}")



