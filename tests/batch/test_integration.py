"""
Integration tests against the real Speechmatics Batch API.

These verify the things mocks cannot: the actual wire format of a synchronous
transcription response, the real status values, and the behaviour of a
long-held connection. Synchronous transcription is SaaS-only, so these are
skipped against on-premises endpoints.

Run with:

    SPEECHMATICS_API_KEY=... pytest tests/batch -m integration

They submit real, billable jobs, so they only run when an API key is set.
"""

import os
from pathlib import Path

import pytest

from speechmatics.batch import AsyncClient
from speechmatics.batch import Client
from speechmatics.batch import FormatType
from speechmatics.batch import JobError
from speechmatics.batch import JobStatus
from speechmatics.batch import Transcript
from speechmatics.batch import TranscriptNotReadyError
from speechmatics.batch._common import api_format_value
from speechmatics.batch._common import is_job_active

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not os.environ.get("SPEECHMATICS_API_KEY"),
        reason="SPEECHMATICS_API_KEY not set",
    ),
]

# Generous, because a real job is being transcribed.
WAIT_SECONDS = 60


@pytest.fixture(scope="module")
def audio_file() -> str:
    """
    Real speech, so the transcript is non-empty.

    Silence transcribes to no text at all, and the API omits an empty
    transcript, which makes "was a transcript embedded?" unanswerable.
    """
    path = Path(__file__).resolve().parents[2] / "examples" / "example1.wav"
    if not path.exists():
        pytest.skip(f"sample audio not found at {path}")
    return str(path)


@pytest.fixture
def client():
    with Client() as sync_client:
        yield sync_client


class TestSynchronousTranscriptionWireFormat:
    """Pin the response shape this SDK parses, against the live API."""

    def test_embedded_json_transcript_key(self, client, audio_file):
        """The transcript must arrive under the 'json-v2' key, not merged or elsewhere."""
        job = client.submit_job(audio_file, wait=WAIT_SECONDS)

        if job.status != JobStatus.DONE:
            pytest.skip(f"Server did not finish within the wait window (status: {job.status.value})")

        assert isinstance(
            job.transcript, Transcript
        ), "Embedded json-v2 transcript was not parsed; the response shape may have changed"

    def test_embedded_txt_transcript_key(self, client, audio_file):
        job = client.submit_job(audio_file, wait=WAIT_SECONDS, format_type=FormatType.TXT)

        if job.status != JobStatus.DONE:
            pytest.skip(f"Server did not finish within the wait window (status: {job.status.value})")
        assert isinstance(
            job.transcript, str
        ), f"expected a txt transcript under the {api_format_value(FormatType.TXT)!r} key, got None"
        assert job.transcript.strip()

    def test_raw_response_shape_is_what_the_docs_describe(self, client, audio_file):
        """Inspect the untouched response body, so a shape change is visible here first."""
        from speechmatics.batch._common import build_file_multipart
        from speechmatics.batch._helpers import prepare_audio_file_sync

        config = {"type": "transcription", "transcription_config": {"language": "en"}}
        with prepare_audio_file_sync(audio_file) as (filename, data):
            response = client._transport.post(
                "/jobs",
                multipart_data=build_file_multipart(config, filename, data),
                params={"wait": str(WAIT_SECONDS)},
                timeout=WAIT_SECONDS + 60,
            )

        assert "id" in response and "status" in response
        if response["status"] == JobStatus.DONE.value:
            key = api_format_value(FormatType.JSON)
            assert key in response, f"expected transcript under {key!r}, got keys {sorted(response)}"
            assert isinstance(response[key], dict)


class TestSynchronousTranscriptionFlow:
    def test_transcribe_in_one_call(self, client, audio_file):
        result = client.transcribe(audio_file, wait=WAIT_SECONDS, format_type=FormatType.TXT)
        assert isinstance(result, str)

    def test_transcribe_without_wait_still_polls(self, client, audio_file):
        result = client.transcribe(audio_file, polling_interval=2.0, timeout=300.0)
        assert isinstance(result, Transcript)

    def test_transcript_before_ready_raises_not_ready(self, client, audio_file):
        """wait=0 should not have a transcript yet, and must raise the typed error."""
        job = client.submit_job(audio_file, wait=0)
        try:
            with pytest.raises(TranscriptNotReadyError):
                client.get_transcript(job.id, wait=0)
        finally:
            client.delete_job(job.id, force=True)

    def test_wait_zero_returns_immediately(self, client, audio_file):
        job = client.submit_job(audio_file, wait=0)
        try:
            assert is_job_active(job.status)
            assert job.transcript is None
        finally:
            client.delete_job(job.id, force=True)

    @pytest.mark.asyncio
    async def test_async_client_matches_sync(self, audio_file):
        async with AsyncClient() as async_client:
            result = await async_client.transcribe(audio_file, wait=WAIT_SECONDS, format_type=FormatType.TXT)
        assert isinstance(result, str)


class TestDeletingRunningJobs:
    def test_running_job_needs_force(self, client, audio_file):
        """The API answers HTTP 423 for a running job unless force is passed."""
        job = client.submit_job(audio_file, wait=0)
        try:
            with pytest.raises(JobError, match="pass force=True"):
                client.delete_job(job.id)
        finally:
            client.delete_job(job.id, force=True)

    def test_force_deletes_a_running_job(self, client, audio_file):
        job = client.submit_job(audio_file, wait=0)
        client.delete_job(job.id, force=True)
