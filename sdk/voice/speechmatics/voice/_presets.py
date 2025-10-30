#
# Copyright (c) 2025, Speechmatics / Cantab Research Ltd
#

from __future__ import annotations

from ._models import EndOfUtteranceMode
from ._models import SpeechSegmentConfig
from ._models import SpeechSegmentEmitMode
from ._models import VoiceAgentConfig


class VoiceAgentConfigPreset:
    """Set of preset configurations for the Voice Agent SDK."""

    @staticmethod
    def LOW_LATENCY(overlay: VoiceAgentConfig | None = None) -> VoiceAgentConfig:  # noqa: N802
        """Best suited for low latency situations.

        This configuration will emit the end of turn as soon as possible, with minimal
        delay to finalizing the spoken sentences. It is not recommended for
        conversation, as it will not account for pauses, slow speech or disfluencies.
        """
        return VoiceAgentConfigPreset._merge_configs(
            VoiceAgentConfig(
                enable_diarization=True,
                max_delay=0.7,
                end_of_utterance_silence_trigger=0.2,
                end_of_utterance_mode=EndOfUtteranceMode.FIXED,
                speech_segment_config=SpeechSegmentConfig(emit_mode=SpeechSegmentEmitMode.ON_FINALIZED_SENTENCE),
            ),
            overlay,
        )

    @staticmethod
    def CONVERSATION_ADAPTIVE(overlay: VoiceAgentConfig | None = None) -> VoiceAgentConfig:  # noqa: N802
        """Best suited for general conversational use cases.

        For conversation, there is a balance between accuracy, speed and the rate at
        which the end of turn is emitted. Tne use of ADAPTIVE means that the delay to
        finalizing the spoken sentences will be adjusted based on the words and whether
        there are any pauses, slow speech or disfluencies.
        """
        return VoiceAgentConfigPreset._merge_configs(
            VoiceAgentConfig(
                enable_diarization=True,
                max_delay=0.7,
                end_of_utterance_silence_trigger=0.5,
                end_of_utterance_mode=EndOfUtteranceMode.ADAPTIVE,
            ),
            overlay,
        )

    @staticmethod
    def CONVERSATION_SMART_TURN(overlay: VoiceAgentConfig | None = None) -> VoiceAgentConfig:  # noqa: N802
        """Best suited for complex conversational use cases.

        For conversation, there is a balance between accuracy, speed and the rate at
        which the end of turn is emitted. Tne use of SMART_TURN means that the delay to
        finalizing the spoken sentences will be adjusted based on the words and whether
        there are any pauses, slow speech or disfluencies.

        This preset will use a model to detect for acoustic indicators from the
        speaker to determine when a turn has ended.

        Use of this will requite `pip install speechmatics-voice[smart]` and may not
        be suited to low-power devices.
        """
        return VoiceAgentConfigPreset._merge_configs(
            VoiceAgentConfig(
                enable_diarization=True,
                max_delay=0.85,
                end_of_utterance_silence_trigger=0.5,
                end_of_utterance_mode=EndOfUtteranceMode.SMART_TURN,
            ),
            overlay,
        )

    @staticmethod
    def _merge_configs(base: VoiceAgentConfig, overlay: VoiceAgentConfig | None) -> VoiceAgentConfig:
        """Merge two VoiceAgentConfig objects.

        Simply merge any overrides from the overlay into the base config. This makes creating
        custom configs from presets easier.

        Args:
            base: Base config to merge into.
            overlay: Overlay config to merge from.

        Returns:
            Merged config.

        """

        # No overlay required
        if overlay is None:
            return base

        # Merge overlay into base - use model_validate to properly reconstruct nested models
        merged_dict = {**base.model_dump(), **overlay.model_dump(exclude_unset=True)}
        return VoiceAgentConfig.model_validate(merged_dict)  # type: ignore[no-any-return]
