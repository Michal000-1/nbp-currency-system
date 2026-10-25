from pathlib import Path
from unittest.mock import Mock

import pytest

st = pytest.importorskip("streamlit")
alt = pytest.importorskip("altair")
AppTest = pytest.importorskip("streamlit.testing.v1").AppTest

from app.services.events import EVENTS

UI_PATH = Path(__file__).resolve().parents[1] / "streamlit_app" / "ui.py"


def render_result(monkeypatch, payload, button_label):
    response = Mock(status_code=200)
    response.json.return_value = payload
    get = Mock(return_value=response)
    monkeypatch.setattr("requests.get", get)
    chart = Mock(wraps=st.vega_lite_chart)
    monkeypatch.setattr(st, "vega_lite_chart", chart)

    app = AppTest.from_file(str(UI_PATH)).run()
    next(button for button in app.button if button.label == button_label).click().run()

    assert not app.exception
    assert not app.error
    get.assert_called_once()
    chart.assert_called_once()
    spec = chart.call_args.kwargs["spec"]
    # Streamlit receives the data separately; supply that required schema field.
    alt.Chart.from_dict({"data": {"values": []}, **spec}, validate=True)
    assert chart.call_args.kwargs["width"] == "stretch"
    return app, chart.call_args.args[0], spec


@pytest.mark.parametrize("changes", [(2.5, -4.0), (0.0, 0.0)])
def test_comparison_preserves_full_names_and_uses_shared_zero_scale(monkeypatch, changes):
    short, long = changes
    payload = [
        {"event_id": event.event_id, "event_name": event.name,
         "pct_change_short": short, "pct_change_long": long,
         "abs_change_short": 0.1, "abs_change_long": -0.16,
         "is_short_stronger_pct": "equal" if short == long else "long"}
        for event in EVENTS
    ]
    _, frame, spec = render_result(monkeypatch, payload, "Run compare analysis")

    assert len(frame) == 2 * len(EVENTS)
    assert frame["event_name"].tolist() == [event.name for event in EVENTS] * 2
    for row in frame.itertuples():
        assert row.event_label.replace("\n", " ") == row.event_name
        assert max(map(len, row.event_label.splitlines())) <= 30
    assert any("\n" in label for label in frame["event_label"])
    axis = spec["encoding"]["y"]["axis"]
    assert axis["labelLimit"] == 0
    assert axis["labelOverlap"] is False
    assert axis["labelExpr"] == "split(datum.label, '\\n')"
    lower, upper = spec["encoding"]["x"]["scale"]["domain"]
    assert lower == -upper
    assert lower < min(changes) <= max(changes) < upper
    assert spec["encoding"]["x"]["axis"]["format"] == "+.2f"
    assert spec["encoding"]["yOffset"]["field"] == "window"
    assert spec["height"] >= len(EVENTS) * 64


@pytest.mark.parametrize("rates", [[4.0], [4.0, 4.0], [3.9, 4.1], [0.0004, 0.0005]])
def test_history_scale_covers_constant_single_and_varying_rates(monkeypatch, rates):
    payload = {"rates": [
        {"no": "test", "effectiveDate": f"2024-01-{index + 2:02d}", "mid": rate}
        for index, rate in enumerate(rates)
    ][::-1]}
    _, frame, spec = render_result(monkeypatch, payload, "Get historical rates")

    lower, upper = spec["encoding"]["y"]["scale"]["domain"]
    assert 0 <= lower < min(rates) <= max(rates) < upper
    assert spec["encoding"]["y"]["scale"]["zero"] is False
    assert spec["mark"]["point"] is True
    assert spec["encoding"]["x"]["axis"]["labelOverlap"] == "greedy"
    assert frame["effectiveDate"].is_monotonic_increasing


def test_single_event_uses_same_rate_chart(monkeypatch):
    payload = {"event_date": "2022-02-24", "before_date": "2022-02-23",
               "after_date": "2022-02-25", "before_rate": 4.0, "after_rate": 4.1,
               "abs_change": 0.1, "pct_change": 2.5,
               "window_rates": [{"date": "2022-02-25", "rate": 4.1},
                                {"date": "2022-02-23", "rate": 4.0}]}
    _, frame, spec = render_result(monkeypatch, payload, "Run single event analysis")
    assert frame["date"].is_monotonic_increasing
    assert spec["encoding"]["y"]["field"] == "rate"
    assert spec["encoding"]["tooltip"][1]["format"] == ".4f"
