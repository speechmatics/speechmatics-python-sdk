import asyncio
import datetime
import json
import os
from dataclasses import dataclass
from dataclasses import field
from typing import Any
from typing import Optional

import pytest
from _utils import get_client
from _utils import send_audio_file

from speechmatics.voice import AdditionalVocabEntry
from speechmatics.voice import AgentServerMessageType
from speechmatics.voice import EndOfUtteranceMode
from speechmatics.voice import VoiceAgentConfig
from speechmatics.voice._utils import TextUtils

# Skip for CI testing
pytestmark = pytest.mark.skipif(os.getenv("CI") == "true", reason="Skipping language tests in CI")

# Constants
API_KEY = os.getenv("SPEECHMATICS_API_KEY")
URL: Optional[str] = "wss://eu2.rt.speechmatics.com/v2"


@dataclass
class AudioSample:
    language: str
    path: str
    transcript: str
    sentence_break: str = " "
    use_cer: bool = False
    cer_pass: float = 0.05
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
        language="es",
        path="./assets/languages/es_419_000896.wav",
        transcript=(
            "Es esencial que cuente, cuando menos, con calzado con suelas apropiadas. "
            "Los zapatos de verano por lo general resbalan mucho en el hielo y la nieve, "
            "incluso hay botas de invierno que no son adecuadas."
        ),
    ),
    AudioSample(
        language="he",
        path="./assets/languages/he_il_000432.wav",
        transcript="טורקיה מוקפת ים משלושה כיוונים: הים האגאי ממערב, הים השחור מצפון והים התיכון מדרום.",
        sentence_break="",
    ),
    AudioSample(
        language="cmn",
        path="./assets/languages/cmn_hans_cn_000328.wav",
        transcript="博贝克出生于克罗地亚首都萨格勒布，在为贝尔格莱德游击队足球俱乐部效力时成名。",
        sentence_break="",
        use_cer=True,
    ),
    AudioSample(
        language="ja",
        path="./assets/languages/ja_jp_000595.wav",
        transcript="動物は地球上のいたるところに生息しています。地面を掘ったり、海を泳ぎ回ったり、空を飛んだりしています。",
        sentence_break="",
        use_cer=True,
        cer_pass=0.07,
    ),
    AudioSample(
        language="th",
        path="./assets/languages/th_th_000208.wav",
        transcript="ข้สภาพอากาศเลวร้ายที่เป็นสาเหตุของการยกเลิกการลงจอดทำให้การค้นหายากลำบาก",
        sentence_break="",
        use_cer=True,
        cer_pass=0.03,
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
    if not API_KEY:
        pytest.skip("Valid API key required for test")

    # Client
    client = await get_client(
        api_key=API_KEY,
        url=URL,
        connect=False,
        config=VoiceAgentConfig(
            max_delay=1.2,
            end_of_utterance_mode=EndOfUtteranceMode.EXTERNAL,
            language=sample.language,
            additional_vocab=[AdditionalVocabEntry(content=vocab) for vocab in sample.vocab],
        ),
    )
    assert client is not None

    # Create an event to track when the callback is called
    messages: list[str] = []
    bytes_sent: int = 0
    last_message: Optional[dict[str, Any]] = None

    # Segments
    segments: list[dict[str, Any]] = []

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
        log = json.dumps({"ts": round(ts, 3), "audio_ts": round(audio_ts, 2), "payload": message})
        messages.append(log)

    # Log a segment
    def log_segment(message):
        segments.extend(message["segments"])

    # Add listeners
    client.once(AgentServerMessageType.RECOGNITION_STARTED, log_message)
    client.on(AgentServerMessageType.ADD_SEGMENT, log_message)
    client.on(AgentServerMessageType.ADD_SEGMENT, log_segment)

    # Load the audio file
    audio_file = sample.path

    # Connect
    await client.connect()

    # Check we are connected
    assert client._is_connected

    # Individual payloads
    await send_audio_file(client, audio_file, progress_callback=log_bytes_sent)

    # Send finalize
    await asyncio.sleep(1.5)
    client.finalize()
    await asyncio.sleep(1.5)

    # Extract the last message
    assert last_message.get("message") == AgentServerMessageType.ADD_SEGMENT

    # Check the segment
    assert len(segments) >= 1
    seg0 = segments[0]

    # Check language
    assert seg0.get("language") == sample.language

    # Concatenate text from segments
    transcribed = sample.sentence_break.join([seg["text"] for seg in segments])

    # Get normalized versions of the transcription and reference
    str_original = TextUtils.normalize(sample.transcript)
    str_transcribed = TextUtils.normalize(transcribed)
    str_cer = TextUtils.cer(str_original, str_transcribed)

    # Assert the CER
    if sample.use_cer:
        ok = str_cer < sample.cer_pass  # < 5% CER acceptable (default)
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
