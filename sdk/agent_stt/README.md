# Speechmatics Agent STT SDK

Python client for the Speechmatics **Agent STT** service, built on
[`speechmatics-rt`](https://pypi.org/project/speechmatics-rt/).

The Agent STT service works in **segments** rather than word groups, and reports the speech and
turn events a voice agent needs. This SDK runs **no VAD and no turn detection of its own** -
either the service's VAD closes turns, or your application's does.

```bash
pip install speechmatics-agent-stt
```

## Quick start

```python
import asyncio
from speechmatics.agent_stt import AsyncClient, ServerMessageType, TranscriptionConfig

async def main():
    # Uses SPEECHMATICS_API_KEY from the environment
    async with AsyncClient(config=TranscriptionConfig(language="en", enable_partials=True)) as client:
        @client.on(ServerMessageType.ADD_SEGMENT)
        def handle_segment(message):
            print(message["segment"]["transcript"])

        while chunk := next_audio_chunk():
            await client.send_audio(chunk)

    print(client.transcript)

asyncio.run(main())
```

## Who closes the turn

The service needs a boundary to close a segment on. Pick where it comes from:

```python
from speechmatics.agent_stt import TranscriptionConfig, VADConfig, VADMode

# The service's VAD (default). It emits SpeechStarted/SpeechEnded and StartOfTurn/EndOfTurn.
config = TranscriptionConfig(
    vad_mode=VADMode.SERVER,
    vad_config=VADConfig(window=0.2, onset_threshold=0.5, offset_threshold=0.35),
)

# Your endpointing - Pipecat, LiveKit, or your own. The service's VAD stays off.
config = TranscriptionConfig(vad_mode=VADMode.CLIENT)
```

With `VADMode.CLIENT`, close each turn when your side decides speech has ended:

```python
client.finalize()              # from a sync callback
await client.force_end_of_utterance()   # from async code
```

Either sends `ForceEndOfUtterance` stamped with the audio position at the moment of the call, so
the service cuts the turn where you heard the end of speech rather than wherever the send lands.
The flushed segment comes back as a normal `AddSegment`.

What decides that is entirely yours - a VAD, an ML turn model, or a push-to-talk button. The SDK
only cares that something calls `finalize()`.

## Session output

Every server message is dispatched to your handlers and also kept on the client:

```python
client.transcript          # final segments joined by the language's word delimiter
client.segments            # list[Segment] - transcript, timing, speaker, is_final
client.partial_segment     # the segment currently in flight, or None
client.timeline            # list[TimedEvent] - the speech and turn events, in order
client.events              # every raw message, including ones this SDK does not model
client.session_info        # session id and the language pack the service reported

client.transcript_text(speaker_labels=True, include_partial=False)
```

Pass `record_events=False` to `AsyncClient` for long-running sessions where the raw log is not
wanted.

## Messages

Emitted by the service:

| Message | Payload |
| --- | --- |
| `AddSegment` | `segment.transcript`, optional `segment.speaker`, `metadata.start_time`, `metadata.end_time` |
| `AddPartialSegment` | interim preview of the segment being built |
| `SpeechStarted` / `SpeechEnded` | `metadata.start_time` / `metadata.end_time` (service VAD) |
| `StartOfTurn` / `EndOfTurn` | `metadata.start_time` / `metadata.end_time` (service turn detection) |

Passed through from the RT engine: `RecognitionStarted`, `AudioAdded`, `AddTranscript`,
`AddPartialTranscript`, `EndOfTranscript`, `SpeakersResult`, `Info`, `Warning`, `Error`.
`EndOfUtterance` is consumed by the service and not forwarded.

## Configuration

`TranscriptionConfig` is the RT transcription config plus the service-only fields:

| Field | Meaning |
| --- | --- |
| `vad_mode` | `VADMode.SERVER` (default) or `VADMode.CLIENT` |
| `vad_config` | `window`, `onset_threshold`, `offset_threshold` for the service's VAD |
| `emit_sentences` | Close a segment on every sentence boundary, not only at the turn boundary |

`model` takes an Agent STT `Model` and defaults to `DEFAULT_MODEL` (`Model.LINDEN_1`):

```python
from speechmatics.agent_stt import Model, TranscriptionConfig

config = TranscriptionConfig(model=Model.LINDEN_1)
```

The proxy in front of the service resolves the Agent STT model name onto the engine's operating
point, so the transcriber never sees a name it has no notion of. The RT models (`enhanced`,
`standard`) are not Agent STT models and are not accepted here; the deprecated `operating_point`
still passes through, and suppresses the `model` default so the two never arrive together.

Engine silence-based end of utterance is off for this service, and `EndOfUtterance` is not
forwarded, so `conversation_config.end_of_utterance_silence_trigger` does not close segments. A
turn ends either because the service's VAD said so, or because you called `finalize()`.

## Endpoint

The Agent STT endpoint is the RT endpoint plus `/agent`, optionally followed by a service
profile:

```python
AsyncClient(url="wss://eu2.rt.speechmatics.com/v2")           # -> /v2/agent
AsyncClient(url="ws://localhost:8000/v2", profile="default")  # -> /v2/agent/default
AsyncClient(app="pipecat/1.0")                                # reported as sm-app
```

Resolution order: the `url` argument, `SPEECHMATICS_AGENT_STT_URL`, `SPEECHMATICS_RT_URL`, then
the EU endpoint. The `/agent` segment is appended when it is missing.

## Audio

The service requires **16 kHz raw PCM**, `pcm_s16le` or `pcm_f32le`, which is what the client
defaults to. Audio sent before the session is ready, or after it closes, is dropped rather than
raising, so an audio callback does not have to track session state.

## Examples

See [examples/agent_stt](../../examples/agent_stt).
