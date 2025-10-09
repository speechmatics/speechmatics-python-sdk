import logging
import sys

import pyaudio

from speechmatics.rt import Microphone


def select_audio_device() -> int | None:
    """Interactive microphone device selection.

    Returns:
        Device index or None for default device
    """
    devices = Microphone.list_devices()
    if not devices:
        return None

    print("Available microphones:")
    for device in devices:
        print(f"  [{device['index']}] {device['name']} ({device['channels']} channels)")
    print()

    return _get_device_choice(
        [d["index"] for d in devices],
        "Enter device index (or press Enter for default): ",
    )


def select_audio_output_device() -> int | None:
    """Interactive audio output device selection.

    Returns:
        Device index or None for default device
    """
    try:
        output_devices = _get_output_devices()
        if not output_devices:
            print("No audio output devices found.")
            return None

        print("Available audio output devices:")
        for device in output_devices:
            print(f"  [{device['index']}] {device['name']} ({device['channels']} channels, {device['sample_rate']}Hz)")
        print()

        return _get_device_choice(
            [d["index"] for d in output_devices],
            "Enter output device index (or press Enter for default): ",
        )

    except Exception as e:
        print(f"Error listing audio devices: {e}")
        return None


def _get_output_devices() -> list[dict]:
    """Get list of available output devices."""
    p = pyaudio.PyAudio()
    try:
        devices = []
        for i in range(p.get_device_count()):
            info = p.get_device_info_by_index(i)
            if info["maxOutputChannels"] > 0:
                devices.append(
                    {
                        "index": i,
                        "name": info["name"],
                        "channels": info["maxOutputChannels"],
                        "sample_rate": int(info["defaultSampleRate"]),
                    }
                )
        return devices
    finally:
        p.terminate()


def _get_device_choice(valid_indices: list[int], prompt: str) -> int | None:
    """Get user device choice with validation."""
    while True:
        try:
            choice = input(prompt).strip()
            if not choice:
                return None

            device_index = int(choice)
            if device_index in valid_indices:
                return device_index

            print(f"Invalid device index. Choose from: {valid_indices}")

        except ValueError:
            print("Please enter a valid number.")
        except KeyboardInterrupt:
            return None


class AudioPlayer:
    """Real-time audio player using PyAudio."""

    def __init__(
        self,
        sample_rate: int,
        channels: int = 1,
        sample_width: int = 2,
        device_index: int | None = None,
    ):
        """Initialize audio player.

        Args:
            sample_rate: Audio sample rate in Hz
            channels: Number of audio channels (1 for mono)
            sample_width: Sample width in bytes (2 for 16-bit)
            device_index: Output device index (None for default)
        """
        self.sample_rate = sample_rate
        self.channels = channels
        self.sample_width = sample_width
        self.device_index = device_index
        self.p = None
        self.stream = None

    def start(self) -> bool:
        """Start audio playback stream."""
        try:
            self.p = pyaudio.PyAudio()
            if not self.p:
                return False

            audio_format = self._get_audio_format()
            if not audio_format:
                return False

            self.stream = self.p.open(
                format=audio_format,
                channels=self.channels,
                rate=self.sample_rate,
                output=True,
                output_device_index=self.device_index,
            )
            return True

        except Exception as e:
            print(f"Error starting audio player: {e}")
            return False

    def play(self, audio_data: bytes) -> None:
        """Play audio data chunk."""
        if self.stream:
            self.stream.write(audio_data)

    def stop(self) -> None:
        """Stop and cleanup audio player."""
        if self.stream:
            self.stream.stop_stream()
            self.stream.close()
            self.stream = None

        if self.p:
            self.p.terminate()
            self.p = None

    def _get_audio_format(self) -> int | None:
        """Get PyAudio format from sample width."""
        format_map = {1: pyaudio.paInt8, 2: pyaudio.paInt16, 4: pyaudio.paInt32}
        if self.sample_width not in format_map:
            print(f"Unsupported sample width: {self.sample_width}")
            return None
        return format_map[self.sample_width]


class CustomLevels:
    """Custom logging levels for transcription events."""

    PARTIAL = 11  # Partial transcription results
    FINAL = 12  # Final transcription results
    SPEAKER = 15  # Speech activity events


class CustomTextFormatter(logging.Formatter):
    """Coloured logging formatter for transcription events."""

    # FORMAT = "%(asctime)s.%(msecs)03d %(levelname)-8s (%(filename)s:%(lineno)d) %(message)s"
    FORMAT = "%(asctime)s.%(msecs)03d %(levelname)-8s %(message)s"

    # ANSI colour codes
    COLOURS = {
        logging.DEBUG: "\033[90m",  # Gray
        CustomLevels.PARTIAL: "\033[32m",  # Green
        CustomLevels.FINAL: "\033[33m",  # Yellow
        CustomLevels.SPEAKER: "\033[36m",  # Cyan
    }
    RESET = "\033[0m\r"

    def format(self, record):
        colour = self.COLOURS.get(record.levelno, self.RESET)
        message = super().format(record)
        return f"{colour}{message}{self.RESET}"


def get_logger(name: str) -> logging.Logger:
    """Setup coloured logger for transcription events."""
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)

    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    logging.getLogger("speechmatics.voice").setLevel(logging.DEBUG)

    # Register custom level names
    logging.addLevelName(CustomLevels.PARTIAL, "PARTIAL")
    logging.addLevelName(CustomLevels.FINAL, "FINAL")
    logging.addLevelName(CustomLevels.SPEAKER, "SPEAKER")

    # Apply custom formatter to all handlers
    formatter = CustomTextFormatter(CustomTextFormatter.FORMAT, datefmt="%Y-%m-%d %H:%M:%S")
    for handler in logging.root.handlers:
        handler.setFormatter(formatter)

    return logger
