"""MC-INSPECT-04 A: Worker runtime visibility tests."""

from __future__ import annotations

from mission_control.worker_runtime import read_worker_runtime


class _Payload:
    def __init__(self, data, status=200):
        self._data = data
        self.status_code = status

    def json(self):
        return self._data


class _Client:
    def __init__(self, routes: dict):
        self.routes = routes
        self.calls: list[str] = []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def get(self, url: str):
        self.calls.append(url)
        for suffix, payload in self.routes.items():
            if url.endswith(suffix):
                data, status = payload
                return _Payload(data, status)
        return _Payload({}, 404)


def _patch(monkeypatch, routes):
    import mission_control.worker_runtime as wr

    client = _Client(routes)

    class _HttpxClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return client

        def __exit__(self, *args):
            return False

    monkeypatch.setattr(wr.httpx, "Client", _HttpxClient)
    return client


def test_reads_usage_and_availability_without_probe(monkeypatch):
    routes = {
        "/health": ({"status": "ok", "version": "test", "listen": "127.0.0.1:7317"}, 200),
        "/v1/models/availability": (
            {"schema_version": "worker.model-availability.v1", "models": [], "warnings": ["w"]},
            200,
        ),
        "/v1/models/usage": (
            {
                "schema_version": "worker.model-usage.v1",
                "scope": "worker-process-jobs",
                "outcomes": {"accepted": 1},
                "billed": {"known_calls": 1, "unknown_calls": 2},
                "estimated": {},
                "models": [],
            },
            200,
        ),
        "/v1/models/preflight": ({"ok": True}, 200),
    }
    client = _patch(monkeypatch, routes)
    result = read_worker_runtime("http://127.0.0.1:7317")
    assert result["available"] is True
    assert result["usage"]["available"] is True
    assert result["usage"]["billed"]["unknown_calls"] == 2
    assert result["availability"]["available"] is True
    assert all("/probe" not in call for call in client.calls)
    assert any("Cached availability" in note for note in result["notes"])


def test_outage_is_honest_unavailable(monkeypatch):
    import httpx
    import mission_control.worker_runtime as wr

    class _FailClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def get(self, url: str):
            raise httpx.ConnectError("refused")

    monkeypatch.setattr(wr.httpx, "Client", _FailClient)
    result = read_worker_runtime("http://127.0.0.1:7317")
    assert result["available"] is False
    assert result["usage"]["available"] is False
    assert result["availability"]["available"] is False


def test_unknown_cost_never_zero(monkeypatch):
    routes = {
        "/health": ({"status": "ok"}, 200),
        "/v1/models/availability": ({"schema_version": "x", "models": []}, 200),
        "/v1/models/usage": (
            {"schema_version": "worker.model-usage.v1", "billed": {}, "models": []},
            200,
        ),
        "/v1/models/preflight": ({}, 200),
    }
    _patch(monkeypatch, routes)
    result = read_worker_runtime("http://127.0.0.1:7317")
    assert result["usage"]["billed_unknown_calls"] is None
