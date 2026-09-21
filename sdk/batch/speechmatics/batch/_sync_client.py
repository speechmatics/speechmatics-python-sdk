"""
Synchronous client for Speechmatics batch transcription.

This module provides the blocking Client class for callers that do not run an
event loop, such as scripts, notebooks, serverless handlers and synchronous
web frameworks.
"""

from __future__ import annotations

import os
import time
import uuid
from typing import Any
from typing import BinaryIO
from typing import Optional
from typing import Union

from ._auth import AuthBase
from ._auth import StaticKeyAuth
from ._common import DEFAULT_TIMEOUT
from ._common import MAX_TRANSIENT_POLL_FAILURES
from ._common import PollingInterval
from ._common import build_delete_job_params
from ._common import build_fetch_data_multipart
from ._common import build_file_multipart
from ._common import build_job_config
from ._common import build_list_jobs_params
from ._common import build_processing_data_header
from ._common import build_query_params
from ._common import build_submit_query_params
from ._common import clamp_wait
from ._common import is_job_active
from ._common import is_transient_poll_error
from ._common import job_details_from_submit_response
from ._common import raise_for_failed_status
from ._common import request_timeout_for_wait
from ._common import validate_audio_source
from ._common import validate_wait
from ._common import warn_deprecated_operating_point
from ._exceptions import AuthenticationError
from ._exceptions import BatchError
from ._exceptions import JobError
from ._exceptions import JobExpiredError
from ._exceptions import TimeoutError
from ._exceptions import TranscriptNotReadyError
from ._exceptions import TransportError
from ._helpers import prepare_audio_file_sync
from ._logging import get_logger
from ._models import ConnectionConfig
from ._models import FormatType
from ._models import JobConfig
from ._models import JobDetails
from ._models import JobStatus
from ._models import Transcript
from ._models import TranscriptionConfig
from ._sync_transport import SyncTransport


