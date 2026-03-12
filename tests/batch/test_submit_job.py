"""Unit tests for AsyncClient.submit_job, focusing on the requested_parallel feature."""

import json
from io import BytesIO
from unittest.mock import AsyncMock
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest

from speechmatics.batch import AsyncClient
from speechmatics.batch import JobConfig
from speechmatics.batch import JobStatus
from speechmatics.batch import JobType
from speechmatics.batch import TranscriptionConfig


def _make_client(api_key: str = "test-key") -> AsyncClient:
    return AsyncClient(api_key=api_key)


def _job_response(job_id: str = "job-123") -> dict:
    return {"id": job_id, "created_at": "2024-01-01T00:00:00Z"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _captured_extra_headers(mock_post: AsyncMock) -> dict | None:
    """Return the extra_headers kwarg from the first call to transport.post."""
    _, kwargs = mock_post.call_args
    return kwargs.get("extra_headers")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestRequestedParallelHeader:
    """X-SM-Processing-Data header is set correctly based on requested_parallel."""

    @pytest.mark.asyncio
    async def test_header_sent_when_requested_parallel_provided(self):
        client = _make_client()
        audio = BytesIO(b"fake-audio")

        with patch.object(client._transport, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = _job_response()
            await client.submit_job(audio, requested_parallel=4)

        extra_headers = _captured_extra_headers(mock_post)
        assert extra_headers is not None
        assert "X-SM-Processing-Data" in extra_headers
        payload = extra_headers["X-SM-Processing-Data"]
        assert payload == {"requested_parallel": 4}

    @pytest.mark.asyncio
    async def test_header_not_sent_when_requested_parallel_is_none(self):
        client = _make_client()
        audio = BytesIO(b"fake-audio")

        with patch.object(client._transport, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = _job_response()
            await client.submit_job(audio)

        extra_headers = _captured_extra_headers(mock_post)
        assert extra_headers is None

    @pytest.mark.asyncio
    async def test_header_value_is_valid_json(self):
        client = _make_client()
        audio = BytesIO(b"fake-audio")

        with patch.object(client._transport, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = _job_response()
            await client.submit_job(audio, requested_parallel=8)

        extra_headers = _captured_extra_headers(mock_post)
        # Must be parseable JSON
        assert extra_headers is not None
        parsed = extra_headers["X-SM-Processing-Data"]
        assert parsed["requested_parallel"] == 8

    @pytest.mark.asyncio
    async def test_requested_parallel_one(self):
        client = _make_client()
        audio = BytesIO(b"fake-audio")

        with patch.object(client._transport, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = _job_response()
            await client.submit_job(audio, requested_parallel=1)

        extra_headers = _captured_extra_headers(mock_post)
        assert extra_headers is not None
        payload = extra_headers["X-SM-Processing-Data"]
        assert payload["requested_parallel"] == 1

    @pytest.mark.asyncio
    async def test_header_sent_with_fetch_data_config(self):
        """requested_parallel works with fetch_data submissions too."""
        client = _make_client()
        config = JobConfig(
            type=JobType.TRANSCRIPTION,
            fetch_data=MagicMock(url="https://example.com/audio.wav"),
            transcription_config=TranscriptionConfig(language="en"),
        )
        # Patch to_dict so fetch_data key is present
        config_dict = {
            "type": "transcription",
            "fetch_data": {"url": "https://example.com/audio.wav"},
            "transcription_config": {"language": "en"},
        }
        with patch.object(config, "to_dict", return_value=config_dict):
            with patch.object(client._transport, "post", new_callable=AsyncMock) as mock_post:
                mock_post.return_value = _job_response()
                await client.submit_job(None, config=config, requested_parallel=2)

        extra_headers = _captured_extra_headers(mock_post)
        assert extra_headers is not None
        payload = extra_headers["X-SM-Processing-Data"]
        assert payload == {"requested_parallel": 2}


class TestSubmitJobReturnValue:
    """submit_job still returns the correct JobDetails regardless of requested_parallel."""

    @pytest.mark.asyncio
    async def test_returns_job_details_with_correct_id(self):
        client = _make_client()
        audio = BytesIO(b"fake-audio")

        with patch.object(client._transport, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = _job_response("abc-456")
            job = await client.submit_job(audio, requested_parallel=3)

        assert job.id == "abc-456"
        assert job.status == JobStatus.RUNNING

    @pytest.mark.asyncio
    async def test_post_called_with_jobs_path(self):
        client = _make_client()
        audio = BytesIO(b"fake-audio")

        with patch.object(client._transport, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = _job_response()
            await client.submit_job(audio, requested_parallel=2)

        args, _ = mock_post.call_args
        assert args[0] == "/jobs"
