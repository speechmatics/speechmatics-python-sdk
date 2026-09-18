"""
Behavioural parity between AsyncClient and Client.

Every test here runs against both clients through a thin adapter, so a
behaviour that exists in one implementation and not the other fails the build.
This is the guardrail for the two clients being separate implementations.
"""

import asyncio
import inspect
from io import BytesIO
from unittest.mock import AsyncMock
from unittest.mock import patch

import pytest

from speechmatics.batch import AsyncClient
from speechmatics.batch import AuthenticationError
from speechmatics.batch import BatchError
from speechmatics.batch import Client
from speechmatics.batch import FetchData
from speechmatics.batch import FormatType
from speechmatics.batch import JobConfig
from speechmatics.batch import JobError
from speechmatics.batch import JobStatus
from speechmatics.batch import JobType
from speechmatics.batch import TimeoutError as SMTimeoutError
from speechmatics.batch import Transcript
from speechmatics.batch import TranscriptNotReadyError
from speechmatics.batch import TransportError


def _transcript_payload(text: str = "Hello") -> dict:
    return {
        "format": "2.9",
        "job": {"id": "job-1", "created_at": "t", "data_name": "audio.wav"},
        "metadata": {"created_at": "t", "type": "transcription"},
        "results": [
            {
                "type": "word",
                "start_time": 0.0,
                "end_time": 0.5,
                "alternatives": [{"content": text, "confidence": 0.9, "language": "en"}],
            }
        ],
    }


class ClientUnderTest:
    """Drives either client with one blocking interface."""

    def __init__(self, kind: str):
        self.kind = kind
        self.is_async = kind == "async"
        self.client = AsyncClient(api_key="test-key") if self.is_async else Client(api_key="test-key")
        # A private loop, so this fixture never mutates global event-loop state.
        self._loop = asyncio.new_event_loop() if self.is_async else None

    def close(self) -> None:
        if self._loop is not None:
            self._loop.close()

    def call(self, method: str, *args, **kwargs):
        result = getattr(self.client, method)(*args, **kwargs)
        if inspect.isawaitable(result):
            assert self._loop is not None
            return self._loop.run_until_complete(result)
        return result

    def patch_transport(self, method: str, **kwargs):
        if self.is_async:
            kwargs.setdefault("new_callable", AsyncMock)
        return patch.object(self.client._transport, method, **kwargs)


@pytest.fixture(params=["sync", "async"])
def client(request):
    """Each test body runs twice: once per client implementation."""
    under_test = ClientUnderTest(request.param)
    try:
        yield under_test
    finally:
        under_test.close()


