import json
import os
import statistics
import time

import pytest
from _utils import get_client
from _utils import send_audio_file
from pydantic import Field

from speechmatics.rt import AsyncClient
from speechmatics.rt import AudioEncoding
from speechmatics.rt import AudioFormat
from speechmatics.voice import AgentServerMessageType
from speechmatics.voice._models import BaseModel
from speechmatics.voice._models import VoiceActivityConfig
from speechmatics.voice._models import VoiceAgentConfig
from speechmatics.voice._presets import VoiceAgentConfigPreset

# Constants
API_KEY = os.getenv("SPEECHMATICS_API_KEY")
SHOW_LOG = os.getenv("SPEECHMATICS_SHOW_LOG", "0").lower() in ["1", "true"]

# The live A/B latency test needs an API key and network; the timestamp unit test below
# is deterministic and offline, so gate only the live test rather than the whole module.
requires_live = pytest.mark.skipif(
    API_KEY is None or os.getenv("CI") == "true",
    reason="Requires a live API key and network; skipped in CI or when no key is set",
)


class TranscriptionSpeaker(BaseModel):
    text: str
    speaker_id: str = "S1"
    start_time: float = 0.0
    end_time: float = 0.0


class TranscriptionTest(BaseModel):
    id: str
    path: str
    sample_rate: int
    language: str
    segments: list[TranscriptionSpeaker] = Field(default_factory=list)


# Audio file with several short utterances, giving one forced EOU per utterance
# and so multiple FEOU -> EndOfUtterance latency samples per run.
SAMPLE: TranscriptionTest = TranscriptionTest.from_dict(
    {
        "id": "08",
        "path": "./assets/audio_08_16kHz.wav",
        "sample_rate": 16000,
        "language": "en",
        "segments": [
            {"text": "Hello.", "start_time": 0.4, "end_time": 0.75},
            {"text": "Goodbye.", "start_time": 2.12, "end_time": 2.5},
            {"text": "Banana.", "start_time": 3.84, "end_time": 4.27},
            {"text": "Breakaway.", "start_time": 5.62, "end_time": 6.42},
            {"text": "Before.", "start_time": 7.76, "end_time": 8.16},
            {"text": "After.", "start_time": 9.56, "end_time": 10.05},
        ],
    }
)

# VAD silence duration (uses VAD end-of-turn detection, not smart turn).
VAD_DELAY_S = 0.18

# Endpoint
ENDPOINT = "wss://eu.rt.speechmatics.com/v2"


class LatencyRun(BaseModel):
    """Result of a single transcription run."""

    compensate: bool
    latencies: list[float] = Field(default_factory=list)
    segment_count: int = 0

    @property
    def mean_ms(self) -> float:
        return statistics.mean(self.latencies) * 1000 if self.latencies else 0.0


async def measure_run(endpoint: str, sample: TranscriptionTest, compensate: bool) -> LatencyRun:
    """Run the sample once and measure per-utterance FEOU -> EndOfUtterance latency.

    Uses the ADAPTIVE preset (VAD-driven end of turn, no smart turn) and toggles
    feou_latency_compensation so the same audio can be compared with and without
    the fix. Latency is measured client-side as the wall-clock time between the
    ForceEndOfUtterance being sent and the EndOfUtterance arriving.
    """

    # ADAPTIVE preset = VAD end-of-turn detection (no smart turn), with the
    # compensation flag toggled for this run.
    config = VoiceAgentConfigPreset.ADAPTIVE(
        VoiceAgentConfig(
            vad_config=VoiceActivityConfig(enabled=True, silence_duration=VAD_DELAY_S),
            feou_latency_compensation=compensate,
        )
    )

    # Client
    client = await get_client(url=endpoint, api_key=API_KEY, connect=False, config=config)

    # Run state
    result = LatencyRun(compensate=compensate)
    pending_sent: dict[str, float] = {}

    # Mark when a ForceEndOfUtterance is sent
    def on_diagnostic(message):
        if "ForceEndOfUtterance sent" in str(message.get("msg", "")):
            pending_sent["t"] = time.perf_counter()

    # Pair the next EndOfUtterance with the last ForceEndOfUtterance sent
    def on_end_of_utterance(message):
        sent = pending_sent.pop("t", None)
        if sent is not None:
            result.latencies.append(time.perf_counter() - sent)

    # Count finalized segments (transcript integrity check)
    def on_segment(message):
        result.segment_count += len(message.get("segments", []))

    # Listeners
    client.on(AgentServerMessageType.DIAGNOSTICS, on_diagnostic)
    client.on(AgentServerMessageType.END_OF_UTTERANCE, on_end_of_utterance)
    client.on(AgentServerMessageType.ADD_SEGMENT, on_segment)

    # Connect
    try:
        await client.connect()
    except Exception:
        pytest.skip("Failed to connect to server")

    # Check we are connected
    assert client._is_connected

    # Stream the audio at real time
    await send_audio_file(client, sample.path)

    # Close session
    await client.disconnect()
    assert not client._is_connected

    return result


