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


class BatchError(Exception):
    """Raised when batch processing fails."""

    pass


class JobError(Exception):
    """Raised when there's an error with a job."""

    pass


class TimeoutError(Exception):
    """Raised when an operation times out."""

    pass
