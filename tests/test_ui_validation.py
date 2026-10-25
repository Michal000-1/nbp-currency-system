from pathlib import Path
from unittest.mock import Mock

import pytest

AppTest = pytest.importorskip("streamlit.testing.v1").AppTest
UI_PATH = Path(__file__).resolve().parents[1] / "streamlit_app" / "ui.py"


def test_initial_form_has_no_validation_errors_or_network_requests(monkeypatch):
    get = Mock(side_effect=AssertionError("Initial rendering must not send requests"))
    monkeypatch.setattr("requests.get", get)
    app = AppTest.from_file(str(UI_PATH)).run()

    assert not app.exception
    assert not app.error
    assert any(button.label == "Get historical rates" for button in app.button)
    get.assert_not_called()


@pytest.mark.parametrize("long_window", [6, 7])
def test_invalid_compare_order_disables_submit_until_corrected(monkeypatch, long_window):
    get = Mock(side_effect=AssertionError("Invalid input must not send requests"))
    monkeypatch.setattr("requests.get", get)
    app = AppTest.from_file(str(UI_PATH)).run()

    next(widget for widget in app.number_input if widget.label == "Long window (business days)").set_value(long_window)
    app.run()

    assert not app.exception
    button = next(button for button in app.button if button.label == "Run compare analysis")
    assert button.disabled
    assert any(error.value == "Long window must be greater than short window" for error in app.error)
    get.assert_not_called()

    next(widget for widget in app.number_input if widget.label == "Long window (business days)").set_value(21)
    app.run()

    assert not app.exception
    assert not app.error
    assert not next(button for button in app.button if button.label == "Run compare analysis").disabled
    get.assert_not_called()
