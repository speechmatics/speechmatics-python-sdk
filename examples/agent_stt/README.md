# Agent STT examples

Set `SPEECHMATICS_API_KEY` first. To point at a local Voice Agent Service, set
`SPEECHMATICS_AGENT_STT_URL` (for example `ws://localhost:8000/v2/agent`).

The service needs 16 kHz raw PCM, so the file examples take a 16 kHz WAV and default to
`tests/voice/assets/audio_01_16kHz.wav`.

| Example | What it shows |
| --- | --- |
| [file/main.py](file/main.py) | File transcription with the service's VAD; segments, turn events, transcript at the end |
| [realtime_file/main.py](realtime_file/main.py) | The same file paced at wall-clock speed, with the lag of each message behind the audio |
| [client_vad/main.py](client_vad/main.py) | The client owns turn boundaries and calls `finalize()`, as Pipecat and LiveKit do |
| [microphone/main.py](microphone/main.py) | Live microphone with diarization and speaker-labelled transcript (needs `pyaudio`) |
| [microphone_windows/main.py](microphone_windows/main.py) | The same, set up for Windows: device selection, in-place partials, Ctrl+C shutdown |

```bash
python examples/agent_stt/file/main.py
python examples/agent_stt/realtime_file/main.py
python examples/agent_stt/client_vad/main.py
python examples/agent_stt/microphone/main.py
py examples\agent_stt\microphone_windows\main.py
```
