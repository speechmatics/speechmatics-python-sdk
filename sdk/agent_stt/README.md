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
from speechmatics.agent_stt import AgentSttAsyncClient, ServerMessageType, TranscriptionConfig

async def main():
    # Uses SPEECHMATICS_API_KEY from the environment
    client = AgentSttAsyncClient(config=TranscriptionConfig(language="en", enable_partials=True))

    # Register handlers before opening the session, so no message can arrive unhandled
    @client.on(ServerMessageType.ADD_SEGMENT)
    def handle_segment(message):
        print(message["segment"]["transcript"])

    async with client:
        while chunk := next_audio_chunk():
            await client.send_audio(chunk)

    print(client.transcript)

asyncio.run(main())
```

## Who closes the turn

The service needs a boundary to close a segment on. Pick where it comes from:

```python
from speechmatics.agent_stt import TurnConfig, TurnDetectionMode

# The service's VAD (default). It emits SpeechStarted/SpeechEnded and StartOfTurn/EndOfTurn.
turn_config = TurnConfig(turn_detection_mode=TurnDetectionMode.VAD)

# Your endpointing - Pipecat, LiveKit, or your own. The service's VAD stays off.
turn_config = TurnConfig(turn_detection_mode=TurnDetectionMode.EXTERNAL)

client = AgentSttAsyncClient(config=TranscriptionConfig(language="en"), turn_config=turn_config)
```

With `TurnDetectionMode.EXTERNAL`, close each turn when your side decides speech has ended:

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

Pass `record_events=False` to `AgentSttAsyncClient` for long-running sessions where the raw log is not
wanted.

## Messages

Emitted by the service:

| Message | Payload |
| --- | --- |
| `AddSegment` | `segment.transcript`, optional `segment.speaker`, `metadata.start_time`, `metadata.end_time` |
| `AddPartialSegment` | interim preview of the segment being built |
| `SpeechStarted` / `SpeechEnded` | `metadata.start_time` / `metadata.end_time` (service VAD) |
| `StartOfTurn` / `EndOfTurn` | `metadata.start_time` / `metadata.end_time` (service turn detection) |

Passed through from the RT engine: `RecognitionStarted`, `AudioAdded`, `EndOfTranscript`,
`SpeakersResult`, `Info`, `Warning`, `Error`.

Anything else the engine sends - the word-level `AddTranscript`/`AddPartialTranscript`, audio
events - is not modelled here, but still reaches `client.events` and any handler registered
under its name.

## Configuration

`TranscriptionConfig` is the RT transcription config with the service's own model names.
Turn taking is configured separately, and is fixed for the life of the session:

| Config | Field | Meaning |
| --- | --- | --- |
| `TurnConfig` | `turn_detection_mode` | `TurnDetectionMode.VAD` (default) or `TurnDetectionMode.EXTERNAL` |

`model` takes an Agent STT `Model` and defaults to `DEFAULT_MODEL` (`Model.LINDEN_1`):

```python
from speechmatics.agent_stt import Model, TranscriptionConfig

config = TranscriptionConfig(model=Model.LINDEN_1)
```

The proxy in front of the service resolves the Agent STT model name onto the engine's operating
point, so the transcriber never sees a name it has no notion of. The RT models (`enhanced`,
`standard`) are not Agent STT models and are not accepted here; the deprecated `operating_point`
still passes through, and suppresses the `model` default so the two never arrive together.

Engine silence-based end of utterance is not offered here. A turn ends either because the
service's VAD said so, or because you called `finalize()`.

## Endpoint

The Agent STT endpoint is the RT endpoint plus `/agent`:

```python
AgentSttAsyncClient(url="wss://eu2.rt.speechmatics.com/v2")  # -> /v2/agent
AgentSttAsyncClient(url="ws://localhost:8000/v2")            # -> /v2/agent
AgentSttAsyncClient(app="pipecat/1.0")                       # reported as sm-app
```

Resolution order: the `url` argument, `SPEECHMATICS_RT_URL`, then the EU endpoint. The `/agent`
segment is appended when it is missing.

## Audio

The service requires **16 kHz raw PCM**, `pcm_s16le` or `pcm_f32le`, which is what the client
defaults to. Audio sent before the session is ready, or after it closes, is dropped rather than
raising, so an audio callback does not have to track session state.

## Examples

See [examples/agent_stt](../../examples/agent_stt).