class TestSubmitParity:
    def test_returns_job_details(self, client):
        with client.patch_transport("post") as post:
            post.return_value = {"id": "job-1", "created_at": "t"}
            job = client.call("submit_job", BytesIO(b"audio"))

        assert (job.id, job.status) == ("job-1", JobStatus.RUNNING)

    def test_embedded_txt_transcript(self, client):
        with client.patch_transport("post") as post:
            post.return_value = {"id": "job-1", "status": "done", "txt": "Hi there"}
            job = client.call("submit_job", BytesIO(b"audio"), wait=60, format_type=FormatType.TXT)

        assert job.status == JobStatus.DONE
        assert job.transcript == "Hi there"

    def test_embedded_json_transcript_under_documented_key(self, client):
        with client.patch_transport("post") as post:
            post.return_value = {"id": "job-1", "status": "done", "json-v2": _transcript_payload()}
            job = client.call("submit_job", BytesIO(b"audio"), wait=60)

        assert isinstance(job.transcript, Transcript)
        assert job.transcript.transcript_text == "Hello"

    def test_wait_elapsed_leaves_job_created(self, client):
        with client.patch_transport("post") as post:
            post.return_value = {"id": "job-1", "status": "created"}
            job = client.call("submit_job", BytesIO(b"audio"), wait=5)

        assert job.status == JobStatus.CREATED
        assert job.transcript is None

    def test_missing_job_id_raises_batch_error(self, client):
        with client.patch_transport("post") as post:
            post.return_value = {"created_at": "t"}
            with pytest.raises(BatchError, match="No job ID returned"):
                client.call("submit_job", BytesIO(b"audio"))

    def test_negative_wait_raises_value_error(self, client):
        """A programmer error stays a ValueError, not a BatchError."""
        with pytest.raises(ValueError, match="non-negative"):
            client.call("submit_job", BytesIO(b"audio"), wait=-1)

    def test_fractional_wait_raises_value_error(self, client):
        with pytest.raises(ValueError, match="whole number"):
            client.call("submit_job", BytesIO(b"audio"), wait=2.5)

    def test_conflicting_audio_sources_raise_value_error(self, client):
        config = JobConfig(type=JobType.TRANSCRIPTION, fetch_data=FetchData(url="https://e.com/a.wav"))
        with pytest.raises(ValueError, match="Cannot specify both"):
            client.call("submit_job", BytesIO(b"audio"), config=config)

    def test_timeout_budget_not_exceeded_by_wait(self, client):
        """transcribe(timeout=5, wait=60) must not ask the server to wait 60s."""
        with client.patch_transport("post") as post:
            post.return_value = {"id": "job-1", "status": "done", "txt": "quick"}
            client.call("transcribe", BytesIO(b"audio"), wait=60, timeout=5, format_type=FormatType.TXT)

        assert post.call_args.kwargs["params"]["wait"] == "5"

    def test_request_timeout_covers_upload_and_wait(self, client):
        with client.patch_transport("post") as post:
            post.return_value = {"id": "job-1", "status": "created"}
            client.call("submit_job", BytesIO(b"audio"), wait=60)

        # Must exceed the operation timeout, not replace it.
        assert post.call_args.kwargs["timeout"] > client.client._conn_config.operation_timeout


class TestTranscriptParity:
    def test_json_transcript(self, client):
        with client.patch_transport("get") as get:
            get.return_value = _transcript_payload("Parity")
            result = client.call("get_transcript", "job-1")

        assert isinstance(result, Transcript)
        assert result.transcript_text == "Parity"

    def test_text_transcript(self, client):
        with client.patch_transport("get") as get:
            get.return_value = {"content": "plain text"}
            result = client.call("get_transcript", "job-1", format_type=FormatType.TXT)

        assert result == "plain text"

    def test_404_raises_transcript_not_ready(self, client):
        with client.patch_transport("get", side_effect=TransportError("HTTP 404", status_code=404)):
            with pytest.raises(TranscriptNotReadyError, match="not available yet"):
                client.call("get_transcript", "job-1", wait=5)

    def test_transcript_not_ready_is_a_job_error(self, client):
        """Existing `except JobError` handlers keep working."""
        with client.patch_transport("get", side_effect=TransportError("HTTP 404", status_code=404)):
            with pytest.raises(JobError):
                client.call("get_transcript", "job-1")

    def test_other_http_errors_stay_job_errors(self, client):
        with client.patch_transport("get", side_effect=TransportError("HTTP 500", status_code=500)):
            with pytest.raises(JobError, match="Failed to get transcript"):
                client.call("get_transcript", "job-1")

    def test_auth_errors_are_not_wrapped(self, client):
        with client.patch_transport("get", side_effect=AuthenticationError("bad key")):
            with pytest.raises(AuthenticationError):
                client.call("get_transcript", "job-1")


class TestPollingParity:
    def test_created_then_done(self, client):
        responses = [
            {"job": {"id": "job-1", "status": "created"}},
            {"job": {"id": "job-1", "status": "done"}},
            _transcript_payload(),
        ]
        with client.patch_transport("get", side_effect=responses):
            result = client.call("wait_for_completion", "job-1", polling_interval=0)

        assert isinstance(result, Transcript)

    def test_unrecognised_status_raises_job_error(self, client):
        """A status this SDK version does not know about is a JobError, not a crash."""
        with client.patch_transport("get") as get:
            get.return_value = {"job": {"id": "job-1", "status": "some-new-status"}}
            with pytest.raises(JobError):
                client.call("wait_for_completion", "job-1", polling_interval=0)

    @pytest.mark.parametrize(
        ("status", "message"),
        [
            ("rejected", "was rejected"),
            ("deleted", "deleted before it finished"),
            ("expired", "has expired"),
        ],
    )
    def test_terminal_failures_are_reported_accurately(self, client, status, message):
        with client.patch_transport("get") as get:
            get.return_value = {"job": {"id": "job-1", "status": status}}
            with pytest.raises(JobError, match=message):
                client.call("wait_for_completion", "job-1", polling_interval=0)

    def test_timeout_raises_timeout_error(self, client):
        with client.patch_transport("get") as get:
            get.return_value = {"job": {"id": "job-1", "status": "running"}}
            with pytest.raises(SMTimeoutError):
                client.call("wait_for_completion", "job-1", polling_interval=0, timeout=0.01)


