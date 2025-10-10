# Realtime speaker identification

Speechmatics STT engine is able to provide labels and identifiers for speakers in a session which can be used in subsequent sessions to train the engine on known speakers. Speaker identifiers are encrypted and specific to your Speechmatics API key and are not transferable to other API keys. Multiple identifiers can be used to train the engine on multiple speakers.

For more information on speaker ID, see the [Speechmatics documentation](https://docs.speechmatics.com//speech-to-text/realtime/realtime-speaker-identification).

### Enrolling one or more speakers

Speaker enrolment can be requested at any point during a conversation. It is recommended that individual speakers have spoken at least 20 words so that the engine can settle and identify them using characteristics from their voice. The example `enrol.py` requests the speaker identifiers to be emitted at the end of the session.

To request the speaker identifiers during a session, you call the `send_message` function. This will then return a `SPEAKERS_RESULT` event.

```python
# listen for speakers result
client.on(AgentServerMessageType.SPEAKERS_RESULT, handler)

# request speaker ID information at the end of the session
await client.send_message({"message": AgentClientMessageType.GET_SPEAKERS, "final": True})

# request speaker ID information up to this point
await client.send_message({"message": AgentClientMessageType.GET_SPEAKERS, "final": False})
```

### Using known speakers

Speaker identifiers can be used in subsequent sessions to train the engine on known speakers.

```python
# create a set of known speakers
known_speakers: list[DiarizationKnownSpeaker] = [
    DiarizationKnownSpeaker(
        label="John",
        speaker_identifiers=["XX...XX"]
    ),
    DiarizationKnownSpeaker(
        label="Jane",
        speaker_identifiers=["YY...YY"]
    )
]

# create a config with known speakers
VoiceAgentConfig(
    known_speakers=known_speakers,
)
```

## Requirements

You will need to have a Speechmatics API key, available from our [portal](https://portal.speechmatics.com/). Use the API key either as an environment variable (`SPEECHMATICS_API_KEY`) or as command line parameter (`--api-key`).

Install the dependencies for the examples, as shown in [example README](../README.md).

## Enrolling example

To enrol a speaker, run the following example with the `--enrol` argument.

```shell
# run the example with API key
python ./examples/voice/speaker_id/main.py \
  --api-key <SPEECHMATICS_API_KEY> \
  --enrol
```

Once you have finished speaking, **press any key** and this will show the speaker information in the console.

```json
[{ "label": "S1", "speaker_identifiers": ["XX...XX"] }]
```

## Known speaker example

To use one or more known speakers, use the following example with the `--speakers` argument. It is recommended to NOT use the labels `S1`, `S2`, etc. as these are reserved for the engine to use.

The SDK is also configured that any transcription from a speaker with the label that is in the format `__XXX__` will be ignored.

```shell
# run the example with API key
python ./examples/voice/speaker_id/main.py \
  --api-key <SPEECHMATICS_API_KEY> \
  --speakers <JSON_PAYLOAD>
```

Where `<JSON_PAYLOAD>` is a JSON payload string of the form:

```json
[
  { "label": "John", "speaker_identifiers": ["XX...XX"] },
  { "label": "Jane", "speaker_identifiers": ["YY...YY"] }
]
```

When you speak, you will now see the enrolled speaker information in the console.

```
2025-10-10 12:00:00.000 FINAL 💬 Partial: ['@John: Hello!']
```
