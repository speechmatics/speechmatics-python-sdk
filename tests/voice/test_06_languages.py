import asyncio
import datetime
import json
import os
from dataclasses import dataclass
from dataclasses import field
from typing import Any
from typing import Optional

import pytest
from _utils import cer
from _utils import get_client
from _utils import normalize
from _utils import send_audio_file

from speechmatics.voice import AdditionalVocabEntry
from speechmatics.voice import AgentServerMessageType
from speechmatics.voice import EndOfUtteranceMode
from speechmatics.voice import VoiceAgentConfig
from speechmatics.voice._helpers import to_serializable

api_key = os.getenv("SPEECHMATICS_API_KEY")


@dataclass
class AudioSample:
    language: str
    path: str
    transcript: str
    use_cer: bool = False
    vocab: list[str] = field(default_factory=list)


SAMPLES: list[AudioSample] = [
    AudioSample(
        language="fr",
        path="./assets/languages/fr_fr_000378.wav",
        transcript=(
            "la partie extérieure que nous voyons lorsque nous regardons le soleil "
            "s’appelle la photosphère ce qui signifie « boule de lumière »"
        ),
    ),
    AudioSample(
        language="de",
        path="./assets/languages/de_de_000675.wav",
        transcript=(
            "Die Einreise in das südliche Afrika mit dem Auto ist eine erstaunliche Möglichkeit, "
            "die ganze Schönheit der Region zu sehen und an Orte abseits der normalen Touristenrouten zu gelangen."
        ),
    ),
    AudioSample(
        language="he",
        path="./assets/languages/he_il_000432.wav",
        transcript="טורקיה מוקפת ים משלושה כיוונים: הים האגאי ממערב, הים השחור מצפון והים התיכון מדרום.",
    ),
    AudioSample(
        language="cmn",
        path="./assets/languages/cmn_hans_cn_000328.wav",
        transcript="博贝克出生于克罗地亚首都萨格勒布，在为贝尔格莱德游击队足球俱乐部效力时成名",
        use_cer=True,
    ),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("sample", SAMPLES, ids=lambda s: f"{s.language}:{s.path}")
async def test_transcribe_languages(sample: AudioSample):
    """Test foreign language transcription.

    This test will:
        - use samples from the FLEURS dataset
        - use different languages
        - compare the normalized transcriptions with the reference transcription
    """

    # API key
    api_key = os.getenv("SPEECHMATICS_API_KEY")
    if not api_key:
        pytest.skip("Valid API key required for test")

    # Client
    client = await get_client(
        api_key=api_key,
        connect=False,
        config=VoiceAgentConfig(
            max_delay=1.2,
            end_of_utterance_mode=EndOfUtteranceMode.EXTERNAL,
            language=sample.language,
            additional_vocab=[AdditionalVocabEntry(content=vocab) for vocab in sample.vocab],
        ),
    )

    # Create an event to track when the callback is called
    messages: list[str] = []
    bytes_sent: int = 0
    last_message: Optional[dict[str, Any]] = None

    # Start time
    start_time = datetime.datetime.now()

    # Bytes logger
    def log_bytes_sent(bytes):
        nonlocal bytes_sent
        bytes_sent += bytes

    # Callback for each message
    def log_message(message):
        nonlocal last_message
        last_message = message
        ts = (datetime.datetime.now() - start_time).total_seconds()
        audio_ts = bytes_sent / 16000 / 2
        log = json.dumps({"ts": ts, "audio_ts": audio_ts, "payload": to_serializable(message)})
        messages.append(log)

    # Add listeners
    client.once(AgentServerMessageType.RECOGNITION_STARTED, log_message)
    client.on(AgentServerMessageType.ADD_SEGMENT, log_message)

    # Load the audio file
    audio_file = sample.path

    # Connect
    await client.connect()

    # Check we are connected
    assert client._is_connected

    # Individual payloads
    await send_audio_file(client, audio_file, progress_callback=log_bytes_sent)

    # Send finalize after a short delay
    await asyncio.sleep(2.0)
    client.finalize()

    # Wait for 5 seconds
    await asyncio.sleep(1.5)

    # Extract the last message
    assert last_message.get("message") == AgentServerMessageType.ADD_SEGMENT

    # Check the segment
    segments = last_message.get("segments", [])
    assert len(segments) == 1
    seg0 = segments[0]

    # Check language
    assert seg0.get("language") == sample.language

    # Get normalized versions of the transcription and reference
    str_original = normalize(sample.transcript)
    str_transcribed = normalize(seg0.get("text", "UNKNOWN"))
    str_cer = cer(str_original, str_transcribed)

    # Assert the CER
    if sample.use_cer:
        ok = str_cer < 0.05  # < 5% CER acceptable
    else:
        ok = str_original == str_transcribed  # Exact match required

    # Compare transcriptions
    if not ok:
        print("\n".join(messages))
        print(f"Original: [{str_original}]")
        print(f"Transcribed: [{str_transcribed}]")
        print(f"CER: {str_cer}")
        raise AssertionError("Transcription does not match original")

    # Close session
    await client.disconnect()
    assert not client._is_connected