class TestTranscribeParity:
    def test_single_round_trip_when_wait_succeeds(self, client):
        with client.patch_transport("post") as post:
            with client.patch_transport("get") as get:
                post.return_value = {"id": "job-1", "status": "done", "txt": "One call"}
                result = client.call("transcribe", BytesIO(b"audio"), wait=60, format_type=FormatType.TXT)

        assert result == "One call"
        get.assert_not_called()

    def test_falls_back_to_polling(self, client):
        responses = [
            {"job": {"id": "job-1", "status": "created"}},
            {"job": {"id": "job-1", "status": "done"}},
            _transcript_payload("Polled"),
        ]
        with client.patch_transport("post") as post:
            with client.patch_transport("get", side_effect=responses) as get:
                post.return_value = {"id": "job-1", "status": "created"}
                result = client.call("transcribe", BytesIO(b"audio"), wait=5, polling_interval=0)

        assert result.transcript_text == "Polled"
        # One poll to see it's still running, one to see it's done, one to fetch the transcript.
        assert get.call_count == 3

    def test_no_query_params_without_wait(self, client):
        with client.patch_transport("post") as post:
            post.return_value = {"id": "job-1", "created_at": "t"}
            client.call("submit_job", BytesIO(b"audio"), format_type=FormatType.TXT)

        assert post.call_args.kwargs["params"] is None
        assert post.call_args.kwargs["timeout"] is None


class TestListAndDeleteParity:
    def test_list_jobs_params(self, client):
        with client.patch_transport("get") as get:
            get.return_value = {"jobs": []}
            client.call("list_jobs", limit=5, created_before="2024-01-01", created_after="2023-01-01")

        assert get.call_args.kwargs["params"] == {
            "limit": "5",
            "created_before": "2024-01-01",
            "created_after": "2023-01-01",
        }

    def test_list_jobs_without_filters(self, client):
        with client.patch_transport("get") as get:
            get.return_value = {"jobs": []}
            client.call("list_jobs")

        assert get.call_args.kwargs["params"] is None

    def test_delete_job(self, client):
        with client.patch_transport("delete") as delete:
            client.call("delete_job", "job-1")

        assert delete.call_args.args[0] == "/jobs/job-1"

    def test_delete_job_force(self, client):
        with client.patch_transport("delete") as delete:
            client.call("delete_job", "job-1", force=True)

        assert delete.call_args.kwargs["params"] == {"force": "true"}

    def test_delete_job_without_force_sends_no_params(self, client):
        with client.patch_transport("delete") as delete:
            client.call("delete_job", "job-1")

        assert delete.call_args.kwargs["params"] is None

    def test_locked_job_suggests_force(self, client):
        """The API answers 423 for a running job; the error must say what to do."""
        locked = TransportError("HTTP 423: Locked", status_code=423)
        with client.patch_transport("delete", side_effect=locked):
            with pytest.raises(JobError, match="pass force=True"):
                client.call("delete_job", "job-1")

    def test_other_delete_failures_keep_their_message(self, client):
        with client.patch_transport("delete", side_effect=TransportError("HTTP 500", status_code=500)):
            with pytest.raises(JobError, match="Failed to delete job"):
                client.call("delete_job", "job-1")

    def test_missing_job_info_raises(self, client):
        with client.patch_transport("get") as get:
            get.return_value = {}
            with pytest.raises(JobError, match="No job information found"):
                client.call("get_job_info", "job-1")
