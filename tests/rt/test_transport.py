import pytest

import speechmatics.rt._transport as transport_module
from speechmatics.rt import ConnectionConfig
from speechmatics.rt import StaticKeyAuth
from speechmatics.rt._transport import Transport


class FakeWebSocket:
    async def close(self):
        pass


@pytest.mark.asyncio
async def test_request_id_is_sent_as_a_header(monkeypatch):
    """The request_id we generate must actually reach the server, not just local logs."""
    captured = {}

    async def fake_connect(url, **kwargs):
        captured["kwargs"] = kwargs
        return FakeWebSocket()

    monkeypatch.setattr(transport_module, "connect", fake_connect)

    transport = Transport("wss://example.com/v2", ConnectionConfig(), StaticKeyAuth("key"), "my-request-id")
    await transport.connect()

    headers = captured["kwargs"][transport_module.WS_HEADERS_KEY]
    assert headers["X-Request-Id"] == "my-request-id"


@pytest.mark.asyncio
async def test_caller_supplied_request_id_header_is_not_overridden(monkeypatch):
    captured = {}

    async def fake_connect(url, **kwargs):
        captured["kwargs"] = kwargs
        return FakeWebSocket()

    monkeypatch.setattr(transport_module, "connect", fake_connect)

    transport = Transport("wss://example.com/v2", ConnectionConfig(), StaticKeyAuth("key"), "my-request-id")
    await transport.connect(ws_headers={"X-Request-Id": "caller-supplied"})

    headers = captured["kwargs"][transport_module.WS_HEADERS_KEY]
    assert headers["X-Request-Id"] == "caller-supplied"


@pytest.mark.asyncio
async def test_connect_does_not_mutate_caller_supplied_headers_dict(monkeypatch):
    """A caller reusing the same ws_headers dict across sessions must get each session's
    own X-Request-Id sent, not have the first session's id written into their dict and
    silently reused (via setdefault no-op) on every later connect()."""
    captured = []

    async def fake_connect(url, **kwargs):
        captured.append(dict(kwargs[transport_module.WS_HEADERS_KEY]))
        return FakeWebSocket()

    monkeypatch.setattr(transport_module, "connect", fake_connect)

    shared_headers = {}

    transport1 = Transport("wss://example.com/v2", ConnectionConfig(), StaticKeyAuth("key"), "req-1")
    await transport1.connect(ws_headers=shared_headers)

    transport2 = Transport("wss://example.com/v2", ConnectionConfig(), StaticKeyAuth("key"), "req-2")
    await transport2.connect(ws_headers=shared_headers)

    assert shared_headers == {}
    assert captured[0]["X-Request-Id"] == "req-1"
    assert captured[1]["X-Request-Id"] == "req-2"
