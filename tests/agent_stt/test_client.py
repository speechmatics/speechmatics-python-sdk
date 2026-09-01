import json

import pytest

from speechmatics.agent_stt import AgentSttAsyncClient
from speechmatics.agent_stt import AudioEncoding
from speechmatics.agent_stt import ClientMessageType
from speechmatics.agent_stt import ServerMessageType
from speechmatics.agent_stt import TranscriptionConfig
from speechmatics.agent_stt import TurnConfig
from speechmatics.agent_stt import TurnDetectionMode

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

    @property
    def messages(self):
        return [json.loads(payload) for payload in self.sent if isinstance(payload, str)]

    @property
    def audio(self):
        return [payload for payload in self.sent if isinstance(payload, bytes)]


async def _noop(*args, **kwargs):
    """Stands in for the handshake steps a stubbed transport never performs."""


@pytest.fixture
def client(monkeypatch):
    monkeypatch.delenv("SPEECHMATICS_RT_URL", raising=False)
    return AgentSttAsyncClient(api_key=API_KEY)


def recognition_started(word_delimiter=" "):
    return {
        "message": ServerMessageType.RECOGNITION_STARTED,
        "id": "session-1",
        "language_pack_info": {"language_description": "English", "word_delimiter": word_delimiter},
    }


def segment_message(transcript, is_final=True, speaker=None, start=0.0, end=1.0):
    segment = {"transcript": transcript}
    if speaker is not None:
        segment["speaker"] = speaker
    return {
        "message": ServerMessageType.ADD_SEGMENT if is_final else ServerMessageType.ADD_PARTIAL_SEGMENT,
        "segment": segment,
        "metadata": {"start_time": start, "end_time": end},
    }


def start_session(client):
    """Put the client in the state it reaches after RecognitionStarted."""
    transport = StubTransport()
    client._transport = transport
    client.emit(ServerMessageType.RECOGNITION_STARTED, recognition_started())
    return transport


@pytest.mark.asyncio
async def test_endpoint_is_the_agent_path(client):
    assert client._transport._url.startswith("wss://eu2.rt.speechmatics.com/v2/agent")


@pytest.mark.asyncio
async def test_app_reaches_the_url(monkeypatch):
    monkeypatch.delenv("SPEECHMATICS_RT_URL", raising=False)
    client = AgentSttAsyncClient(api_key=API_KEY, app="pipecat/1.0")
    assert "/v2/agent" in client._transport._url
    assert "sm-app=pipecat%2F1.0" in client._transport._url


@pytest.mark.asyncio
async def test_sdk_identifier(client):
    assert "sm-sdk=python-agent-stt-sdk-v" in client._transport._prepare_url()


@pytest.mark.asyncio
async def test_audio_format_defaults_to_16k_pcm(client):
    assert client._audio_format.encoding == AudioEncoding.PCM_S16LE
    assert client._audio_format.sample_rate == 16000


@pytest.mark.asyncio
async def test_recognition_started_sets_session_state(client):
    start_session(client)
    assert client.is_ready_for_audio
    assert client.session_info.session_id == "session-1"
    assert client.session_info.language_pack_info.language_description == "English"


@pytest.mark.asyncio
async def test_transcript_accumulates_from_segments(client):
    start_session(client)
    client.emit(ServerMessageType.ADD_PARTIAL_SEGMENT, segment_message("Hello th", is_final=False))
    client.emit(ServerMessageType.ADD_SEGMENT, segment_message("Hello there."))
    client.emit(ServerMessageType.ADD_SEGMENT, segment_message("How are you?"))

    assert client.transcript == "Hello there. How are you?"
    assert client.partial_segment is None
    assert [segment.transcript for segment in client.segments] == ["Hello there.", "How are you?"]


@pytest.mark.asyncio
async def test_transcript_uses_language_pack_delimiter(client):
    client._transport = StubTransport()
    client.emit(ServerMessageType.RECOGNITION_STARTED, recognition_started(word_delimiter=""))
    client.emit(ServerMessageType.ADD_SEGMENT, segment_message("你好"))
    client.emit(ServerMessageType.ADD_SEGMENT, segment_message("世界"))
    assert client.transcript == "你好世界"


@pytest.mark.asyncio
async def test_transcript_with_speaker_labels(client):
    start_session(client)
    client.emit(ServerMessageType.ADD_SEGMENT, segment_message("Hello.", speaker="S1"))
    client.emit(ServerMessageType.ADD_SEGMENT, segment_message("Hi.", speaker="S2"))
    assert client.transcript_text(speaker_labels=True) == "S1: Hello. S2: Hi."


@pytest.mark.asyncio
async def test_timeline_records_speech_and_turn_events(client):
    start_session(client)
    client.emit(ServerMessageType.SPEECH_STARTED, {"message": "SpeechStarted", "metadata": {"start_time": 0.5}})
    client.emit(ServerMessageType.START_OF_TURN, {"message": "StartOfTurn", "metadata": {"start_time": 0.5}})
    client.emit(ServerMessageType.SPEECH_ENDED, {"message": "SpeechEnded", "metadata": {"end_time": 2.0}})
    client.emit(ServerMessageType.END_OF_TURN, {"message": "EndOfTurn", "metadata": {"end_time": 2.2}})

    assert [(event.message, event.time) for event in client.timeline] == [
        ("SpeechStarted", 0.5),
        ("StartOfTurn", 0.5),
        ("SpeechEnded", 2.0),
        ("EndOfTurn", 2.2),
    ]


