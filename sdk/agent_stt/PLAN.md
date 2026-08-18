# Agent STT SDK - plan

## What this is

`speechmatics-agent-stt` is a thin extension of `speechmatics-rt` that talks to the
**Voice Agent Service** (`voice-agent-service`) instead of the raw RT engine. The service sits
between the RT SaaS proxy and the transcriber and turns word-level RT output into
**segments**, plus VAD/turn signals.

The SDK does **no VAD and no turn detection of its own**. Boundaries come from one of two places:

| Mode | Who decides the turn boundary | Wire behaviour |
| --- | --- | --- |
| `VADMode.SERVER` | the service's own (Silero) VAD | `transcription_config.vad_config.enabled = true`; service emits `SpeechStarted`/`SpeechEnded`/`StartOfTurn`/`EndOfTurn` and forces end-of-utterance internally |
| `VADMode.CLIENT` | the host framework (Pipecat, LiveKit, ...) | `transcription_config.vad_config.enabled = false`; the host calls `client.force_end_of_utterance()` on its own VAD's stop-speaking event |

This is the whole reason the SDK exists as a separate package: the `voice` SDK bundles VAD +
smart-turn models in-process, which duplicates what Pipecat/LiveKit already run and what the
service now does server-side.

## Protocol delta vs the RT SDK

Endpoint: RT URL + `/agent`, optionally + `/{profile}`
(`wss://eu2.rt.speechmatics.com/v2/agent`, service route is `/v2/agent/{profile:path}`).

Client -> server: unchanged (`StartRecognition`, binary audio, `EndOfStream`,
`ForceEndOfUtterance`). No new client messages.

`StartRecognition.transcription_config` gains two service-only fields, stripped by the service
before it forwards to the RT engine (`_profiles/_rt_conversion.NON_RT_API_FIELDS`):

- `vad_config`: `{enabled, window, onset_threshold, offset_threshold}`
- `emit_sentences`: `bool` - close a segment on sentence boundaries mid-turn

Server -> client, new messages (`voice_agent_api/_service_messages.py`):

- `AddSegment` - `{segment: {transcript, speaker?}, metadata: {start_time, end_time}}`
- `AddPartialSegment` - same shape, interim
- `SpeechStarted` / `SpeechEnded` - `{metadata: {start_time|end_time}}` (VAD)
- `StartOfTurn` / `EndOfTurn` - `{metadata: {start_time|end_time}}` (turn detection)
- `Warning` - RT shape, also emitted by the service for profile/lock adjustments

Server -> client, RT passthrough: `RecognitionStarted`, `AudioAdded`, `AddTranscript`,
`AddPartialTranscript`, `EndOfTranscript`, `Info`, `Warning`, `Error`, audio events.
`EndOfUtterance` is consumed by the service and never reaches the client.

Note: the service still forwards `AddTranscript`/`AddPartialTranscript` verbatim today. The SDK
accumulates its transcript from **segments only**, but the transcript messages remain available
via handlers and the event log, so nothing is lost if a future profile mutes them.

Constraints the service imposes: `audio_format.type` must be `raw`, sample rate `16000`
(Silero), encoding `pcm_s16le` or `pcm_f32le` (no mulaw). The SDK defaults to exactly that.

## Milestone 1 - the SDK (done)

```
sdk/agent_stt/
  pyproject.toml            speechmatics-agent-stt, depends on speechmatics-rt
  README.md
  PLAN.md                   this file
  speechmatics/agent_stt/
    __init__.py             public API
    _client.py              AsyncClient (subclasses rt.AsyncClient)
    _models.py              message enums, TranscriptionConfig, VADConfig, Segment, TimedEvent
    _transcript.py          Transcript - final segments, live partial, timeline, raw event log
    _transport.py           AgentTransport - stamps sm-sdk=python-agent-stt-sdk-vX
    _url.py                 URL/profile resolution
tests/agent_stt/            offline unit tests (no API key needed)
examples/agent_stt/         server-VAD and client-VAD (BYO) examples
```

Everything inherited from `rt.AsyncClient` stays: auth (`StaticKeyAuth`/`JWTAuth`), transport,
reconnect-free lifecycle, `send_audio`, `transcribe`, `stop_session`,
`force_end_of_utterance`, the `EventEmitter` decorator API.

What the subclass adds:

1. URL resolution (`/agent` + profile, on top of the `SPEECHMATICS_RT_URL` endpoint).
2. `TranscriptionConfig` with `vad_mode`, `vad_config`, `emit_sentences`, and an Agent STT
   `Model` enum defaulting to `linden-1`. The request goes to the proxy rather than the service
   websocket directly, and the proxy resolves the Agent STT model name onto the engine's
   operating point, so the transcriber never sees a name it has no notion of. The deprecated
   `operating_point` suppresses the `model` default, so the merged `StartRecognition` never
   carries both keys. `linden-2` lands as one more enum member.
