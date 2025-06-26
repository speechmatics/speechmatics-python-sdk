from typing import Any
from typing import Optional

from .._models import AudioEventsConfig
from .._models import AudioFormat
from .._models import ClientMessageType
from .._models import TranscriptionConfig
from .._models import TranslationConfig


def build_start_recognition_message(
    transcription_config: TranscriptionConfig,
    audio_format: AudioFormat,
    translation_config: Optional[TranslationConfig] = None,
    audio_events_config: Optional[AudioEventsConfig] = None,
) -> dict[str, Any]:
    """Build the start recognition message for the server.

    Args:
        transcription_config: The transcription configuration.
        audio_format: The audio format.
        translation_config: The translation configuration.
        audio_events_config: The audio events configuration.

    Returns:
        The start recognition message.
    """

    start_recognition_message = {
        "message": ClientMessageType.START_RECOGNITION,
        "audio_format": audio_format.to_dict(),
        "transcription_config": transcription_config.to_dict(),
    }

    if translation_config:
        start_recognition_message["translation_config"] = translation_config.to_dict()

    if audio_events_config:
        start_recognition_message["audio_events_config"] = audio_events_config.to_dict()

    return start_recognition_message
