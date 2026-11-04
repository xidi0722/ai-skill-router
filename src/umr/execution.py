"""Allowlisted execution adapters for SymPy and Open-Meteo WeatherNext 2."""

import ast
import json
import math
import multiprocessing
import re
from datetime import date, datetime, timedelta, timezone
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


class ExecutionError(RuntimeError):
    def __init__(self, message: str, code: str = "adapter_execution_failed"):
        super().__init__(message)
        self.code = code


class _NoRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, new_url):
        return None


def _safe_sympy_expression(source: str, symbol_table: dict[str, Any]) -> Any:
    import sympy as sp

    if len(source) > 256:
        raise ExecutionError("Equation expression is too long")
    try:
        tree = ast.parse(source, mode="eval")
    except SyntaxError as exc:
        raise ExecutionError("Invalid equation syntax") from exc
    if sum(1 for _ in ast.walk(tree)) > 64:
        raise ExecutionError("Equation expression is too complex")

    binary_ops = {
        ast.Add: lambda left, right: left + right,
        ast.Sub: lambda left, right: left - right,
        ast.Mult: lambda left, right: left * right,
        ast.Div: lambda left, right: left / right,
        ast.Pow: lambda left, right: left**right,
    }
    unary_ops = {
        ast.UAdd: lambda operand: operand,
        ast.USub: lambda operand: -operand,
    }

    def visit(node: ast.AST) -> Any:
        if isinstance(node, ast.Expression):
            return visit(node.body)
        if isinstance(node, ast.Constant) and type(node.value) in (int, float):
            if isinstance(node.value, float) and not math.isfinite(node.value):
                raise ExecutionError("Non-finite numeric constants are not allowed")
            if abs(node.value) > 1_000_000_000:
                raise ExecutionError("Numeric constants must be within one billion")
            return sp.Rational(str(node.value))
        if isinstance(node, ast.Name):
            if node.id.startswith("_") or len(node.id) > 32:
                raise ExecutionError("Invalid variable name")
            if node.id not in symbol_table and len(symbol_table) >= 4:
                raise ExecutionError("At most four variables are allowed")
            return symbol_table.setdefault(node.id, sp.Symbol(node.id))
        if isinstance(node, ast.BinOp) and type(node.op) in binary_ops:
            left = visit(node.left)
            right = visit(node.right)
            if isinstance(node.op, ast.Div):
                if not right.is_number or right == 0:
                    raise ExecutionError("Division is limited to a non-zero numeric constant denominator")
                return left / right
            if isinstance(node.op, ast.Pow):
                if not right.is_integer or int(right) < 0 or int(right) > 10:
                    raise ExecutionError("Exponent must be an integer between 0 and 10")
            return binary_ops[type(node.op)](left, right)
        if isinstance(node, ast.UnaryOp) and type(node.op) in unary_ops:
            return unary_ops[type(node.op)](visit(node.operand))
        raise ExecutionError(f"Unsupported expression syntax: {type(node).__name__}")

    return visit(tree)


class SympyEquationAdapter:
    adapter_id = "sympy-equation"

    def __init__(self, timeout_seconds: float = 5.0):
        self.timeout_seconds = timeout_seconds

    def execute(self, inputs: dict[str, Any]) -> dict[str, Any]:
        equation = inputs.get("equation")
        if not isinstance(equation, str) or equation.count("=") != 1:
            raise ExecutionError("equation must be a string containing exactly one '='")
        return _run_sympy_worker(equation, self.timeout_seconds)


def _run_sympy_worker(equation: str, timeout_seconds: float, worker=None) -> dict[str, Any]:
    context = multiprocessing.get_context("spawn")
    parent, child = context.Pipe(duplex=False)
    process = context.Process(target=worker or _sympy_worker, args=(child, equation), daemon=True)
    try:
        process.start()
        child.close()
        process.join(timeout_seconds)
        if process.is_alive():
            process.terminate()
            process.join(1.0)
            if process.is_alive():
                process.kill()
                process.join()
            raise ExecutionError("SymPy solve exceeded the wall-clock time limit", "timeout")
        if not parent.poll():
            raise ExecutionError("SymPy worker exited without a result")
        response = parent.recv()
        if response[0]:
            return response[1]
        _, error_type, message = response
        raise ExecutionError(f"SymPy {error_type}: {message}")
    except (OSError, EOFError) as exc:
        raise ExecutionError("SymPy worker could not be started or read") from exc
    finally:
        parent.close()
        child.close()
        if process.pid is not None and process.is_alive():
            process.terminate()
            process.join(1.0)
            if process.is_alive():
                process.kill()
                process.join()


