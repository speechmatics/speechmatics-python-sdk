"""
Transport-agnostic logic shared by the async and sync Batch clients.

Request construction and response parsing live here so that ``AsyncClient`` and
``Client`` cannot drift apart: the only thing the two client modules should
differ in is how they perform I/O.
"""

from __future__ import annotations

import logging
import os
import random
from typing import Any
from typing import BinaryIO
from typing import Optional
from typing import Union

from ._exceptions import BatchError
from ._exceptions import JobError
from ._models import ConnectionConfig
from ._models import FormatType
from ._models import JobConfig
from ._models import JobDetails
from ._models import JobStatus
from ._models import JobType
from ._models import Transcript
from ._models import TranscriptionConfig

PROCESSING_DATA_HEADER = "X-SM-Processing-Data"

# Slack on top of a server-side ``wait``, so the request is not aborted
# client-side while the server is still inside its own wait window.
WAIT_TIMEOUT_BUFFER = 10.0

# The API spells the default format ``json-v2`` where the SDK spells it
# FormatType.JSON. This value is both the ``format`` query parameter and the
# key an embedded transcript arrives under.
_API_FORMAT_VALUES = {
    FormatType.JSON: "json-v2",
    FormatType.TXT: "txt",
    FormatType.SRT: "srt",
}

_ACTIVE_JOB_STATUSES = (JobStatus.CREATED, JobStatus.RUNNING)

_FAILED_JOB_STATUSES = {
    JobStatus.REJECTED: "was rejected",
    JobStatus.DELETED: "was deleted before it finished",
    JobStatus.EXPIRED: "has expired",
}


def api_format_value(format_type: FormatType) -> str:
    """Return the API's name for an output format (FormatType.JSON -> json-v2)."""
    return _API_FORMAT_VALUES[format_type]


def is_job_active(status: JobStatus) -> bool:
    """Return True while a job is still queued or running."""
    return status in _ACTIVE_JOB_STATUSES


def raise_for_failed_status(job_id: str, status: JobStatus) -> None:
    """Raise JobError if a status is terminal and not successful."""
    reason = _FAILED_JOB_STATUSES.get(status)
    if reason is not None:
        raise JobError(f"Job {job_id} {reason}")


def build_job_config(
    config: Optional[JobConfig],
    transcription_config: Optional[TranscriptionConfig],
) -> JobConfig:
    """Return the job config to submit, building a default one if needed."""
    if config is not None:
        return config
    return JobConfig(
        type=JobType.TRANSCRIPTION,
        transcription_config=transcription_config or TranscriptionConfig(),
    )


def validate_audio_source(audio_file: Union[str, BinaryIO, None], config_dict: dict[str, Any]) -> bool:
    """
    Validate that exactly one audio source is configured.

    Returns:
        True if the job fetches its own audio via ``fetch_data``.
    """
    has_fetch_data = "fetch_data" in config_dict
    if audio_file is not None and has_fetch_data:
        raise ValueError("Cannot specify both audio_file and fetch_data")
    if audio_file is None and not has_fetch_data:
        raise ValueError("Must provide either audio_file or fetch_data in config")
    return has_fetch_data


def validate_wait(wait: Optional[int]) -> None:
    """
    Validate the ``wait`` argument.

    Raises:
        ValueError: If wait is negative or not a whole number of seconds.
    """
    if wait is None:
        return
    if wait < 0:
        raise ValueError("wait must be a non-negative number of seconds")
    if not float(wait).is_integer():
        raise ValueError("wait must be a whole number of seconds")


def warn_deprecated_operating_point(config: JobConfig) -> None:
    """Emit the deprecation warning for ``operating_point`` if it is in use."""
    if config.transcription_config is not None and config.transcription_config.operating_point is not None:
        logging.warning(
            "TranscriptionConfig.operating_point is deprecated and will be removed in the future. Please use the model property instead."
        )


def resolve_stream_filename(audio_file: BinaryIO) -> str:
    """Derive a filename for a file-like audio source."""
    filename = getattr(audio_file, "name", "audio.wav")
    if hasattr(filename, "split"):
        filename = os.path.basename(filename)
    return str(filename)


def build_fetch_data_multipart(config_dict: dict[str, Any]) -> tuple[dict[str, Any], str]:
    """Build multipart fields for a ``fetch_data`` submission."""
    return {"config": config_dict}, str(config_dict["fetch_data"]["url"])


def build_file_multipart(
    config_dict: dict[str, Any],
    filename: str,
    file_data: Union[BinaryIO, bytes],
) -> dict[str, Any]:
    """Build multipart fields for a file upload submission."""
    return {
        "config": config_dict,
        "data_file": (filename, file_data, "audio/wav"),
    }


