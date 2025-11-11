# Simple Microphone Transcription

Basic real-time transcription using the default microphone with speaker diarization.

## Quick Start

```bash
export SPEECHMATICS_API_KEY=your_api_key
python simple.py
```

Press `CTRL+C` to stop.

## Features

- Uses default microphone
- Real-time transcription with speaker diarization
- Shows partial and final results
- Detects end of turn
- Uses "scribe" preset

## Requirements

- Speechmatics API key from the [portal](https://portal.speechmatics.com/)
- PyAudio: `pip install pyaudio`
- See [examples README](../README.md) for SDK dependencies

## Code Example

```python
from speechmatics.rt import Microphone
from speechmatics.voice import VoiceAgentClient, AgentServerMessageType

# Create client with preset
client = VoiceAgentClient(api_key="YOUR_KEY", preset="scribe")

# Register event handlers
@client.on(AgentServerMessageType.ADD_SEGMENT)
def on_segment(message):
    segments = message.get("segments", [])
    for segment in segments:
        print(f"{segment['speaker_id']}: {segment['text']}")

# Connect and stream
await client.connect()
mic = Microphone(sample_rate=16000, chunk_size=320)
mic.start()

while True:
    audio_chunk = await mic.read(320)
    await client.send_audio(audio_chunk)
```

## Output Example

```
Microphone ready - speak now... (Press CTRL+C to stop)

[PARTIAL] S1: Hello
[PARTIAL] S1: Hello how
[PARTIAL] S1: Hello how are
[FINAL] S1: Hello, how are you?
[END OF TURN]
[PARTIAL] S2: I'm
[PARTIAL] S2: I'm good
[FINAL] S2: I'm good, thanks!
[END OF TURN]
```
