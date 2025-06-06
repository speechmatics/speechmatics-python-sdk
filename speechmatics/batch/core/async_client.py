"""
Asynchronous client for Speechmatics batch transcription.

This module provides the main AsyncClient class that handles batch
speech-to-text transcription using the Speechmatics Batch API.
"""

from __future__ import annotations

import asyncio
import os
import uuid
from typing import Any
from typing import BinaryIO
from typing import Optional
from typing import Union

from .exceptions import AuthenticationError
from .exceptions import BatchError
from .exceptions import ConfigurationError
from .exceptions import JobError
from .exceptions import TimeoutError
from .helpers import prepare_audio_file
from .logging import get_logger
from .models import ConnectionConfig
from .models import FormatType
from .models import JobConfig
from .models import JobDetails
from .models import JobStatus
from .models import JobType
from .models import Transcript
from .models import TranscriptionConfig
from .transport import Transport


class AsyncClient:
    """
    Asynchronous client for Speechmatics batch speech transcription.

    This client provides a full-featured async interface to the Speechmatics Batch API,
    supporting job submission, monitoring, and result retrieval with comprehensive
    error management. It properly implements the Speechmatics REST API.

    The client handles the complete batch transcription workflow:
    1. Job submission with audio file and configuration
    2. Job status monitoring (with polling helpers)
    3. Result retrieval when transcription is complete
    4. Proper cleanup and error handling

    Args:
        api_key: Speechmatics API key for authentication. If not provided,
                uses the SPEECHMATICS_API_KEY environment variable.
        url: REST API endpoint URL. If not provided, uses SPEECHMATICS_BATCH_URL
             environment variable or defaults to production endpoint.
        conn_config: Complete connection configuration object. If provided, overrides
               api_key and url parameters.

    Raises:
        ConfigurationError: If required configuration is missing or invalid.

    Examples:
        Basic usage:
            >>> async with AsyncClient(api_key="your-key") as client:
            ...     job = await client.submit_job("audio.wav")
            ...     result = await client.wait_for_completion(job.id)
            ...     print(result.transcript)

        With custom configuration:
            >>> config = ConnectionConfig(
            ...     url="https://asr.api.speechmatics.com/v2",
            ...     api_key="your-key",
            ... )
            >>> async with AsyncClient(conn_config=config) as client:
            ...     # Use client with custom settings
            ...     pass

        Manual resource management:
            >>> client = AsyncClient(api_key="your-key")
            >>> try:
            ...     job = await client.submit_job("audio.wav")
            ...     result = await client.wait_for_completion(job.id)
            ... finally:
            ...     await client.close()
    """

    def __init__(
        self,
        *,
        api_key: Optional[str] = None,
        url: Optional[str] = None,
        conn_config: Optional[ConnectionConfig] = None,
    ) -> None:
        """
        Initialize the AsyncClient.

        Args:
            api_key: Speechmatics API key. If None, uses SPEECHMATICS_API_KEY env var.
            url: REST API endpoint URL. If None, uses SPEECHMATICS_BATCH_URL env var
                 or defaults to production endpoint.
            conn_config: Complete connection configuration. Overrides api_key and url.

        Raises:
            ConfigurationError: If API key is not provided and not found in environment.
        """
        # Set up configuration
        if conn_config:
            self._conn_config = conn_config
        else:
            api_key = api_key or os.environ.get("SPEECHMATICS_API_KEY")
            if not api_key:
                raise ConfigurationError("API key required: provide api_key parameter or set SPEECHMATICS_API_KEY")

            final_url = url or os.environ.get("SPEECHMATICS_BATCH_URL") or "https://asr.api.speechmatics.com/v2"
            self._conn_config = ConnectionConfig(url=final_url, api_key=api_key)

        self._request_id = str(uuid.uuid4())
        self._transport = Transport(self._conn_config, self._request_id)
        self._logger = get_logger(__name__, self._request_id)

    async def __aenter__(self) -> AsyncClient:
        """
        Async context manager entry.

        Returns:
            Self for use in async with statements.

        Examples:
            >>> async with AsyncClient(api_key="key") as client:
            ...     job = await client.submit_job("audio.wav")
        """
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """
        Async context manager exit with automatic cleanup.

        Ensures all resources are properly cleaned up when exiting the
        async context manager, including closing HTTP connections.

        Args:
            exc_type: Exception type if an exception occurred.
            exc_val: Exception value if an exception occurred.
            exc_tb: Exception traceback if an exception occurred.
        """
        await self.close()

    async def submit_job(
        self,
        audio_file: Union[str, BinaryIO],
        *,
        config: Optional[JobConfig] = None,
        transcription_config: Optional[TranscriptionConfig] = None,
    ) -> JobDetails:
        """
        Submit a new transcription job.

        This method uploads an audio file and submits it for batch transcription
        with the specified configuration. The job will be queued and processed
        asynchronously on the server.

        Args:
            audio_file: Path to audio file or file-like object containing audio data.
            config: Complete job configuration. If not provided, uses transcription_config
                   to build a basic job configuration.
            transcription_config: Transcription-specific configuration. Used if config
                                is not provided.

        Returns:
            JobDetails object containing the job ID and initial status.

        Raises:
            BatchError: If job submission fails.
            AuthenticationError: If API key is invalid.
            ConfigurationError: If configuration is invalid.

        Examples:
            Basic job submission:
                >>> job = await client.submit_job("audio.wav")
                >>> print(f"Job submitted: {job.id}")

            With custom configuration:
                >>> config = JobConfig(
                ...     transcription_config=TranscriptionConfig(
                ...         language="es",
                ...         enable_entities=True
                ...     )
                ... )
                >>> job = await client.submit_job("audio.wav", config=config)
        """
        # Prepare job configuration
        if config is None:
            transcription_config = transcription_config or TranscriptionConfig()
            config = JobConfig(type=JobType.TRANSCRIPTION, transcription_config=transcription_config)

        # Prepare file data using async context manager
        try:
            async with prepare_audio_file(audio_file) as (filename, file_data):
                # Prepare multipart form data
                multipart_data = {
                    "config": config.to_dict(),
                    "data_file": (filename, file_data, "audio/wav"),
                }

                response = await self._transport.post("/jobs", multipart_data=multipart_data)

                # Extract job info from response
                job_id = response.get("id")
                if not job_id:
                    raise BatchError("No job ID returned from server")

                self._logger.info("job_submitted", job_id=job_id)

                return JobDetails(
                    id=job_id,
                    status=JobStatus.RUNNING,  # Assume running initially
                    created_at=response.get("created_at", ""),
                    data_name=filename,
                    config=config,
                )

        except Exception as e:
            if isinstance(e, (AuthenticationError, BatchError)):
                raise
            raise BatchError(f"Failed to submit job: {e}") from e

    async def get_job_info(self, job_id: str) -> JobDetails:
        """
        Get information about a specific job.

        This method retrieves the current status and metadata for a job.

        Args:
            job_id: The unique job identifier.

        Returns:
            JobDetails object with current job status and metadata.

        Raises:
            JobError: If job is not found or cannot be retrieved.
            AuthenticationError: If API key is invalid.

        Examples:
            >>> job_info = await client.get_job_info("12345")
            >>> print(f"Job status: {job_info.status}")
        """
        try:
            response = await self._transport.get(f"/jobs/{job_id}")
            job = response.get("job")
            if job is None:
                raise JobError(f"No job information found for job ID: {job_id}")
            return JobDetails.from_dict(job)
        except Exception as e:
            if isinstance(e, AuthenticationError):
                raise
            raise JobError(f"Failed to get job info: {e}") from e

    async def list_jobs(
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
            >>> jobs = await client.list_jobs(limit=10)
            >>> for job in jobs:
            ...     print(f"Job {job.id}: {job.status}")
        """
        params = {}
        if limit is not None:
            params["limit"] = str(limit)
        if created_before:
            params["created_before"] = created_before
        if created_after:
            params["created_after"] = created_after

        try:
            response = await self._transport.get("/jobs", params=params or None)
            jobs_data = response.get("jobs", [])
            return [JobDetails.from_dict(job) for job in jobs_data]
        except Exception as e:
            if isinstance(e, AuthenticationError):
                raise
            raise BatchError(f"Failed to list jobs: {e}") from e

    async def delete_job(self, job_id: str) -> None:
        """
        Delete a job and its results.

        This method permanently deletes a job and all associated data.
        Use with caution as this operation cannot be undone.

        Args:
            job_id: The unique job identifier.

        Raises:
            JobError: If job cannot be deleted.
            AuthenticationError: If API key is invalid.

        Examples:
            >>> await client.delete_job("12345")
        """
        try:
            await self._transport.delete(f"/jobs/{job_id}")
            self._logger.info("job_deleted", job_id=job_id)
        except Exception as e:
            if isinstance(e, AuthenticationError):
                raise
            raise JobError(f"Failed to delete job: {e}") from e

    async def get_transcript(self, job_id: str, *, format_type: FormatType = FormatType.JSON) -> Union[Transcript, str]:
        """
        Get the transcript for a completed job.

        Args:
            job_id: The unique job identifier.
            format_type: Output format (FormatType.JSON, FormatType.TXT, FormatType.SRT). Defaults to FormatType.JSON.

        Returns:
            Transcript object for JSON format, or string for text/SRT formats.

        Raises:
            JobError: If transcript cannot be retrieved or job is not complete.
            AuthenticationError: If API key is invalid.

        Examples:
            >>> result = await client.get_transcript("12345")
            >>> print(result.transcript)

            >>> # Get plain text transcript
            >>> text = await client.get_transcript("12345", format_type=FormatType.TXT)
            >>> print(text)
        """
        params = {"format": format_type.value} if format_type != FormatType.JSON else None

        try:
            response = await self._transport.get(f"/jobs/{job_id}/transcript", params=params)

            if format_type == FormatType.JSON:
                return Transcript.from_dict(response)
            else:
                # Return plain text for other formats
                return response.get("content", "")  # type: ignore[no-any-return]

        except Exception as e:
            if isinstance(e, AuthenticationError):
                raise
            raise JobError(f"Failed to get transcript: {e}") from e

    async def _poll_job_status(self, job_id: str, polling_interval: float) -> None:
        """Poll job status until completion or failure."""
        while True:
            job_info = await self.get_job_info(job_id)

            if job_info.status == JobStatus.DONE:
                return
            elif job_info.status == JobStatus.REJECTED:
                raise JobError(f"Job {job_id} was rejected")
            elif job_info.status == JobStatus.RUNNING:
                self._logger.debug("job_polling", job_id=job_id, status=job_info.status)
                await asyncio.sleep(polling_interval)
            else:
                raise JobError(f"Job {job_id} has unknown status: {job_info.status}")

    async def wait_for_completion(
        self,
        job_id: str,
        *,
        format_type: FormatType = FormatType.JSON,
        polling_interval: float = 5.0,
        timeout: Optional[float] = None,
    ) -> Union[Transcript, str]:
        """
        Wait for a job to complete and return the result.

        This method polls the job status until it completes (successfully or with error)
        and then retrieves the transcript result.

        Args:
            job_id: The unique job identifier.
            format_type: Output format (FormatType.JSON, FormatType.TXT, FormatType.SRT). Defaults to FormatType.JSON.
            polling_interval: Time in seconds between status checks.
            timeout: Maximum time in seconds to wait for completion.

        Returns:
            Transcript object for JSON format, or string for text/SRT formats.

        Raises:
            TimeoutError: If job doesn't complete within timeout.
            JobError: If job fails or cannot be retrieved.
            AuthenticationError: If API key is invalid.

        Examples:
            >>> job = await client.submit_job("audio.wav")
            >>> result = await client.wait_for_completion(job.id)
            >>> print(f"Transcript: {result.transcript}")

            >>> # With custom timeout and format
            >>> result = await client.wait_for_completion(
            ...     job.id,
            ...     format_type=FormatType.TXT,
            ...     polling_interval=2.0,
            ...     timeout=300.0
            ... )
        """
        try:
            await asyncio.wait_for(self._poll_job_status(job_id, polling_interval), timeout=timeout)

            return await self.get_transcript(job_id, format_type=format_type)

        except asyncio.TimeoutError:
            raise TimeoutError(f"Job {job_id} did not complete within {timeout} seconds") from None

    async def transcribe(
        self,
        audio_file: Union[str, BinaryIO],
        *,
        config: Optional[JobConfig] = None,
        transcription_config: Optional[TranscriptionConfig] = None,
        polling_interval: float = 5.0,
        timeout: Optional[float] = None,
    ) -> Union[Transcript, str]:
        """
        Complete transcription workflow: submit job and wait for completion.

        This is a convenience method that combines job submission and waiting
        for completion in a single call.

        Args:
            audio_file: Path to audio file or file-like object.
            config: Complete job configuration.
            transcription_config: Transcription-specific configuration.
            polling_interval: Time in seconds between status checks.
            timeout: Maximum time in seconds to wait for completion.

        Returns:
            Transcript object containing the transcript and metadata.

        Raises:
            BatchError: If job submission fails.
            TimeoutError: If job doesn't complete within timeout.
            JobError: If job fails.
            AuthenticationError: If API key is invalid.

        Examples:
            >>> result = await client.transcribe("audio.wav")
            >>> print(f"Transcript: {result.transcript}")

            >>> # With custom configuration
            >>> config = TranscriptionConfig(language="es", enable_entities=True)
            >>> result = await client.transcribe(
            ...     "audio.wav",
            ...     transcription_config=config,
            ...     timeout=300.0
            ... )
        """
        # Submit the job
        job = await self.submit_job(
            audio_file,
            config=config,
            transcription_config=transcription_config,
        )

        # Wait for completion and return result
        return await self.wait_for_completion(
            job.id,
            polling_interval=polling_interval,
            timeout=timeout,
        )

    async def close(self) -> None:
        """
        Close the client and cleanup all resources.

        This method ensures proper cleanup of all client resources including
        closing HTTP connections and sessions.

        This method is safe to call multiple times and will handle cleanup
        gracefully even if errors occur during the process.

        Examples:
            >>> client = AsyncClient(api_key="key")
            >>> try:
            ...     result = await client.transcribe("audio.wav")
            >>> finally:
            ...     await client.close()
        """
        try:
            await self._transport.close()
        except Exception:
            pass  # Best effort cleanup
