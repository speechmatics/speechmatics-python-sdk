import asyncio

import pytest
import pytest_asyncio

from speechmatics.rt import AsyncClient
from speechmatics.rt import AsyncMultiChannelClient
from speechmatics.rt import ServerMessageType
from speechmatics.rt import TimeoutError as RTTimeoutError
from speechmatics.rt import TranscriptionError
from speechmatics.rt._exceptions import TransportError

API_KEY = "test-key"


class StubTransport:
    """Captures what the client sends instead of opening a WebSocket."""

    def __init__(self):
        self.sent = []
        self.closed = False

    async def send_message(self, payload):
        self.sent.append(payload)

    async def close(self):
        self.closed = True


class RaisingTransport:
    """A transport whose receive_message() fails immediately, simulating a dropped connection."""

    def __init__(self, error=None):
        self.error = error or TransportError("connection reset")
        self.closed = False

    async def receive_message(self):
        raise self.error

    async def close(self):
        self.closed = True


class SessionStubTransport:
    """A stub transport that accepts RecognitionStarted on connect, for a full session lifecycle."""

    def __init__(self, request_id):
        self.request_id = request_id
        self.sent = []
        self.closed = False
        self._queue = asyncio.Queue()

    async def connect(self, headers=None):
        self._queue.put_nowait({"message": "RecognitionStarted", "id": f"session-{self.request_id}"})

    async def send_message(self, payload):
        self.sent.append(payload)

    async def receive_message(self):
        return await self._queue.get()

    async def close(self):
        self.closed = True


@pytest_asyncio.fixture
async def client(monkeypatch):
    # Must construct AsyncClient (and its internal asyncio.Event()s) inside the test's own
    # running loop: on Python 3.9, Event() binds to whatever loop is current at construction,
    # and a plain sync fixture runs outside the loop pytest-asyncio sets up for the test.
    monkeypatch.delenv("SPEECHMATICS_RT_URL", raising=False)
    c = AsyncClient(api_key=API_KEY)
    c._transport = StubTransport()
    return c


def error_message(reason="Not Authorized", error_type="not_authorised"):
    return {"message": ServerMessageType.ERROR, "type": error_type, "reason": reason}


@pytest.mark.asyncio
async def test_wait_recognition_started_returns_once_started(client):
    client.emit(ServerMessageType.RECOGNITION_STARTED, {"message": "RecognitionStarted", "id": "s1"})
    await client._wait_recognition_started(timeout=1.0)  # must not raise or hang


@pytest.mark.asyncio
async def test_error_before_recognition_started_raises_transcription_error(client):
    client.emit(ServerMessageType.ERROR, error_message())

    with pytest.raises(TranscriptionError, match="Not Authorized"):
        await client._wait_recognition_started(timeout=5.0)


@pytest.mark.asyncio
async def test_end_of_transcript_before_recognition_started_raises_transcription_error(client):
    client.emit(ServerMessageType.END_OF_TRANSCRIPT, {"message": "EndOfTranscript"})

    with pytest.raises(TranscriptionError, match="Session ended before RecognitionStarted"):
        await client._wait_recognition_started(timeout=5.0)


@pytest.mark.asyncio
async def test_no_response_raises_the_typed_timeout_error(client):
    with pytest.raises(RTTimeoutError):
        await client._wait_recognition_started(timeout=0.05)


@pytest.mark.asyncio
async def test_failed_handshake_closes_the_transport(client):
    """A session that never gets RecognitionStarted must not leak the connection or the
    receive task - otherwise a caller retrying without an explicit close() first would reuse
    a half-open transport instead of getting the fresh one _begin_new_session builds."""
    client._transport = SessionStubTransport(client.request_id)
    client._transport.connect = lambda headers=None: asyncio.sleep(3600)  # never responds

    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(client._start_recognition_session(), timeout=0.05)

    assert client._closed_evt.is_set()
    assert client._transport.closed


@pytest.mark.asyncio
async def test_close_after_error_does_not_leak_cancelled_error(client):
    """The recv loop is still winding down when close() cancels it - that must not surface."""
    client._recv_task = asyncio.get_event_loop().create_task(asyncio.sleep(10))
    await client.close()  # must not raise CancelledError
    assert client._transport.closed


@pytest.mark.asyncio
async def test_second_session_gets_a_fresh_request_id_and_transport(client):
    """Regression test: a client reused for a second session used to keep the first
    session's request_id, and its Transport - permanently closed by the first close() -
    could never reconnect at all."""
    client._transport = SessionStubTransport(client.request_id)
    client._build_transport = SessionStubTransport

    await client.start_session()
    first_request_id = client.request_id
    first_transport = client._transport
    assert client.session_id == f"session-{first_request_id}"

    await client.close()
    await client.start_session()

    assert client.request_id != first_request_id
    assert client._transport is not first_transport
    assert client.session_id == f"session-{client.request_id}"

    await client.close()


@pytest.mark.asyncio
async def test_multi_channel_client_second_session_gets_a_fresh_request_id(monkeypatch):
    monkeypatch.delenv("SPEECHMATICS_RT_URL", raising=False)
    client = AsyncMultiChannelClient(api_key=API_KEY)
    client._transport = SessionStubTransport(client.request_id)
    client._build_transport = SessionStubTransport

    await client._start_recognition_session()
    first_request_id = client.request_id

    await client.close()
    await client._start_recognition_session()

    assert client.request_id != first_request_id

    await client.close()


@pytest.mark.asyncio
async def test_async_client_logger_keeps_its_own_name(client):
    """_BaseClient.__init__ must not clobber the subclass-specific logger AsyncClient set
    before calling super().__init__() - otherwise per-logger filtering/level config aimed
    at 'speechmatics.rt.async_client' silently gets no output."""
    assert client._logger.name == "speechmatics.rt.async_client"


@pytest.mark.asyncio
async def test_recv_loop_error_unblocks_wait_for_recognition_started(client):
    """A transport failure before RecognitionStarted must be reported as the real error
    promptly, not swallowed until the full timeout elapses - _recv_loop's exception path
    has to wake _wait_started_or_session_done via _session_done_evt, not just _closed_evt."""
    client._transport = RaisingTransport()
    client._recv_task = asyncio.get_event_loop().create_task(client._recv_loop())

    with pytest.raises(TranscriptionError):
        await asyncio.wait_for(client._wait_recognition_started(timeout=5.0), timeout=1.0)

    assert client._closed_evt.is_set()


@pytest.mark.asyncio
async def test_multi_channel_on_error_logs_the_reason(caplog):
    """AsyncMultiChannelClient._on_error must log server errors like AsyncClient._on_error
    does, otherwise a failed multi-channel session leaves no trace before RecognitionStarted."""
    client = AsyncMultiChannelClient(api_key=API_KEY)

    with caplog.at_level("ERROR", logger="speechmatics.rt.async_multi_chan_client"):
        client.emit(ServerMessageType.ERROR, error_message("Not Authorized"))

    assert "Not Authorized" in caplog.text