class Client:
    """
    Synchronous client for Speechmatics batch speech transcription.

    This is the blocking counterpart of :class:`AsyncClient`, for code that is
    not running an event loop. It exposes the same operations and returns the
    same models.

    Args:
        auth: Authentication instance. If not provided, uses StaticKeyAuth
              with api_key parameter or SPEECHMATICS_API_KEY environment variable.
        api_key: Speechmatics API key (used only if auth not provided).
        url: REST API endpoint URL. If not provided, uses SPEECHMATICS_BATCH_URL
             environment variable or defaults to production endpoint.
        conn_config: Complete connection configuration object. If provided, overrides
               other parameters.

    Raises:
        ConfigurationError: If required configuration is missing or invalid.

    Examples:
        Transcribe in a single call, letting the server hold the request open
        until the transcript is ready:
            >>> with Client(api_key="your-key") as client:
            ...     result = client.transcribe("audio.wav", wait=60)
            ...     print(result.transcript_text)

        Submit and poll explicitly:
            >>> with Client(api_key="your-key") as client:
            ...     job = client.submit_job("audio.wav")
            ...     result = client.wait_for_completion(job.id)
    """

    def __init__(
        self,
        auth: Optional[AuthBase] = None,
        *,
        api_key: Optional[str] = None,
        url: Optional[str] = None,
        conn_config: Optional[ConnectionConfig] = None,
    ) -> None:
        """
        Initialize the Client.

        Args:
            auth: Authentication method, it can be StaticKeyAuth or JWTAuth.
                If None, creates StaticKeyAuth with the api_key.
            api_key: Speechmatics API key. If None, uses SPEECHMATICS_API_KEY env var.
            url: REST API endpoint URL. If None, uses SPEECHMATICS_BATCH_URL env var
                 or defaults to production endpoint.
            conn_config: Complete connection configuration.

        Raises:
            ConfigurationError: If auth is None and API key is not provided/found.
        """
        self._auth = auth or StaticKeyAuth(api_key)
        self._url = url or os.environ.get("SPEECHMATICS_BATCH_URL") or "https://asr.api.speechmatics.com/v2"
        self._conn_config = conn_config or ConnectionConfig()
        self._request_id = str(uuid.uuid4())
        self._transport = SyncTransport(self._url, self._conn_config, self._auth, self._request_id)

        self._logger = get_logger(__name__)
        self._logger.debug("Client initialized (request_id=%s, url=%s)", self._request_id, self._url)

    def __enter__(self) -> Client:
        """
        Context manager entry.

        Returns:
            Self for use in with statements.

        Examples:
            >>> with Client(api_key="key") as client:
            ...     job = client.submit_job("audio.wav")
        """
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """
        Context manager exit with automatic cleanup.

        Args:
            exc_type: Exception type if an exception occurred.
            exc_val: Exception value if an exception occurred.
            exc_tb: Exception traceback if an exception occurred.
        """
        self.close()

    def submit_job(
        self,
        audio_file: Union[str, BinaryIO, None],
        *,
        config: Optional[JobConfig] = None,
        transcription_config: Optional[TranscriptionConfig] = None,
        parallel_engines: Optional[int] = None,
        user_id: Optional[str] = None,
        wait: Optional[int] = None,
        format_type: FormatType = FormatType.JSON,
    ) -> JobDetails:
        """
        Submit a new transcription job.

        Args:
            audio_file: Path to audio file or file-like object containing audio data, or None if using fetch_data.
                NOTE: You must explicitly pass audio_file=None if providing a fetch_data in the config
            config: Complete job configuration. If not provided, uses transcription_config
                   to build a basic job configuration.
            transcription_config: Transcription-specific configuration. Used if config
                                is not provided.
            parallel_engines: Optional number of parallel engines to request for this job.
                               Sent as ``{"parallel_engines": N}`` in the ``X-SM-Processing-Data`` header.
                               This only applies when using the container onPrem on http batch mode.
            user_id: Optional user identifier to associate with this job.
                    Sent as ``{"user_id": "..."}`` in the ``X-SM-Processing-Data`` header.
                    This only applies when using the container onPrem on http batch mode.
            wait: Seconds to let the server hold the request open waiting for the
                job to finish (synchronous transcription, SaaS only). When the job
                finishes in time, the returned JobDetails has status DONE and
                carries the transcript in ``transcript``. Otherwise the job is
                still running and must be polled as usual. Note that the server
                caps this value, and that long-held connections may be closed
                early by intermediate proxies.
            format_type: Format of the transcript embedded in the response when
                ``wait`` is used. Ignored otherwise.

        Returns:
            JobDetails object containing the job ID and status, plus the transcript
            if the server returned one.

        Raises:
            BatchError: If job submission fails.
            AuthenticationError: If API key is invalid.
            ConfigurationError: If configuration is invalid.

        Note:
            Submission is not idempotent: if a submission fails after the server
            accepted it (for example a network timeout while waiting), resubmitting
            creates a second billable job. Prefer listing jobs to recover the
            original job over blind retries.

        Examples:
            Basic job submission:
                >>> job = client.submit_job("audio.wav")
                >>> print(f"Job submitted: {job.id}")

            Submit and get the transcript in one call:
                >>> job = client.submit_job("audio.wav", wait=60)
                >>> if job.status == JobStatus.DONE:
                ...     print(job.transcript.transcript_text)
        """
        validate_wait(wait)
        config = build_job_config(config, transcription_config)
        warn_deprecated_operating_point(config)

        config_dict = config.to_dict()
        has_fetch_data = validate_audio_source(audio_file, config_dict)

        try:
            if has_fetch_data:
                multipart_data, filename = build_fetch_data_multipart(config_dict)
                return self._submit(multipart_data, filename, config, parallel_engines, user_id, wait, format_type)

            assert audio_file is not None  # for type checker; validated above
            with prepare_audio_file_sync(audio_file) as (filename, file_data):
                multipart_data = build_file_multipart(config_dict, filename, file_data)
                return self._submit(multipart_data, filename, config, parallel_engines, user_id, wait, format_type)
        except Exception as e:
            if isinstance(e, (AuthenticationError, BatchError)):
                raise
            raise BatchError(f"Job submission failed: {e}") from e

    def get_job_info(self, job_id: str, *, wait: Optional[int] = None) -> JobDetails:
        """
        Get information about a specific job.

        Args:
            job_id: The unique job identifier.
            wait: Seconds to let the server hold the request open until the job
                reaches a terminal state (synchronous transcription, SaaS only).
                The API applies a small default wait when this is omitted.
                Pass 0 to return immediately.

        Returns:
            JobDetails object with current job status and metadata.

        Raises:
            JobExpiredError: If the job's data has expired and been deleted.
            JobError: If job is not found or cannot be retrieved.
            AuthenticationError: If API key is invalid.

        Examples:
            >>> job_info = client.get_job_info("12345")
            >>> print(f"Job status: {job_info.status}")
        """
        return self._request_job_info(job_id, wait=wait, request_timeout=None)

    def _request_job_info(self, job_id: str, *, wait: Optional[int], request_timeout: Optional[float]) -> JobDetails:
        """
        Fetch job info, optionally under a caller-imposed request timeout.

        ``request_timeout`` lets the polling loop keep a single hung request
        from outliving the deadline the caller gave ``wait_for_completion()``.
        """
        try:
            self._logger.debug("Retrieving job info for job_id=%s (wait=%s)", job_id, wait)
            response = self._transport.get(
                f"/jobs/{job_id}",
                params=build_query_params(wait=wait),
                timeout=request_timeout or request_timeout_for_wait(wait, self._conn_config),
            )
            job = response.get("job")
            if job is None:
                raise JobError(f"No job information found for job ID: {job_id}")
            return JobDetails.from_dict(job)
        except Exception as e:
            if isinstance(e, AuthenticationError):
                raise
            if isinstance(e, TransportError) and e.status_code == 410:
                raise JobExpiredError(f"Job {job_id} has expired and is no longer available") from e
            raise JobError(f"Failed to get job info: {e}") from e

    def list_jobs(
        self,
        *,
        limit: Optional[int] = None,
        created_before: Optional[str] = None,
        created_after: Optional[str] = None,
    ) -> list[JobDetails]:
        """
        List jobs with optional filtering.

        Args:
            limit: Maximum number of jobs to return.
            created_before: Only return jobs created before this timestamp.
            created_after: Only return jobs created after this timestamp.

        Returns:
            List of JobDetails objects.

        Raises:
            BatchError: If listing jobs fails.
            AuthenticationError: If API key is invalid.

        Examples:
            >>> jobs = client.list_jobs(limit=10)
            >>> for job in jobs:
            ...     print(f"Job {job.id}: {job.status}")
        """
        params = build_list_jobs_params(limit, created_before, created_after)

        try:
            self._logger.debug("Listing jobs (limit=%s)", limit)
            response = self._transport.get("/jobs", params=params)
            jobs_data = response.get("jobs", [])
            self._logger.debug("Jobs retrieved (%d jobs)", len(jobs_data))
            return [JobDetails.from_dict(job) for job in jobs_data]
        except Exception as e:
            if isinstance(e, AuthenticationError):
                raise
            raise BatchError(f"Failed to list jobs: {e}") from e

    def delete_job(self, job_id: str, *, force: bool = False) -> None:
        """
        Delete a job and its results.

        This method permanently deletes a job and all associated data.
        Use with caution as this operation cannot be undone.

        Args:
            job_id: The unique job identifier.
            force: Delete the job even if it is still running. Without this the
                API refuses to delete a running job.

        Raises:
            JobError: If job cannot be deleted.
            AuthenticationError: If API key is invalid.

        Examples:
            >>> client.delete_job("12345")
        """
        try:
            self._logger.debug("Deleting job_id=%s", job_id)
            self._transport.delete(f"/jobs/{job_id}", params=build_delete_job_params(force))
            self._logger.debug("Job deleted successfully (job_id=%s)", job_id)
        except Exception as e:
            if isinstance(e, AuthenticationError):
                raise
            if isinstance(e, TransportError) and e.status_code == 423:
                raise JobError(f"Job {job_id} is still running; pass force=True to delete it") from e
            raise JobError(f"Failed to delete job: {e}") from e

    def get_transcript(
        self,
        job_id: str,
        *,
        format_type: FormatType = FormatType.JSON,
        wait: Optional[int] = None,
    ) -> Union[Transcript, str]:
        """
        Get the transcript for a completed job.

        Args:
            job_id: The unique job identifier.
            format_type: Output format (FormatType.JSON, FormatType.TXT, FormatType.SRT). Defaults to FormatType.JSON.
            wait: Seconds to let the server hold the request open until the
                transcript is ready (synchronous transcription, SaaS only). The
                The API applies a small default wait when this is omitted.
                Pass 0 to return immediately.

        Returns:
            Transcript object for JSON format, or string for text/SRT formats.

        Raises:
            JobExpiredError: If the job's data has expired and been deleted.
            TranscriptNotReadyError: If the transcript is not available yet (the
                job may still be running, or the job ID may not exist).
            JobError: If transcript cannot be retrieved or job is not complete.
            AuthenticationError: If API key is invalid.

        Examples:
            >>> result = client.get_transcript("12345")
            >>> print(result.transcript_text)

            >>> # Get plain text transcript
            >>> text = client.get_transcript("12345", format_type=FormatType.TXT)
            >>> print(text)
        """
        try:
            self._logger.debug("Retrieving transcript for job_id=%s (format=%s)", job_id, format_type.value)
            response = self._transport.get(
                f"/jobs/{job_id}/transcript",
                params=build_query_params(wait=wait, format_type=format_type),
                timeout=request_timeout_for_wait(wait, self._conn_config),
            )

            if format_type == FormatType.JSON:
                return Transcript.from_dict(response)
            return str(response.get("content", ""))

        except Exception as e:
            if isinstance(e, AuthenticationError):
                raise
            if isinstance(e, TransportError) and e.status_code == 410:
                raise JobExpiredError(f"Transcript for job {job_id} has expired and is no longer available") from e
            if isinstance(e, TransportError) and e.status_code == 404:
                raise TranscriptNotReadyError(
                    f"Transcript for job {job_id} is not available yet; retry the request "
                    "(the job may still be running, or the job ID may not exist)"
                ) from e
            raise JobError(f"Failed to get transcript: {e}") from e

    def wait_for_completion(
        self,
        job_id: str,
        *,
        format_type: FormatType = FormatType.JSON,
        polling_interval: float = 5.0,
        min_polling_interval: float = 0.5,
        timeout: Optional[float] = DEFAULT_TIMEOUT,
    ) -> Union[Transcript, str]:
        """
        Wait for a job to complete and return the result.

        This method polls the job status until it completes (successfully or with error)
        and then retrieves the transcript result.

        Args:
            job_id: The unique job identifier.
            format_type: Output format (FormatType.JSON, FormatType.TXT, FormatType.SRT). Defaults to FormatType.JSON.
            polling_interval: Ceiling in seconds for the time between status
                checks. Polling starts at ``min_polling_interval`` and backs off
                towards this value, so short jobs are caught quickly while
                long-running jobs settle into this interval. Up to 20% jitter is
                applied so that concurrent clients do not synchronise, so an
                individual wait can exceed this by that much. Must be greater than 0.
            min_polling_interval: Initial time in seconds between status checks.
                Must be greater than 0.
            timeout: Maximum time in seconds to wait for completion, one hour
                by default. Pass ``None`` to wait indefinitely.

        Returns:
            Transcript object for JSON format, or string for text/SRT formats.

        Raises:
            TimeoutError: If job doesn't complete within timeout.
            JobError: If job fails or cannot be retrieved.
            AuthenticationError: If API key is invalid.

        Examples:
            >>> job = client.submit_job("audio.wav")
            >>> result = client.wait_for_completion(job.id)
            >>> print(f"Transcript: {result.transcript_text}")
        """
        self._poll_job_status(job_id, polling_interval, min_polling_interval, timeout)
        return self.get_transcript(job_id, format_type=format_type)

    def transcribe(
        self,
        audio_file: Union[str, BinaryIO],
        *,
        config: Optional[JobConfig] = None,
        transcription_config: Optional[TranscriptionConfig] = None,
        format_type: FormatType = FormatType.JSON,
        polling_interval: float = 5.0,
        min_polling_interval: float = 0.5,
        timeout: Optional[float] = DEFAULT_TIMEOUT,
        parallel_engines: Optional[int] = None,
        user_id: Optional[str] = None,
        wait: Optional[int] = None,
    ) -> Union[Transcript, str]:
        """
        Complete transcription workflow: submit job and return the transcript.

        Args:
            audio_file: Path to audio file or file-like object.
            config: Complete job configuration.
            transcription_config: Transcription-specific configuration.
            format_type: Output format (FormatType.JSON, FormatType.TXT, FormatType.SRT). Defaults to FormatType.JSON.
            polling_interval: Ceiling in seconds for the time between status
                checks. Polling starts at ``min_polling_interval`` and backs off
                towards this value, so short jobs are caught quickly while
                long-running jobs settle into this interval. Up to 20% jitter is
                applied so that concurrent clients do not synchronise, so an
                individual wait can exceed this by that much. Must be greater than 0.
            min_polling_interval: Initial time in seconds between status checks.
                Must be greater than 0.
            timeout: Maximum time in seconds to wait for completion, one hour
                by default. Pass ``None`` to wait indefinitely.
            parallel_engines: Optional number of parallel engines to request for this job.
                               Sent as ``{"parallel_engines": N}`` in the ``X-SM-Processing-Data`` header.
                               This only applies when using the container onPrem on http batch mode.
            user_id: Optional user identifier to associate with this job.
                    Sent as ``{"user_id": "..."}`` in the ``X-SM-Processing-Data`` header.
                    This only applies when using the container onPrem on http batch mode.
            wait: Seconds to let the server hold the submit request open waiting
                for the transcript (synchronous transcription, SaaS only). Short
                audio then needs only one round trip; anything still running when
                the wait elapses falls back to polling.

        Returns:
            Transcript object for JSON format, or string for text/SRT formats.

        Raises:
            BatchError: If job submission fails.
            TimeoutError: If job doesn't complete within timeout.
            JobError: If job fails.
            AuthenticationError: If API key is invalid.

        Examples:
            >>> result = client.transcribe("audio.wav")
            >>> print(f"Transcript: {result.transcript_text}")

            >>> # One round trip for short audio
            >>> result = client.transcribe("audio.wav", wait=60)
        """
        started_at = time.monotonic()

        # The server-side wait must not outlive the caller's own timeout.
        wait = clamp_wait(wait, timeout)

        job = self.submit_job(
            audio_file,
            config=config,
            transcription_config=transcription_config,
            parallel_engines=parallel_engines,
            user_id=user_id,
            wait=wait,
            format_type=format_type,
        )

        if job.status == JobStatus.DONE:
            if job.transcript is not None:
                self._logger.info("Transcription completed during submit (job_id=%s)", job.id)
                return job.transcript
            return self.get_transcript(job.id, format_type=format_type)

        remaining = None if timeout is None else max(0.0, timeout - (time.monotonic() - started_at))

        self._logger.debug("Waiting for job completion (job_id=%s)", job.id)
        result = self.wait_for_completion(
            job.id,
            format_type=format_type,
            polling_interval=polling_interval,
            min_polling_interval=min_polling_interval,
            timeout=remaining,
        )
        self._logger.info("Transcription job completed successfully (job_id=%s)", job.id)
        return result

    def close(self) -> None:
        """
        Close the client and cleanup all resources.

        This method is safe to call multiple times and will handle cleanup
        gracefully even if errors occur during the process.

        Examples:
            >>> client = Client(api_key="key")
            >>> try:
            ...     result = client.transcribe("audio.wav")
            >>> finally:
            ...     client.close()
        """
        try:
            self._transport.close()
        except Exception:
            pass  # Best effort cleanup

    def _poll_job_status(
        self, job_id: str, polling_interval: float, min_polling_interval: float, timeout: Optional[float]
    ) -> None:
        """Poll job status until completion, failure or timeout."""
        self._logger.debug(
            "Starting job status polling for job_id=%s (min_interval=%.1fs, max_interval=%.1fs)",
            job_id,
            min_polling_interval,
            polling_interval,
        )
        started_at = time.monotonic()
        deadline = None if timeout is None else started_at + timeout
        interval = PollingInterval(min_polling_interval, polling_interval)
        poll_count = 0
        last_log_time = 0.0
        transient_failures = 0

        while True:
            poll_count += 1
            request_timeout = None
            if deadline is not None:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError(f"Job {job_id} did not complete within {timeout} seconds")
                # Without this a single hung request could outlive the caller's
                # deadline by a whole operation timeout.
                request_timeout = min(remaining, self._conn_config.operation_timeout)

            try:
                job_info = self._request_job_info(job_id, wait=None, request_timeout=request_timeout)
            except Exception as e:
                if not is_transient_poll_error(e):
                    raise
                if deadline is not None and time.monotonic() >= deadline:
                    # The request was cut short by the caller's own deadline
                    # (the server holds a status request for an unspecified
                    # time), so report the timeout rather than a transport fault.
                    raise TimeoutError(f"Job {job_id} did not complete within {timeout} seconds") from e
                transient_failures += 1
                if transient_failures > MAX_TRANSIENT_POLL_FAILURES:
                    raise JobError(
                        f"Job {job_id} status could not be read after "
                        f"{transient_failures} consecutive failures: {e}"
                    ) from e
                self._logger.warning(
                    "Job status poll failed, retrying (job_id=%s, failure=%d/%d): %s",
                    job_id,
                    transient_failures,
                    MAX_TRANSIENT_POLL_FAILURES,
                    e,
                )
            else:
                transient_failures = 0

                if job_info.status == JobStatus.DONE:
                    self._logger.info("Job completed (job_id=%s, polls=%d)", job_id, poll_count)
                    self._logger.debug(
                        "Job turnaround time: %.2fs (job_id=%s, polls=%d)",
                        time.monotonic() - started_at,
                        job_id,
                        poll_count,
                    )
                    return
                elif is_job_active(job_info.status):
                    current_time = time.monotonic()
                    if current_time - last_log_time >= 30.0:
                        self._logger.debug("Job still running (job_id=%s, polls=%d)", job_id, poll_count)
                        last_log_time = current_time
                else:
                    self._logger.warning("Job did not succeed (job_id=%s, status=%s)", job_id, job_info.status.value)
                    raise_for_failed_status(job_id, job_info.status)
                    raise JobError(f"Job {job_id} has unexpected status: {job_info.status.value}")

            sleep_for = interval.next()
            if deadline is not None:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError(f"Job {job_id} did not complete within {timeout} seconds")
                sleep_for = min(sleep_for, remaining)
            time.sleep(sleep_for)

    def _submit(
        self,
        multipart_data: dict[str, Any],
        filename: str,
        config: JobConfig,
        parallel_engines: Optional[int],
        user_id: Optional[str],
        wait: Optional[int],
        format_type: FormatType,
    ) -> JobDetails:
        """Submit the job and build its JobDetails."""
        response = self._transport.post(
            "/jobs",
            multipart_data=multipart_data,
            extra_headers=build_processing_data_header(parallel_engines, user_id),
            params=build_submit_query_params(wait, format_type),
            timeout=request_timeout_for_wait(wait, self._conn_config),
        )
        job = job_details_from_submit_response(response, config, filename, format_type)
        self._logger.debug("Job submitted successfully (job_id=%s, filename=%s)", job.id, filename)
        return job
