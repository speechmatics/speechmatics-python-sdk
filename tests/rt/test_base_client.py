import asyncio

import pytest
import pytest_asyncio

from speechmatics.rt import AsyncClient
from speechmatics.rt import AsyncMultiChannelClient
from speechmatics.rt import ServerMessageType
from speechmatics.rt import TimeoutError as RTTimeoutError
from speechmatics.rt import TranscriptionError

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
async def test_request_id_and_session_id_properties(client):
    assert client.request_id == client._session.request_id
    assert client.session_id is None

    client.emit(ServerMessageType.RECOGNITION_STARTED, {"message": "RecognitionStarted", "id": "s1"})
    assert client.session_id == "s1"


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
