class ConfigurationError(Exception):
    """Raised when there's an error in configuration."""

    pass


class AuthenticationError(Exception):
    """Raised when authentication fails."""

    pass


class ConnectionError(Exception):
    """Raised when connection to the service fails."""

    pass


class TransportError(Exception):
    """Raised when there's an error in the transport layer."""

    pass


class TranscriptionError(Exception):
    """Raised when transcription fails."""

    pass


class AudioError(Exception):
    """Raised when there's an issue with audio data."""

    pass


class SessionError(Exception):
    """Raised when there's an error with the session state."""

    pass


class TimeoutError(Exception):
    """Raised when an operation times out."""

    pass


class EndOfTranscriptError(Exception):
    """Raised when the transcript has ended."""

    pass
