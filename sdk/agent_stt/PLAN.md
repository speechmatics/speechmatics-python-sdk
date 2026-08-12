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

1. URL resolution (`/agent` + profile, `SPEECHMATICS_AGENT_STT_URL` env override).
2. `TranscriptionConfig` with `vad_mode`, `vad_config`, `emit_sentences`, and `model` left
   **unset** by default - the service's default profile pins `operating_point: enhanced` and
   locks it, so sending `model` too would put both keys in the merged `StartRecognition`.
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

The StartRecognition the service forwarded downstream confirmed the two design points that
mattered: `vad_config` and `emit_sentences` are stripped, and because the SDK leaves `model`
unset the message carries only the profile's locked `operating_point` - no conflicting pair.

## Milestone 2 - Pipecat (not in this change)

`pipecat/src/pipecat/services/speechmatics/stt.py` (~1266 lines) currently drives
`speechmatics.voice.VoiceAgentClient` and its in-process VAD/smart-turn. Nothing in Pipecat is
touched by this change. The migration:

- swap the import block to `speechmatics.agent_stt`
- `TurnDetectionMode.EXTERNAL` -> `VADMode.CLIENT` + `force_end_of_utterance()` on
  `VADUserStoppedSpeakingFrame`; `ADAPTIVE`/`SMART_TURN` -> `VADMode.SERVER` and let
  `StartOfTurn`/`EndOfTurn` drive `ProposedUserStartedSpeakingFrame`/`ProposedUserStoppedSpeakingFrame`
- `AddPartialSegment` -> `InterimTranscriptionFrame`, `AddSegment` -> `TranscriptionFrame`
- drop the `pipecat-ai[speechmatics]` onnxruntime/transformers extras that only existed for the
  bundled VAD and smart-turn models
- keep `SpeechmaticsSTTSettings` as the public surface so user code doesn't change

Open questions to settle before starting milestone 2:

- ~~speaker-focus / known-speaker features in the Pipecat service have no service-side
  equivalent yet~~ - dropped for now, to be added in a later service release. `known_speakers`
  still works, since `speaker_diarization_config.speakers` passes straight through.
- non-forced `EndOfUtterance` no longer flushes a segment (the default profile sets
  `end_of_utterance_silence_trigger: 0.0`), so engine-silence endpointing is not available -
  confirm that is intended for the `FIXED` mode Pipecat exposes. If it is, `FIXED` has to map
  onto `VADMode.SERVER` (or be removed for this service) rather than onto engine silence.