@pytest.mark.asyncio
@requires_live
async def test_feou_latency_compensation():
    """Compare FEOU -> EndOfUtterance latency with and without the compensation fix.

    Streams the same audio twice using VAD-driven end of turn: once with
    feou_latency_compensation disabled (baseline) and once enabled (fix). The
    injected silence should roughly halve the forced EOU response latency while
    leaving the transcript unchanged.
    """

    # Baseline (no fix) then compensated (fix)
    baseline = await measure_run(ENDPOINT, SAMPLE, compensate=False)
    compensated = await measure_run(ENDPOINT, SAMPLE, compensate=True)

    # Summary (printed with pytest -s)
    reduction = (1 - compensated.mean_ms / baseline.mean_ms) * 100 if baseline.mean_ms else 0.0
    print("\n=== FEOU -> EndOfUtterance latency ===")
    print(f"  baseline    (no fix): {baseline.mean_ms:6.1f} ms  over {len(baseline.latencies)} utterance(s)")
    print(f"  compensated (fix)   : {compensated.mean_ms:6.1f} ms  over {len(compensated.latencies)} utterance(s)")
    print(f"  reduction           : {reduction:6.1f}%")
    if SHOW_LOG:
        print(f"  baseline samples    : {[round(x * 1000) for x in baseline.latencies]} ms")
        print(f"  compensated samples : {[round(x * 1000) for x in compensated.latencies]} ms")
        print(f"  segments (base/comp): {baseline.segment_count} / {compensated.segment_count}")

    # We need latency samples from both runs to compare
    assert baseline.latencies, "No forced EOU latencies captured for the baseline run"
    assert compensated.latencies, "No forced EOU latencies captured for the compensated run"

    # Transcript must be unaffected by the injected silence
    assert baseline.segment_count > 0, "Baseline run produced no segments"
    assert compensated.segment_count == baseline.segment_count, (
        f"Compensation changed the transcript: {compensated.segment_count} segments "
        f"vs baseline {baseline.segment_count}"
    )

    # The compensation should reduce mean forced EOU latency
    assert compensated.mean_ms < baseline.mean_ms, (
        f"Compensation did not reduce latency: {compensated.mean_ms:.1f} ms "
        f"vs baseline {baseline.mean_ms:.1f} ms"
    )


class _FakeTransport:
    """Captures outbound audio bytes and JSON messages without a network."""

    def __init__(self):
        self.messages: list[dict] = []
        self.audio_bytes: int = 0

    async def send_message(self, data):
        if isinstance(data, (bytes, bytearray)):
            self.audio_bytes += len(data)
        else:
            self.messages.append(json.loads(data))


def _offline_client(sample_rate: int = 16000) -> AsyncClient:
    """An RT client wired to a fake transport, ready to send FEOUs offline."""
    client = AsyncClient(api_key="test")
    client._transport = _FakeTransport()
    client._audio_format = AudioFormat(encoding=AudioEncoding.PCM_S16LE, sample_rate=sample_rate)
    return client


@pytest.mark.asyncio
async def test_explicit_feou_timestamp_shifted_onto_server_timeline():
    """A manually supplied FEOU timestamp is real-audio time and is mapped correctly.

    When compensation has injected silence, the server audio timeline runs ahead of the
    real audio. An explicit timestamp (which the caller expresses in real audio time) must
    be shifted onto the server timeline by the silence injected so far - the inverse of
    adjust_timestamp - so it stays aligned across successive forced EOUs. This is offline
    and deterministic (no network).
    """
    rate, bps = 16000, 2
    client = _offline_client(rate)

    # 5.0s of real audio streamed; first compensated FEOU at real speech-end 5.0s.
    # No silence has been injected yet, so the timestamp is sent unchanged.
    client._audio_bytes_sent = int(5.0 * rate * bps)
    await client.force_end_of_utterance(timestamp=5.0, compensate_latency=True)
    assert client._transport.messages[-1]["timestamp"] == pytest.approx(5.0)

    injected = client.injected_silence_seconds
    assert injected > 0, "compensation should have injected silence"

    # 3.0s more real audio; next FEOU at real speech-end 8.0s. The explicit real-audio
    # time is shifted onto the server timeline by the silence injected so far.
    client._audio_bytes_sent += int(3.0 * rate * bps)
    await client.force_end_of_utterance(timestamp=8.0, compensate_latency=True)
    sent = client._transport.messages[-1]["timestamp"]
    assert sent == pytest.approx(8.0 + injected)

    # ...and it maps straight back to real audio time.
    assert client.adjust_timestamp(sent) == pytest.approx(8.0)


@pytest.mark.asyncio
async def test_explicit_feou_timestamp_unchanged_without_injection():
    """Without injected silence an explicit timestamp is sent verbatim (backward compat)."""
    rate, bps = 16000, 2
    client = _offline_client(rate)
    client._audio_bytes_sent = int(4.0 * rate * bps)

    await client.force_end_of_utterance(timestamp=4.0, compensate_latency=False)
    assert client._transport.messages[-1]["timestamp"] == pytest.approx(4.0)
    assert client.injected_silence_seconds == 0.0