def build_processing_data_header(
    parallel_engines: Optional[int],
    user_id: Optional[str],
) -> Optional[dict[str, Any]]:
    """Build the ``X-SM-Processing-Data`` header value, if any is needed."""
    processing_data: dict[str, Any] = {}
    if parallel_engines is not None:
        processing_data["parallel_engines"] = parallel_engines
    if user_id is not None:
        processing_data["user_id"] = user_id
    if not processing_data:
        return None
    return {PROCESSING_DATA_HEADER: processing_data}


def build_list_jobs_params(
    limit: Optional[int],
    created_before: Optional[str],
    created_after: Optional[str],
) -> Optional[dict[str, str]]:
    """Build query parameters for listing jobs."""
    params: dict[str, str] = {}
    if limit is not None:
        params["limit"] = str(limit)
    if created_before:
        params["created_before"] = created_before
    if created_after:
        params["created_after"] = created_after
    return params or None


def build_delete_job_params(force: bool) -> Optional[dict[str, str]]:
    """Query parameters for deleting a job; a running job needs force."""
    return {"force": "true"} if force else None


def build_query_params(
    *,
    wait: Optional[int] = None,
    format_type: FormatType = FormatType.JSON,
) -> Optional[dict[str, str]]:
    """
    Build query parameters for synchronous transcription.

    ``wait`` asks the server to hold the request open until the job reaches a
    terminal state. ``format`` is omitted for FormatType.JSON because that is
    the documented API default (``json-v2``).
    """
    validate_wait(wait)
    params: dict[str, str] = {}
    if wait is not None:
        params["wait"] = str(int(wait))
    if format_type != FormatType.JSON:
        params["format"] = api_format_value(format_type)
    return params or None


def build_submit_query_params(
    wait: Optional[int],
    format_type: FormatType,
) -> Optional[dict[str, str]]:
    """
    Build query parameters for a job submission.

    ``format`` only describes the transcript the server embeds while waiting, so
    it is pointless without ``wait``.
    """
    if wait is None:
        return None
    return build_query_params(wait=wait, format_type=format_type)


def request_timeout_for_wait(wait: Optional[int], conn_config: ConnectionConfig) -> Optional[float]:
    """
    Request timeout that covers both the upload and the server-side ``wait``.

    The wait window is added to the configured operation timeout rather than
    replacing it, so that asking the server to wait can never give a request
    less time than the same request without ``wait``.
    """
    if wait is None:
        return None
    return conn_config.operation_timeout + wait + WAIT_TIMEOUT_BUFFER


def clamp_wait(wait: Optional[int], remaining_timeout: Optional[float]) -> Optional[int]:
    """
    Reduce ``wait`` so it cannot outlive the caller's overall timeout.

    Without this, ``transcribe(timeout=5, wait=60)`` would block for the full
    60 seconds inside the submit call before the deadline was ever checked.
    """
    if wait is None or remaining_timeout is None:
        return wait
    return max(0, min(wait, int(remaining_timeout)))


def extract_embedded_transcript(
    response: dict[str, Any],
    format_type: FormatType = FormatType.JSON,
) -> Optional[Union[Transcript, str]]:
    """
    Pull the transcript out of a response that embedded one.

    When a ``wait`` request finishes in time, the transcript is embedded under a
    key named after the requested format: a string for ``txt``/``srt``, and a
    nested transcript object for ``json-v2``.
    """
    value = response.get(api_format_value(format_type))

    if format_type == FormatType.JSON:
        return Transcript.from_dict(value) if isinstance(value, dict) else None
    return value if isinstance(value, str) else None


def job_details_from_submit_response(
    response: dict[str, Any],
    config: JobConfig,
    filename: str,
    format_type: FormatType = FormatType.JSON,
) -> JobDetails:
    """Build JobDetails from a ``POST /jobs`` response."""
    job_id = response.get("id")
    if not job_id:
        raise BatchError("No job ID returned from server")

    raw_status = response.get("status")
    status = JobStatus(raw_status) if raw_status else JobStatus.RUNNING

    return JobDetails(
        id=job_id,
        status=status,
        created_at=response.get("created_at", ""),
        data_name=filename,
        config=config,
        transcript=extract_embedded_transcript(response, format_type),
    )


def jittered_interval(base_interval: float) -> float:
    """
    Add +/-20% jitter to a polling interval.

    Many clients polling on a fixed interval synchronise into load spikes
    against the API, so spread them out.
    """
    return base_interval * random.uniform(0.8, 1.2)  # noqa: S311 - jitter, not crypto
