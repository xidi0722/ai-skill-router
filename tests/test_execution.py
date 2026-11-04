import json
import time
from datetime import datetime as RealDateTime
from urllib.error import HTTPError, URLError

import pytest

from umr import execution
from umr.execution import ExecutionError, OpenMeteoWeatherNextAdapter, SympyEquationAdapter, _run_sympy_worker


def slow_worker(connection, _equation):
    time.sleep(2)
    connection.send((True, {}))
    connection.close()


class FrozenDateTime(RealDateTime):
    @classmethod
    def now(cls, tz=None):
        value = cls(2026, 11, 4, 12, 0, 0, tzinfo=execution.timezone.utc)
        return value if tz is None else value.astimezone(tz)


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self, limit=-1):
        return self.payload[:limit]


class FakeOpener:
    def __init__(self, result):
        self.result = result

    def open(self, _request, timeout=None):
        if isinstance(self.result, BaseException):
            raise self.result
        return FakeResponse(self.result)


@pytest.fixture
def weather(monkeypatch):
    monkeypatch.setattr(execution, "datetime", FrozenDateTime)
    adapter = OpenMeteoWeatherNextAdapter(timeout_seconds=0.01)

    def call(payload):
        monkeypatch.setattr(execution, "build_opener", lambda *_args: FakeOpener(payload))
        return adapter.execute({
            "latitude": 24.1477,
            "longitude": 120.6736,
            "target_date": "2026-11-05",
            "timezone": "Asia/Taipei",
        })
    return call


def test_sympy_solves_and_verifies_using_process_worker():
    result = SympyEquationAdapter().execute({"equation": "x**2 - 4 = 0"})
    assert {row["x"] for row in result["solutions"]} == {"-2", "2"}
    assert all(row["verified"] for row in result["solutions"])
    assert result["verification"]["passed"] is True
    assert "completeness is not independently certified" in result["verification"]["scope"]


@pytest.mark.parametrize("equation", [
    "__import__('os')=1", "x/(x-1)=0", "x**-1=2", "x/0=1", "x**13=1",
    "x=" + "1" * 257,
])
def test_sympy_rejects_unsafe_or_out_of_scope_equations(equation):
    with pytest.raises(ExecutionError):
        SympyEquationAdapter().execute({"equation": equation})


def test_sympy_process_timeout_terminates_worker():
    with pytest.raises(ExecutionError, match="wall-clock time limit"):
        _run_sympy_worker("x=1", 0.2, worker=slow_worker)


def test_weather_successful_fixture(weather):
    payload = json.dumps({"daily": {
        "time": ["2026-11-05"],
        "precipitation_sum": [12.5],
        "rain_sum": [10.0],
        "precipitation_hours": [3.0],
    }}).encode()
    result = weather(payload)
    assert result["precipitation_sum_mm"] == 12.5
    assert result["quality_verified_by_this_project"] is False
    assert result["validation"]["passed"] is True


@pytest.mark.parametrize("payload", [
    (b"not-json", "invalid_json"),
    (json.dumps({"daily": {"time": ["2026-11-05"], "precipitation_sum": [None]}}).encode(), "adapter_execution_failed"),
    (json.dumps({"daily": {"time": ["2026-11-05"]}}).encode(), "adapter_execution_failed"),
    (b"{" + b" " * 1_000_001, "response_too_large"),
])
def test_weather_invalid_responses_fail_closed(weather, payload):
    data, expected_code = payload
    with pytest.raises(ExecutionError) as error:
        weather(data)
    assert error.value.code == expected_code


@pytest.mark.parametrize("overrides", [
    {"latitude": 91},
    {"longitude": 181},
    {"timezone": "../../etc/passwd"},
    {"target_date": "not-a-date"},
])
def test_weather_rejects_bad_parameters_before_network(monkeypatch, overrides):
    monkeypatch.setattr(execution, "datetime", FrozenDateTime)
    monkeypatch.setattr(execution, "build_opener", lambda *_args: pytest.fail("network must not be called"))
    inputs = {
        "latitude": 24,
        "longitude": 121,
        "target_date": "2026-11-05",
        "timezone": "Asia/Taipei",
    }
    inputs.update(overrides)
    with pytest.raises(ExecutionError):
        OpenMeteoWeatherNextAdapter().execute(inputs)


@pytest.mark.parametrize("error,expected_code", [
    (HTTPError("https://provider.invalid", 302, "redirect", {}, None), "provider_redirect_blocked"),
    (URLError(TimeoutError("fixture timeout")), "provider_timeout"),
    (HTTPError("https://provider.invalid", 503, "unavailable", {}, None), "provider_http_error"),
])
def test_weather_redirect_timeout_and_http_errors_are_structured(error, expected_code, weather, monkeypatch):
    with pytest.raises(ExecutionError) as raised:
        weather(error)
    assert raised.value.code == expected_code
