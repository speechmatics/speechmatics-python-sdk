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


class ConversationError(Exception):
    """
    Indicates an error in Flow conversation session.

    This is raised when the Flow service returns an error message
    during an active conversation session.
    """

    pass


class ConversationEndedException(Exception):
    """
    Indicates the conversation session ended.

    This is a normal control flow exception that signals the
    conversation has completed successfully.
    """

    pass