def _sympy_worker(connection: Any, equation: str) -> None:
    try:
        connection.send((True, _solve_equation(equation)))
    except BaseException as exc:
        connection.send((False, type(exc).__name__, str(exc)))
    finally:
        connection.close()


def _solve_equation(equation: str) -> dict[str, Any]:
    import sympy as sp

    left_text, right_text = (piece.strip() for piece in equation.split("=", 1))
    if not left_text or not right_text:
        raise ExecutionError("Both sides of the equation are required")
    symbols: dict[str, Any] = {}
    left = _safe_sympy_expression(left_text, symbols)
    right = _safe_sympy_expression(right_text, symbols)
    if not symbols:
        equal = sp.simplify(left - right) == 0
        return {
            "equation": equation,
            "solutions": [],
            "constant_equation": True,
            "is_true": bool(equal),
            "verification": {
                "passed": True,
                "method": "exact symbolic simplification",
                "scope": "consistency check only; does not assess model quality",
            },
        }

    difference = sp.simplify(left - right)
    if difference == 0:
        return {
            "equation": equation,
            "solutions": [],
            "solution_space": "all values of the declared variables",
            "verification": {
                "passed": True,
                "method": "exact symbolic simplification",
                "scope": "identity check; solution completeness is not independently certified",
            },
        }
    try:
        polynomial = sp.Poly(difference, *symbols.values())
    except sp.PolynomialError as exc:
        raise ExecutionError("MVP solver supports polynomial equations only") from exc
    if polynomial.total_degree() > 12:
        raise ExecutionError("Polynomial total degree must not exceed 12")
    solutions = sp.solve(polynomial.as_expr(), list(symbols.values()), dict=True)
    rendered = []
    verified = True
    for solution in solutions:
        residual = sp.simplify((left - right).subs(solution))
        row = {str(variable): str(value) for variable, value in solution.items()}
        row["verified"] = bool(residual == 0)
        verified = verified and row["verified"]
        rendered.append(row)
    return {
        "equation": equation,
        "solutions": rendered,
        "verification": {
            "passed": verified,
            "method": "exact symbolic substitution into the original equation",
            "scope": "returned solutions checked; completeness is not independently certified",
        },
    }


