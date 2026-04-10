"""Unit tests for AsyncClient.submit_job, focusing on the parallel engines and user_id features."""

import json
from io import BytesIO
from unittest.mock import AsyncMock
from unittest.mock import MagicMock
from unittest.mock import patch

from typing import Optional

import pytest

from speechmatics.batch import AsyncClient
from speechmatics.batch import JobConfig
from speechmatics.batch import JobStatus
from speechmatics.batch import JobType
from speechmatics.batch import TranscriptionConfig
from speechmatics.batch import PROCESSING_DATA_HEADER


def _make_client(api_key: str = "test-key") -> AsyncClient:
    return AsyncClient(api_key=api_key)


def _job_response(job_id: str = "job-123") -> dict:
    return {"id": job_id, "created_at": "2024-01-01T00:00:00Z"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _captured_extra_headers(mock_post: AsyncMock) -> Optional[dict]:
    """Return the extra_headers kwarg from the first call to transport.post."""
    _, kwargs = mock_post.call_args
    return kwargs.get("extra_headers")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestRequestedParallelHeader:
    """X-SM-Processing-Data header is set correctly based on parallel_engines."""

    @pytest.mark.asyncio
    async def test_header_sent_when_parallel_engines_provided(self):
        client = _make_client()
        audio = BytesIO(b"fake-audio")

        with patch.object(client._transport, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = _job_response()
            await client.submit_job(audio, parallel_engines=4)

        extra_headers = _captured_extra_headers(mock_post)
        assert extra_headers is not None
        assert PROCESSING_DATA_HEADER in extra_headers
        payload = extra_headers[PROCESSING_DATA_HEADER]
        assert payload == {"parallel_engines": 4}

    @pytest.mark.asyncio
    async def test_header_not_sent_when_parallel_engines_is_none(self):
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
            await client.submit_job(audio, parallel_engines=8)

        extra_headers = _captured_extra_headers(mock_post)
        # Must be parseable JSON
        assert extra_headers is not None
        parsed = extra_headers[PROCESSING_DATA_HEADER]
        assert parsed["parallel_engines"] == 8

    @pytest.mark.asyncio
    async def test_parallel_engines_one(self):
        client = _make_client()
        audio = BytesIO(b"fake-audio")

        with patch.object(client._transport, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = _job_response()
            await client.submit_job(audio, parallel_engines=1)

        extra_headers = _captured_extra_headers(mock_post)
        assert extra_headers is not None
        payload = extra_headers[PROCESSING_DATA_HEADER]
        assert payload["parallel_engines"] == 1

    @pytest.mark.asyncio
    async def test_header_sent_with_fetch_data_config(self):
        """parallel_engines works with fetch_data submissions too."""
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
                await client.submit_job(None, config=config, parallel_engines=2)

        extra_headers = _captured_extra_headers(mock_post)
        assert extra_headers is not None
        payload = extra_headers[PROCESSING_DATA_HEADER]
        assert payload == {"parallel_engines": 2}


class TestUserIdHeader:
    """X-SM-Processing-Data header is set correctly based on user_id."""

    @pytest.mark.asyncio
    async def test_header_sent_when_user_id_provided(self):
        client = _make_client()
        audio = BytesIO(b"fake-audio")

        with patch.object(client._transport, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = _job_response()
            await client.submit_job(audio, user_id="user-abc")

        extra_headers = _captured_extra_headers(mock_post)
        assert extra_headers is not None
        assert PROCESSING_DATA_HEADER in extra_headers
        payload = extra_headers[PROCESSING_DATA_HEADER]
        assert payload == {"user_id": "user-abc"}

    @pytest.mark.asyncio
    async def test_header_not_sent_when_user_id_is_none(self):
        client = _make_client()
        audio = BytesIO(b"fake-audio")

        with patch.object(client._transport, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = _job_response()
            await client.submit_job(audio)

        extra_headers = _captured_extra_headers(mock_post)
        assert extra_headers is None

    @pytest.mark.asyncio
    async def test_user_id_and_parallel_engines_sent_together(self):
        client = _make_client()
        audio = BytesIO(b"fake-audio")

        with patch.object(client._transport, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = _job_response()
            await client.submit_job(audio, parallel_engines=4, user_id="user-xyz")

        extra_headers = _captured_extra_headers(mock_post)
        assert extra_headers is not None
        payload = extra_headers[PROCESSING_DATA_HEADER]
        assert payload == {"parallel_engines": 4, "user_id": "user-xyz"}

    @pytest.mark.asyncio
    async def test_user_id_does_not_appear_when_only_parallel_engines_set(self):
        client = _make_client()
        audio = BytesIO(b"fake-audio")

        with patch.object(client._transport, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = _job_response()
            await client.submit_job(audio, parallel_engines=2)

        payload = _captured_extra_headers(mock_post)[PROCESSING_DATA_HEADER]
        assert "user_id" not in payload

    @pytest.mark.asyncio
    async def test_parallel_engines_does_not_appear_when_only_user_id_set(self):
        client = _make_client()
        audio = BytesIO(b"fake-audio")

        with patch.object(client._transport, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = _job_response()
            await client.submit_job(audio, user_id="u1")

        payload = _captured_extra_headers(mock_post)[PROCESSING_DATA_HEADER]
        assert "parallel_engines" not in payload

    @pytest.mark.asyncio
    async def test_user_id_forwarded_from_transcribe(self):
        client = _make_client()
        audio = BytesIO(b"fake-audio")

        with patch.object(client._transport, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = _job_response()
            with patch.object(client, "wait_for_completion", new_callable=AsyncMock) as mock_wait:
                mock_wait.return_value = MagicMock()
                await client.transcribe(audio, user_id="transcribe-user")

        extra_headers = _captured_extra_headers(mock_post)
        assert extra_headers is not None
        assert extra_headers[PROCESSING_DATA_HEADER]["user_id"] == "transcribe-user"


class TestSubmitJobReturnValue:
    """submit_job still returns the correct JobDetails regardless of parallel_engines."""

    @pytest.mark.asyncio
    async def test_returns_job_details_with_correct_id(self):
        client = _make_client()
        audio = BytesIO(b"fake-audio")

        with patch.object(client._transport, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = _job_response("abc-456")
            job = await client.submit_job(audio, parallel_engines=3)

        assert job.id == "abc-456"
        assert job.status == JobStatus.RUNNING

    @pytest.mark.asyncio
    async def test_post_called_with_jobs_path(self):
        client = _make_client()
        audio = BytesIO(b"fake-audio")

        with patch.object(client._transport, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = _job_response()
            await client.submit_job(audio, parallel_engines=2)

        args, _ = mock_post.call_args
        assert args[0] == "/jobs"
