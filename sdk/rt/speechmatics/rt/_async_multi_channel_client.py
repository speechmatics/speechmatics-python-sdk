from __future__ import annotations

import asyncio
import contextlib
from typing import Any
from typing import BinaryIO
from typing import Optional

from ._audio_sources import MultiChanSource
from ._auth import AuthBase
from ._base_client import _BaseClient
from ._exceptions import ConfigurationError
from ._exceptions import TimeoutError
from ._exceptions import TranscriptionError
from ._logging import get_logger
from ._models import AudioEventsConfig
from ._models import AudioFormat
from ._models import ClientMessageType
from ._models import ConnectionConfig
from ._models import ServerMessageType
from ._models import TranscriptionConfig
from ._models import TranslationConfig
from ._utils.audio import b64_encode_audio
from ._utils.message import build_start_recognition_message
from .constants import CHUNK_SIZE


class AsyncMultiChannelClient(_BaseClient):
    """
    Async client for multi-channel real-time audio transcription.

    This client enables simultaneous transcription of multiple audio streams
    over a single WebSocket connection. Each audio stream is identified by a
    channel ID, and the server provides channel-tagged transcription results.

    The client handles multiple audio sources using a round-robin approach to
    ensure fair bandwidth distribution across channels. Audio data is base64-encoded
    and wrapped in JSON messages for transmission.

    Args:
        auth: Authentication instance. If not provided, uses StaticKeyAuth
                with api_key parameter or SPEECHMATICS_API_KEY environment variable.
        api_key: Speechmatics API key used if auth not provided.
        url: WebSocket endpoint URL. If not provided, uses SPEECHMATICS_RT_URL
                environment variable or defaults to EU endpoint.
        conn_config: Websocket connection configuration.

    Examples:
        Transcribing stereo audio:
        >>> sources = {
        ...     "left": open("left_channel.wav", "rb"),
        ...     "right": open("right_channel.wav", "rb")
        ... }
        >>> async with AsyncMultiChannelClient(api_key="your-key") as client:
        ...     @client.on(ServerMessageType.ADD_TRANSCRIPT)
        ...     def handle_transcript(msg):
        ...         channel = msg['results'][0]['channel']
        ...         transcript = msg['metadata']['transcript']
        ...         print(f"Channel {channel}: {transcript}")
        ...
        ...     await client.transcribe(sources)
    """

    def __init__(
        self,
        auth: Optional[AuthBase] = None,
        *,
        api_key: Optional[str] = None,
        url: Optional[str] = None,
        conn_config: Optional[ConnectionConfig] = None,
    ) -> None:
        self._logger = get_logger(__name__)

        (
            self._session,
            self._rec_started_evt,
            self._session_done_evt,
        ) = self._init_session_info()
        self._eos_sent = False

        transport = self._create_transport_from_config(
            auth=auth,
            api_key=api_key,
            url=url,
            conn_config=conn_config,
            request_id=self._session.request_id,
        )

        super().__init__(transport)

        self.on(ServerMessageType.RECOGNITION_STARTED, self._on_recognition_started)
        self.on(ServerMessageType.END_OF_TRANSCRIPT, self._on_eot)
        self.on(ServerMessageType.ERROR, self._on_error)
        self.on(ServerMessageType.WARNING, self._on_warning)

        self._logger.debug(
            "AsyncMultiChannelClient initialized (request_id=%s)",
            self._session.request_id,
        )

    async def transcribe(
        self,
        sources: dict[str, BinaryIO],
        *,
        transcription_config: Optional[TranscriptionConfig] = None,
        audio_format: Optional[AudioFormat] = None,
        translation_config: Optional[TranslationConfig] = None,
        audio_events_config: Optional[AudioEventsConfig] = None,
        ws_headers: Optional[dict] = None,
        timeout: Optional[float] = None,
    ) -> None:
        """
        Transcribe multiple audio streams simultaneously in real-time.

        This method establishes a WebSocket connection, configures the transcription
        session for multiple channels, streams audio data from all sources in a
        round-robin fashion, and processes results through registered event handlers.

        Args:
            sources: Dictionary mapping channel IDs to file-like objects containing
                    audio data. Keys are channel identifiers (e.g., "left", "right").
                    Values must be opened in binary mode ('rb').
                    Example: {"left": open("left.wav", "rb"), "right": open("right.wav", "rb")}
            transcription_config: Configuration for transcription behavior such as
                                language, partial transcripts, and advanced features.
                                Uses default if not provided.
            audio_format: Audio format specification including encoding, sample rate,
                        and chunk size. Uses default (PCM 16-bit LE, 44.1kHz) if
                        not provided.
            ws_headers: Additional headers to include in the WebSocket handshake.
            timeout: Maximum time in seconds to wait for transcription completion.
                    Default None.
        Raises:
            AudioError: If sources is empty or contains invalid audio streams.
            TimeoutError: If transcription exceeds the specified timeout.
            TranscriptionError: If the server reports an error during transcription.
            ConnectionError: If the WebSocket connection fails.

        Examples:
            Basic multi-channel transcription:
            >>> sources = {
            ...     "left": open("left_channel.wav", "rb"),
            ...     "right": open("right_channel.wav", "rb")
            ... }
            >>> await client.transcribe(sources)

            With custom configuration:
            >>> config = TranscriptionConfig(
            ...     language="en",
            ...     enable_partials=True,
            ... )
            >>> audio_fmt = AudioFormat(
            ...     encoding=AudioEncoding.PCM_S16LE,
            ...     sample_rate=16000
            ... )
            >>> await client.transcribe(
            ...     sources,
            ...     transcription_config=config,
            ...     audio_format=audio_fmt,
            ... )
        """
        audio_format = audio_format or AudioFormat()
        transcription_config = transcription_config or TranscriptionConfig()

        self._validate_diarization_config(transcription_config, sources)
        sources = self._remap_sources_with_labels(transcription_config, sources)

        start_recognition_message = build_start_recognition_message(
            transcription_config=transcription_config,
            audio_format=audio_format,
            translation_config=translation_config,
            audio_events_config=audio_events_config,
        )

        try:
            await asyncio.wait_for(
                self._run_pipeline(
                    sources,
                    start_recognition_message,
                    ws_headers,
                    audio_format.chunk_size,
                ),
                timeout=timeout,
            )
        except asyncio.TimeoutError as exc:
            raise TimeoutError("Transcription session timed out") from exc

    async def _run_pipeline(
        self,
        sources: dict[str, BinaryIO],
        start_recognition_message: dict[str, Any],
        ws_headers: Optional[dict[str, Any]],
        chunk_size: int = CHUNK_SIZE,
    ) -> None:
        """
        Run the multi-channel audio streaming pipeline and wait for completion.

        This method orchestrates the multi-channel audio streaming process by
        starting the audio producer task and waiting for the session to complete.
        It ensures proper cleanup even if the producer encounters errors.

        Args:
            sources: Dictionary of channel IDs to audio file handles
            chunk_size: Size of audio chunks in bytes
        """
        await self._transport.connect(ws_headers)
        await self._send_message(start_recognition_message)

        await asyncio.wait_for(self._rec_started_evt.wait(), timeout=5.0)

        producer = asyncio.create_task(self._producer(sources, chunk_size))
        await self._session_done_evt.wait()
        with contextlib.suppress(Exception):
            await asyncio.wait_for(producer, timeout=2.0)

    async def _producer(self, sources: dict[str, BinaryIO], chunk_size: int) -> None:
        """
        Continuously read from multiple audio sources and send data to the server.

        This method implements round-robin reading across all channels, ensuring
        fair bandwidth distribution. Each audio chunk is base64-encoded and wrapped
        in a JSON message with channel identification.

        Args:
            sources: Dictionary mapping channel IDs to file-like objects
            chunk_size: Size of audio chunks in bytes
        """
        multi_chan_src = MultiChanSource(sources, chunk_size=chunk_size)
        seq_no_mapping = dict.fromkeys(sources.keys(), 0)

        try:
            async for chan_id, chunk in multi_chan_src:
                if self._session_done_evt.is_set():
                    break

                seq_no_mapping[chan_id] += 1
                frame = b64_encode_audio(chan_id, chunk)

                try:
                    await self._send_message(frame)
                except Exception as e:
                    self._logger.error("Failed to send audio chunk for channel %s: %s", chan_id, e)
                    self._session_done_evt.set()
                    break

            if not self._eos_sent and not self._session_done_evt.is_set():
                try:
                    for chan_id in sources:
                        await self._send_message(
                            {
                                "message": ClientMessageType.END_OF_CHANNEL,
                                "channel": chan_id,
                                "last_seq_no": seq_no_mapping[chan_id],
                            }
                        )
                except Exception as e:
                    self._logger.error("Failed to send EndOfChannel message: %s", e)
                finally:
                    self._eos_sent = True
        except Exception as e:
            self._logger.error("Audio producer error: %s", e)
            self._session_done_evt.set()

    def _on_recognition_started(self, msg: dict[str, Any]) -> None:
        """Handle RecognitionStarted message from server."""
        self._session.session_id = msg.get("id")
        self._rec_started_evt.set()
        self._logger.debug(
            "Recognition started (session_id=%s)",
            self._session.session_id,
        )

    def _on_eot(self, msg: dict[str, Any]) -> None:
        """Handle EndOfTranscript message from server."""
        self._session_done_evt.set()

    def _on_error(self, msg: dict[str, Any]) -> None:
        """Handle Error message from server."""
        self._session_done_evt.set()
        raise TranscriptionError(msg.get("reason", "unknown"))

    def _on_warning(self, msg: dict[str, Any]) -> None:
        """Handle Warning message from server."""
        self._logger.warning("Server warning: %s", msg.get("reason", "unknown"))

    async def close(self) -> None:
        """
        Close the client and clean up resources.

        Ensures the session is marked as complete and delegates to the base
        class for full cleanup including WebSocket connection termination.
        """
        self._session_done_evt.set()
        await super().close()

    def _validate_diarization_config(
        self, transcription_config: TranscriptionConfig, sources: dict[str, BinaryIO]
    ) -> None:
        """
        Validate diarization settings and source-channel consistency.

        Raises:
            ConfigurationError: If any part of the configuration is invalid.
        """
        if not sources:
            raise ConfigurationError("Audio input sources cannot be empty")

        dz_options = ["channel", "channel_and_speaker"]
        if transcription_config.diarization and transcription_config.diarization not in dz_options:
            raise ConfigurationError(
                f"Diarization must be one of {dz_options}, got '{transcription_config.diarization}'."
            )

        if transcription_config.diarization is None:
            transcription_config.diarization = "channel"

        chan_labels = transcription_config.channel_diarization_labels
        if chan_labels:
            if len(chan_labels) != len(sources):
                raise ConfigurationError(f"Expected {len(sources)} channel labels, got {len(chan_labels)}.")

            if len(set(chan_labels)) != len(chan_labels):
                raise ConfigurationError("Channel labels must be unique.")

    def _remap_sources_with_labels(
        self, transcription_config: TranscriptionConfig, sources: dict[str, BinaryIO]
    ) -> dict[str, BinaryIO]:
        """
        Set default diarization values and return sources remapped to channel labels.

        Returns:
            A dict mapping channel labels to audio sources.
        """

        if transcription_config.channel_diarization_labels is None:
            transcription_config.channel_diarization_labels = list(sources.keys())

        original_keys = sorted(sources.keys())
        return {
            label: sources[original_keys[i]] for i, label in enumerate(transcription_config.channel_diarization_labels)
        }
