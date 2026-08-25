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