@pytest.mark.asyncio
async def test_every_message_is_recorded(client):
    start_session(client)
    unmodelled = {"message": "SomeFutureMessage", "metadata": {"value": 1}}
    client.emit("SomeFutureMessage", unmodelled)

    recorded = [event["message"] for event in client.events]
    assert recorded == [ServerMessageType.RECOGNITION_STARTED, "SomeFutureMessage"]
    assert client.events[-1] == unmodelled


@pytest.mark.asyncio
async def test_event_recording_can_be_disabled(monkeypatch):
    monkeypatch.delenv("SPEECHMATICS_RT_URL", raising=False)
    client = AgentSttAsyncClient(api_key=API_KEY, record_events=False)
    start_session(client)
    assert client.events == []
    assert client.session_info.session_id == "session-1"


@pytest.mark.asyncio
async def test_audio_dropped_until_session_is_ready(client):
    transport = StubTransport()
    client._transport = transport

    await client.send_audio(b"\x00" * 32)
    assert transport.audio == []

    client.emit(ServerMessageType.RECOGNITION_STARTED, recognition_started())
    await client.send_audio(b"\x00" * 32)
    assert transport.audio == [b"\x00" * 32]


@pytest.mark.asyncio
async def test_finalize_sends_force_end_of_utterance_with_timestamp(client):
    transport = start_session(client)
    await client.send_audio(b"\x00" * 32000)  # 1 second of 16 kHz signed 16-bit PCM

    await client.force_end_of_utterance()

    assert transport.messages == [
        {"message": ClientMessageType.FORCE_END_OF_UTTERANCE.value, "timestamp": 1.0},
    ]


@pytest.mark.asyncio
async def test_finalize_accepts_an_explicit_timestamp(client):
    transport = start_session(client)
    await client.force_end_of_utterance(timestamp=4.2)
    assert transport.messages[0]["timestamp"] == 4.2


@pytest.mark.asyncio
async def test_finalize_can_omit_the_timestamp(client):
    transport = start_session(client)
    await client.force_end_of_utterance(timestamp=None)
    assert "timestamp" not in transport.messages[0]


@pytest.mark.asyncio
async def test_sync_finalize_schedules_the_send(client):
    transport = start_session(client)
    await client.send_audio(b"\x00" * 16000)  # 0.5 seconds

    client.finalize()
    assert transport.messages == []  # scheduled, not yet sent

    await _drain()
    assert transport.messages == [
        {"message": ClientMessageType.FORCE_END_OF_UTTERANCE.value, "timestamp": 0.5},
    ]


@pytest.mark.asyncio
async def test_finalize_latency_measured_against_the_flushed_segment(client):
    start_session(client)
    assert client.last_finalize_latency == 0.0

    await client.force_end_of_utterance()
    client.emit(ServerMessageType.ADD_SEGMENT, segment_message("Hello there."))
    assert client.last_finalize_latency > 0.0


@pytest.mark.parametrize(
    ("mode", "expected"),
    [(TurnDetectionMode.VAD, "vad"), (TurnDetectionMode.EXTERNAL, "external")],
)
@pytest.mark.asyncio
async def test_turn_detection_reaches_start_recognition(client, mode, expected):
    transport = StubTransport()
    client._transport = transport
    client._turn_config = TurnConfig(turn_detection_mode=mode)

    await client.send_message(
        {
            "message": ClientMessageType.START_RECOGNITION.value,
            "transcription_config": client._transcription_config.to_dict(),
        }
    )

    sent = transport.messages[0]
    assert sent["turn_config"] == {"turn_detection_mode": expected}
    assert "vad_config" not in sent["transcription_config"]


@pytest.mark.asyncio
async def test_start_session_turn_config_wins_over_the_constructor(client, monkeypatch):
    """A turn config passed to start_session must replace the constructor's, not be ignored."""
    transport = StubTransport()
    client._transport = transport
    client._turn_config = TurnConfig(turn_detection_mode=TurnDetectionMode.EXTERNAL)
    monkeypatch.setattr(client, "_ws_connect", _noop)
    monkeypatch.setattr(client, "_wait_recognition_started", _noop)

    await client.start_session(turn_config=TurnConfig(turn_detection_mode=TurnDetectionMode.VAD))

    assert transport.messages[0]["turn_config"] == {"turn_detection_mode": "vad"}


@pytest.mark.asyncio
async def test_reset_transcript(client):
    start_session(client)
    client.emit(ServerMessageType.ADD_SEGMENT, segment_message("Hello."))
    client.reset_transcript()
    assert client.transcript == ""
    assert client.events == []


@pytest.mark.asyncio
async def test_close_clears_session_state(client):
    transport = start_session(client)
    await client.close()
    assert transport.closed
    assert not client.is_connected
    assert not client.is_ready_for_audio


async def _drain():
    """Let scheduled tasks run."""
    import asyncio

    await asyncio.sleep(0)
    await asyncio.sleep(0)
