from typing import Optional


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
    """
    Raised when there's an error in the transport layer.

    Attributes:
        status_code: HTTP status code, when the error came from an HTTP response.
    """

    def __init__(self, message: str, *, status_code: Optional[int] = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class BatchError(Exception):
    """Raised when batch processing fails."""

    pass


class JobError(Exception):
    """Raised when there's an error with a job."""

    pass


class TranscriptNotReadyError(JobError):
    """
    Raised when a transcript is requested before it is available.

    The API answers ``GET /jobs/{id}/transcript`` with HTTP 404 both while a job
    is still running and for a job that does not exist, so retry the request
    (or check the job status) rather than assuming the job is missing.
    """

    pass


class JobExpiredError(JobError):
    """
    Raised when a job's data has expired and been deleted from storage.

    Speechmatics retains job data for a limited time. Once it expires, both
    ``GET /jobs/{id}`` and ``GET /jobs/{id}/transcript`` answer with HTTP 410,
    not a ``status`` field, so this is raised instead of a generic JobError.
    """

    pass


class TimeoutError(Exception):
    """Raised when an operation times out."""

    pass
