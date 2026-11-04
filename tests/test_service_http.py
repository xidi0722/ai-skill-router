import json
from http.server import ThreadingHTTPServer
from io import BytesIO
from threading import Thread
from urllib.error import HTTPError
from urllib.request import ProxyHandler, Request, build_opener

import pytest

from umr.execution import ExecutionError
from umr.http_api import make_handler
from umr.registry import HuggingFaceHubConnector
from umr.service import RouterService


def test_service_math_route_execute_and_strict_abstain(root):
    service = RouterService(root / "profiles")
    result = service.handle({
        "task_id": "math.solve_equation",
        "inputs": {"equation": "x**2 - 4 = 0"},
        "execute": True,
    })
    assert result["decision"]["status"] == "selected"
    assert result["execution"]["status"] == "completed"
    assert len(result["provenance"]["input_digest_sha256"]) == 64

    strict = service.handle({
        "task_id": "math.solve_equation",
        "inputs": {"equation": "x=1"},
        "constraints": {"require_independent_evidence": True},
    })
    assert strict["decision"]["status"] == "abstain"


def test_service_rejects_invalid_input_and_output_contracts(root, monkeypatch):
    service = RouterService(root / "profiles")
    invalid = service.handle({"task_id": "math.solve_equation", "inputs": {"equation": 4}})
    assert invalid["decision"]["status"] == "abstain"
    monkeypatch.setattr(service.adapters, "execute", lambda *_args: {"wrong": True})
    result = service.handle({
        "task_id": "math.solve_equation",
        "inputs": {"equation": "x=1"},
        "execute": True,
    })
    assert result["execution"]["status"] == "failed"
    assert result["execution"]["error"]["code"] == "output_schema_validation_failed"
    assert result["provenance"]["adapter"] == "sympy-equation"


def test_service_execution_errors_are_structured_and_redacted(root, monkeypatch):
    service = RouterService(root / "profiles")

    def fail_with_sensitive_detail(*_args):
        raise ExecutionError("request https://provider.invalid/?coordinates=24,121", "provider_timeout")

    monkeypatch.setattr(service.adapters, "execute", fail_with_sensitive_detail)
    result = service.handle({
        "task_id": "math.solve_equation",
        "inputs": {"equation": "x=1"},
        "execute": True,
    })
    assert result["decision"]["status"] == "selected"
    assert result["execution"]["status"] == "failed"
    assert result["execution"]["error"]["code"] == "provider_timeout"
    assert "coordinates" not in result["execution"]["error"]["message"]
    assert result["provenance"]["profile_id"].endswith(":sympy-equation")
    assert result["provenance"]["deployment_id"] == "sympy-equation-local"


def test_huggingface_metadata_discovery_never_becomes_executable(monkeypatch, root):
    connector = HuggingFaceHubConnector()
    payload = json.dumps([{
        "id": "example/math-model",
        "modelId": "example/math-model",
        "pipeline_tag": "text-classification",
        "downloads": 123,
        "sha": "abc123",
    }]).encode()

    class Response:
        def __enter__(self): return self
        def __exit__(self, *_args): return False
        def read(self, limit): return payload[:limit]

    class Opener:
        def open(self, *_args, **_kwargs): return Response()

    monkeypatch.setattr("umr.registry.build_opener", lambda *_args: Opener())
    found = connector.search_models("text.text_classification")
    assert len(found) == 1 and found[0]["deployments"] == []
    service = RouterService(root / "profiles")
    monkeypatch.setattr(service.hf_connector, "search_models", lambda *_args, **_kwargs: found)
    result = service.handle({
        "task_id": "text.text_classification",
        "inputs": {},
        "constraints": {"discover_huggingface": True},
    })
    assert result["decision"]["status"] == "abstain"


def _invoke_handler(handler_type, path, payload=b""):
    handler = handler_type.__new__(handler_type)
    handler.path = path
    handler.headers = {"Content-Length": str(len(payload))}
    handler.rfile = BytesIO(payload)
    captured = {}
    handler._send = lambda status, body: captured.update(status=status, body=body)
    if path == "/route":
        handler.do_POST()
    else:
        handler.do_GET()
    return captured


def test_http_handler_success_invalid_json_and_request_errors(root):
    handler = make_handler(root / "profiles")
    health = _invoke_handler(handler, "/health")
    assert health["status"] == 200 and health["body"]["status"] == "ok"

    success = _invoke_handler(handler, "/route", json.dumps({
        "task_id": "math.solve_equation", "inputs": {"equation": "x=1"}
    }).encode())
    assert success["status"] == 200
    assert success["body"]["decision"]["status"] == "selected"

    invalid = _invoke_handler(handler, "/route", b"{")
    assert invalid["status"] == 400
    assert invalid["body"]["error"]["code"] == "invalid_request"

    missing = _invoke_handler(handler, "/route", b'{"inputs":{}}')
    assert missing["status"] == 400
    assert missing["body"]["error"]["code"] == "invalid_request"

    failed = _invoke_handler(handler, "/route", json.dumps({
        "task_id": "math.solve_equation",
        "inputs": {"equation": "x**13=1"},
        "execute": True,
    }).encode())
    assert failed["status"] == 200
    assert failed["body"]["execution"]["status"] == "failed"
    assert failed["body"]["execution"]["error"]["code"] == "adapter_execution_failed"
    assert failed["body"]["provenance"]["adapter"] == "sympy-equation"


def test_http_api_loopback_tcp_smoke(root):
    try:
        server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(root / "profiles"))
    except PermissionError:
        pytest.skip("sandbox policy blocks localhost TCP sockets")
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    client = build_opener(ProxyHandler({}))
    base = f"http://127.0.0.1:{server.server_port}"
    try:
        health = json.loads(client.open(f"{base}/health", timeout=2).read())
        assert health["status"] == "ok"
        payload = json.dumps({"task_id": "math.solve_equation", "inputs": {"equation": "x=1"}}).encode()
        response = json.loads(client.open(Request(
            f"{base}/route", data=payload, headers={"Content-Type": "application/json"}
        ), timeout=2).read())
        assert response["decision"]["status"] == "selected"
        assert response["execution"]["status"] == "not_requested"
        try:
            client.open(Request(f"{base}/route", data=b"{", headers={"Content-Type": "application/json"}), timeout=2)
        except HTTPError as error:
            assert error.code == 400
            assert json.loads(error.read())["error"]["code"] == "invalid_request"
        else:
            raise AssertionError("invalid JSON should return HTTP 400")
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