3. Segment-level transcript accumulation, so `client.transcript` reads like the RT flow does.
4. A raw event log (`client.events`) capturing every server message, including ones this SDK
   version doesn't model yet - that is the "accept and save the other messages" requirement.
5. 16 kHz raw PCM defaults.

Plumbing carried over from the `voice` SDK (rewritten, not imported, since that SDK goes away):

- `connect()` / `disconnect()` and a context manager that connects on entry, the shape Pipecat
  already calls
- an audio gate: frames before RecognitionStarted or after close are dropped, not raised on, and
  a transport error closes the gate instead of propagating into an audio callback
- `finalize()` callable from a sync handler, stamping ForceEndOfUtterance with the audio position
  **at the moment of the call** rather than when the send lands
- `app` reported as `sm-app` on the URL, alongside the SDK's own `sm-sdk` identifier
- the language pack's `word_delimiter` from RecognitionStarted driving how text is joined

Not carried over: VAD, smart turn, the audio ring buffer, metrics/diagnostics messages,
speaker focus, fragment-level segment assembly (the service does that now).

### Verified end to end

Run against the real `voice-agent-service` with a stub RT transcriber behind it, in client-VAD
mode: `/v2/agent/default` routing, three `ForceEndOfUtterance` turns each flushing one
`AddSegment`, speaker labels, the event log, and `client.transcript` coming out as
`"Hello there. How are you today? Goodbye."`.

The StartRecognition the service forwarded downstream confirmed that `vad_config` and
`emit_sentences` are stripped before it reaches the RT engine.

That run predates the `linden-1` default, so it sent no `model` at all and the message carried
only the profile's locked `operating_point`. Model resolution happens in the proxy ahead of the
service, which this stub setup does not exercise, so it still needs verifying against the real
proxy.

## Milestone 2 - Pipecat (not in this change)

`pipecat/src/pipecat/services/speechmatics/stt.py` (~1266 lines) currently drives
`speechmatics.voice.VoiceAgentClient` and its in-process VAD/smart-turn. Nothing in Pipecat is
touched by this change. The migration:

- swap the import block to `speechmatics.agent_stt`
- collapse `TurnDetectionMode` onto the two modes that exist:
  - `EXTERNAL` -> `VADMode.CLIENT`, with `finalize()` on `VADUserStoppedSpeakingFrame`
  - `ADAPTIVE` -> `VADMode.SERVER`, with `StartOfTurn`/`EndOfTurn` driving
    `ProposedUserStartedSpeakingFrame`/`ProposedUserStoppedSpeakingFrame`
  - `FIXED` and `SMART_TURN` -> removed (see below)
- `AddPartialSegment` -> `InterimTranscriptionFrame`, `AddSegment` -> `TranscriptionFrame`
- drop the `pipecat-ai[speechmatics]` onnxruntime/transformers extras that only existed for the
  bundled VAD and smart-turn models
- drop `end_of_utterance_silence_trigger` and `end_of_utterance_max_delay` from
  `SpeechmaticsSTTSettings` and `InputParams`, along with the passthrough at
  `stt.py:788` and `stt.py:1252` - engine silence-based end of utterance is off for this
  service, so both are no-ops
- `_enable_vad` (`stt.py:530`) becomes `vad_mode is VADMode.CLIENT`, since that is now the only
  mode where Pipecat's own VAD drives the boundary
- otherwise keep `SpeechmaticsSTTSettings` as the public surface so user code doesn't change

### `FIXED` and `SMART_TURN` are removed

`end_of_utterance_silence_trigger` is off for this service: the default profile pins it to `0.0`,
the service consumes `EndOfUtterance` rather than forwarding it, and a non-forced end of utterance
does not close a segment. So there is nothing for `TurnDetectionMode.FIXED` to mean here and it
goes away rather than being aliased to another mode.

`SMART_TURN` goes for the same reason: the service has no smart-turn endpoint yet (planned for a
later release), and this SDK loads no models, so the mode cannot be honoured as specified. It
comes back when the service does, as a `VADMode.SERVER` variant.

Removing it costs Pipecat users nothing, because Pipecat's own turn analyzer still works: any
host-side endpointing - VAD, ML turn model, push-to-talk - reaches the service the same way,
through `finalize()`. `VADMode.CLIENT` is agnostic about what produced the signal.

Turns therefore end in exactly two ways, which is what `VADMode` models: the service's VAD, or
the client calling `finalize()`.

Open questions to settle before starting milestone 2:

- ~~speaker-focus / known-speaker features in the Pipecat service have no service-side
  equivalent yet~~ - dropped for now, to be added in a later service release. `known_speakers`
  still works, since `speaker_diarization_config.speakers` passes straight through.
- ~~engine-silence endpointing / `FIXED` mode~~ - removed, see above.
- ~~`SMART_TURN`~~ - removed until the service implements it. Host-side turn models keep working
  through `VADMode.CLIENT`.

Both removals are user-visible, so they need a changelog entry when the Pipecat change lands.