class OpenMeteoWeatherNextAdapter:
    adapter_id = "open-meteo-weathernext2"
    endpoint = "https://ensemble-api.open-meteo.com/v1/ensemble"
    _timezone_pattern = re.compile(r"^[A-Za-z0-9_+./-]{1,80}$")

    def __init__(self, timeout_seconds: float = 12.0):
        self.timeout_seconds = timeout_seconds

    def execute(self, inputs: dict[str, Any]) -> dict[str, Any]:
        latitude = inputs.get("latitude")
        longitude = inputs.get("longitude")
        target_date = inputs.get("target_date")
        tz_name = inputs.get("timezone", "UTC")
        if isinstance(latitude, bool) or not isinstance(latitude, (int, float)) or not -90 <= latitude <= 90:
            raise ExecutionError("latitude must be a number between -90 and 90")
        if isinstance(longitude, bool) or not isinstance(longitude, (int, float)) or not -180 <= longitude <= 180:
            raise ExecutionError("longitude must be a number between -180 and 180")
        if not isinstance(target_date, str):
            raise ExecutionError("target_date must be YYYY-MM-DD")
        if not isinstance(tz_name, str) or not self._timezone_pattern.fullmatch(tz_name):
            raise ExecutionError("timezone must be a valid IANA timezone")
        try:
            requested_day = date.fromisoformat(target_date)
            local_today = datetime.now(ZoneInfo(tz_name)).date()
        except (ValueError, ZoneInfoNotFoundError) as exc:
            raise ExecutionError("Invalid target_date or IANA timezone") from exc
        if requested_day < local_today or requested_day > local_today + timedelta(days=14):
            raise ExecutionError("target_date must be within the next 15 local forecast dates")

        query = urlencode({
            "latitude": latitude,
            "longitude": longitude,
            "models": "google_weathernext2_ensemble",
            "daily": "precipitation_sum,rain_sum,precipitation_hours",
            "forecast_days": 15,
            "timezone": tz_name,
        })
        request = Request(
            f"{self.endpoint}?{query}",
            headers={"Accept": "application/json", "User-Agent": "universal-model-router/0.1"},
        )
        try:
            with build_opener(_NoRedirectHandler).open(
                request, timeout=self.timeout_seconds
            ) as response:
                raw = response.read(1_000_001)
                if len(raw) > 1_000_000:
                    raise ExecutionError("Weather provider response exceeded the size limit", "response_too_large")
                payload = json.loads(raw)
        except HTTPError as exc:
            code = "provider_redirect_blocked" if 300 <= exc.code < 400 else "provider_http_error"
            raise ExecutionError(f"Weather provider returned HTTP {exc.code}", code) from exc
        except (URLError, TimeoutError) as exc:
            reason = getattr(exc, "reason", None)
            if isinstance(exc, TimeoutError) or isinstance(reason, TimeoutError):
                raise ExecutionError("Weather provider request timed out", "provider_timeout") from exc
            raise ExecutionError("Weather provider connection failed", "provider_connection_failed") from exc
        except json.JSONDecodeError as exc:
            raise ExecutionError("Weather provider returned invalid JSON", "invalid_json") from exc

        if not isinstance(payload, dict):
            raise ExecutionError("Weather provider returned a non-object JSON response")
        daily = payload.get("daily")
        if not isinstance(daily, dict) or not isinstance(daily.get("time"), list):
            raise ExecutionError("Weather response is missing daily forecast data")
        try:
            index = daily["time"].index(requested_day.isoformat())
        except ValueError as exc:
            raise ExecutionError("Requested date is not present in the provider response") from exc

        def value_at(key: str) -> float | None:
            values = daily.get(key)
            if not isinstance(values, list) or index >= len(values) or values[index] is None:
                return None
            value = values[index]
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                raise ExecutionError(f"Invalid numeric value in {key}")
            if value < 0:
                raise ExecutionError(f"Negative value in {key}")
            return float(value)

        precipitation = value_at("precipitation_sum")
        if precipitation is None:
            raise ExecutionError("Weather response has no usable precipitation_sum for the requested date")

        return {
            "location": {
                "latitude": float(latitude),
                "longitude": float(longitude),
                "timezone": tz_name,
            },
            "target_date": requested_day.isoformat(),
            "precipitation_sum_mm": precipitation,
            "rain_sum_mm": value_at("rain_sum"),
            "precipitation_hours": value_at("precipitation_hours"),
            "model": "Google WeatherNext 2 Ensemble",
            "source": self.endpoint,
            "quality_evidence_level": "none",
            "quality_verified_by_this_project": False,
            "validation": {
                "passed": True,
                "checks": [
                    "response shape",
                    "requested date",
                    "units and non-negative numeric values"
                ],
                "limitation": (
                    "Operational response was not compared with observations; "
                    "hourly and rain fields may be provider-derived from native precipitation."
                )
            },
            "retrieved_at": datetime.now(timezone.utc).isoformat()
        }


class AdapterRegistry:
    def __init__(self, additional_adapters: dict[str, Any] | None = None):
        self._adapters = {
            SympyEquationAdapter.adapter_id: SympyEquationAdapter(),
            OpenMeteoWeatherNextAdapter.adapter_id: OpenMeteoWeatherNextAdapter(),
        }
        for adapter_id, adapter in (additional_adapters or {}).items():
            if not isinstance(adapter_id, str) or not adapter_id or adapter_id in self._adapters:
                raise ValueError("Additional adapter IDs must be nonempty and not replace built-in adapters")
            if not callable(getattr(adapter, "execute", None)):
                raise ValueError("Additional adapters must provide an execute method")
            self._adapters[adapter_id] = adapter

    @property
    def adapter_ids(self) -> set[str]:
        return set(self._adapters)

    def execute(self, adapter_id: str, inputs: dict[str, Any]) -> dict[str, Any]:
        adapter = self._adapters.get(adapter_id)
        if adapter is None:
            raise ExecutionError(f"Adapter is not allowlisted: {adapter_id}")
        return adapter.execute(inputs)
