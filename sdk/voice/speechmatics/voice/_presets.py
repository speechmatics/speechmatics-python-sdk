#
# Copyright (c) 2025, Speechmatics / Cantab Research Ltd
#

from __future__ import annotations

from typing import Optional

from ._models import EndOfTurnConfig
from ._models import EndOfUtteranceMode
from ._models import OperatingPoint
from ._models import SmartTurnConfig
from ._models import SpeechSegmentConfig
from ._models import VoiceActivityConfig
from ._models import VoiceAgentConfig


class VoiceAgentConfigPreset:
    """Set of preset configurations for the Voice Agent SDK."""

    @staticmethod
    def FAST(overlay: Optional[VoiceAgentConfig] = None) -> VoiceAgentConfig:  # noqa: N802
        """Best suited for low latency situations.

        This configuration will emit the end of turn as soon as possible, with minimal
        delay to finalizing the spoken sentences. It is not recommended for
        conversation, as it will not account for pauses, slow speech or disfluencies.

        Note that this uses our standard operating point so will have marginally lower
        accuracy that the enhanced operating point.
        """
        return VoiceAgentConfigPreset._merge_configs(
            VoiceAgentConfig(
                operating_point=OperatingPoint.STANDARD,
                enable_diarization=True,
                max_delay=2.0,
                end_of_utterance_silence_trigger=0.25,
                end_of_utterance_mode=EndOfUtteranceMode.FIXED,
                speech_segment_config=SpeechSegmentConfig(emit_sentences=False),
            ),
            overlay,
        )

    @staticmethod
    def FIXED(overlay: Optional[VoiceAgentConfig] = None) -> VoiceAgentConfig:  # noqa: N802
        """Best suited for general conversational use cases with fixed end-of-utterance timing.

        For conversation, there is a balance between accuracy, speed and the rate at
        which the end of turn is emitted. This configuration uses fixed timing for
        end-of-utterance detection.
        """
        return VoiceAgentConfigPreset._merge_configs(
            VoiceAgentConfig(
                operating_point=OperatingPoint.ENHANCED,
                enable_diarization=True,
                max_delay=2.0,
                end_of_utterance_silence_trigger=0.5,
                end_of_utterance_mode=EndOfUtteranceMode.FIXED,
                speech_segment_config=SpeechSegmentConfig(emit_sentences=False),
            ),
            overlay,
        )

    @staticmethod
    def ADAPTIVE(overlay: Optional[VoiceAgentConfig] = None) -> VoiceAgentConfig:  # noqa: N802
        """Best suited for general conversational use cases.

        For conversation, there is a balance between accuracy, speed and the rate at
        which the end of turn is emitted. The use of ADAPTIVE means that the delay to
        finalizing the spoken sentences will be adjusted based on the words and whether
        there are any pauses, slow speech or disfluencies.

        Use of this will require `pip install speechmatics-voice[smart]` and may not
        be suited to low-power devices.
        """
        return VoiceAgentConfigPreset._merge_configs(
            VoiceAgentConfig(
                operating_point=OperatingPoint.ENHANCED,
                enable_diarization=True,
                max_delay=2.0,
                end_of_utterance_silence_trigger=0.7,
                end_of_utterance_mode=EndOfUtteranceMode.ADAPTIVE,
                speech_segment_config=SpeechSegmentConfig(emit_sentences=False),
                vad_config=VoiceActivityConfig(enabled=True),
                end_of_turn_config=EndOfTurnConfig(use_forced_eou=True),
            ),
            overlay,
        )

    @staticmethod
    def SMART_TURN(overlay: Optional[VoiceAgentConfig] = None) -> VoiceAgentConfig:  # noqa: N802
        """Best suited for complex conversational use cases.

        For conversation, there is a balance between accuracy, speed and the rate at
        which the end of turn is emitted. The use of SMART_TURN means that the delay to
        finalizing the spoken sentences will be adjusted based on the words and whether
        there are any pauses, slow speech or disfluencies.

        This preset will use a model to detect for acoustic indicators from the
        speaker to determine when a turn has ended.

        Use of this will require `pip install speechmatics-voice[smart]` and may not
        be suited to low-power devices.
        """
        return VoiceAgentConfigPreset._merge_configs(
            VoiceAgentConfig(
                operating_point=OperatingPoint.ENHANCED,
                enable_diarization=True,
                max_delay=2.0,
                end_of_utterance_silence_trigger=0.8,
                end_of_utterance_mode=EndOfUtteranceMode.ADAPTIVE,
                speech_segment_config=SpeechSegmentConfig(emit_sentences=False),
                smart_turn_config=SmartTurnConfig(
                    enabled=True,
                ),
                vad_config=VoiceActivityConfig(enabled=True),
                end_of_turn_config=EndOfTurnConfig(use_forced_eou=True),
            ),
            overlay,
        )

    @staticmethod
    def SCRIBE(overlay: Optional[VoiceAgentConfig] = None) -> VoiceAgentConfig:  # noqa: N802
        """Best suited for note-taking and scribes.

        This mode will emit partial and final segments as they become available. The end of
        utterance is set to fixed. End of turn is not required for note-taking.

        Use of this will require `pip install speechmatics-voice[smart]` and may not
        be suited to low-power devices.
        """
        return VoiceAgentConfigPreset._merge_configs(
            VoiceAgentConfig(
                operating_point=OperatingPoint.ENHANCED,
                enable_diarization=True,
                max_delay=2.0,
                end_of_utterance_silence_trigger=1.0,
                end_of_utterance_mode=EndOfUtteranceMode.FIXED,
                speech_segment_config=SpeechSegmentConfig(emit_sentences=True),
            ),
            overlay,
        )

    @staticmethod
    def CAPTIONS(overlay: Optional[VoiceAgentConfig] = None) -> VoiceAgentConfig:  # noqa: N802
        """Best suited for captioning.

        This mode will emit final segments as they become available. The end of
        utterance is set to fixed. End of turn is not required for captioning.
        """
        return VoiceAgentConfigPreset._merge_configs(
            VoiceAgentConfig(
                operating_point=OperatingPoint.ENHANCED,
                enable_diarization=True,
                max_delay=0.7,
                end_of_utterance_silence_trigger=0.5,
                end_of_utterance_mode=EndOfUtteranceMode.FIXED,
                speech_segment_config=SpeechSegmentConfig(emit_sentences=True),
                include_partials=False,
            ),
            overlay,
        )

    @staticmethod
    def EXTERNAL(overlay: Optional[VoiceAgentConfig] = None) -> VoiceAgentConfig:  # noqa: N802
        """Best suited for external turn control.

        This mode will emit partial and final segments as they become available. The end of
        utterance is set to external. End of turn is not required for external turn control.
        """
        return VoiceAgentConfigPreset._merge_configs(
            VoiceAgentConfig(
                operating_point=OperatingPoint.ENHANCED,
                enable_diarization=True,
                max_delay=2.0,
                end_of_utterance_mode=EndOfUtteranceMode.EXTERNAL,
                speech_segment_config=SpeechSegmentConfig(emit_sentences=False),
                end_of_turn_config=EndOfTurnConfig(use_forced_eou=True),
            ),
            overlay,
        )

    @staticmethod
    def list_presets() -> list[str]:
        """List available presets."""
        return [attr.lower() for attr in dir(VoiceAgentConfigPreset) if not attr.startswith("_") and attr.isupper()]

    @staticmethod
    def load(preset: str, overlay_json: Optional[str] = None) -> VoiceAgentConfig:
        """Get a preset configuration.

        Args:
            preset: Preset to use.
            overlay_json: Optional overlay JSON to apply to the preset.

        Returns:
            VoiceAgentConfig: Preset configuration.
        """
        try:
            config: VoiceAgentConfig = getattr(VoiceAgentConfigPreset, preset.upper())()
            if overlay_json is not None:
                overlay = VoiceAgentConfig.from_json(overlay_json)
                config = VoiceAgentConfigPreset._merge_configs(config, overlay)
            return config
        except ValueError:
            raise ValueError(f"Invalid overlay JSON: {overlay_json}")
        except AttributeError:
            raise ValueError(f"Invalid preset: {preset}")

    @staticmethod
    def _merge_configs(base: VoiceAgentConfig, overlay: Optional[VoiceAgentConfig]) -> VoiceAgentConfig:
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

        # Merge overlay into base
        merged_dict = {
            **base.model_dump(exclude_unset=True, exclude_none=True),
            **overlay.model_dump(exclude_unset=True, exclude_none=True),
        }
        return VoiceAgentConfig.from_dict(merged_dict)
