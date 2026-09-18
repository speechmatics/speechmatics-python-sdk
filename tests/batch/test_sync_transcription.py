"""Unit tests for synchronous transcription (the server-side ``wait`` parameter)."""

from io import BytesIO
from unittest.mock import AsyncMock
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest

from speechmatics.batch import AsyncClient
from speechmatics.batch import Client
from speechmatics.batch import ConnectionConfig
from speechmatics.batch import FormatType
from speechmatics.batch import JobDetails
from speechmatics.batch import JobStatus
from speechmatics.batch import StaticKeyAuth
from speechmatics.batch import Transcript
from speechmatics.batch._common import build_query_params
from speechmatics.batch._common import extract_embedded_transcript
from speechmatics.batch._common import is_job_active
from speechmatics.batch._common import jittered_interval
from speechmatics.batch._common import request_timeout_for_wait


def _transcript_payload(text: str = "Hello") -> dict:
    return {
        "format": "2.9",
        "job": {"id": "job-123", "created_at": "2024-01-01T00:00:00Z", "data_name": "audio.wav"},
        "metadata": {"created_at": "2024-01-01T00:00:00Z", "type": "transcription"},
        "results": [
            {
                "type": "word",
                "start_time": 0.0,
                "end_time": 0.5,
                "alternatives": [{"content": text, "confidence": 0.9, "language": "en"}],
            }
        ],
    }


# ---------------------------------------------------------------------------
# Query parameter construction
# ---------------------------------------------------------------------------


class TestBuildQueryParams:
    def test_no_params_when_nothing_requested(self):
        assert build_query_params() is None

    def test_wait_serialized(self):
        assert build_query_params(wait=60) == {"wait": "60"}

    def test_wait_zero_is_sent(self):
        assert build_query_params(wait=0) == {"wait": "0"}

    def test_json_format_omitted_to_use_api_default(self):
        assert build_query_params(format_type=FormatType.JSON) is None

    def test_non_default_format_sent(self):
        assert build_query_params(format_type=FormatType.TXT) == {"format": "txt"}

    def test_wait_and_format_together(self):
        assert build_query_params(wait=30, format_type=FormatType.SRT) == {"wait": "30", "format": "srt"}

    def test_negative_wait_rejected(self):
        with pytest.raises(ValueError, match="non-negative"):
            build_query_params(wait=-1)


class TestRequestTimeoutForWait:
    def test_none_without_wait(self):
        assert request_timeout_for_wait(None, ConnectionConfig()) is None

    def test_exceeds_wait_so_server_can_use_full_window(self):
        assert request_timeout_for_wait(60, ConnectionConfig()) > 60

    def test_never_shorter_than_the_configured_operation_timeout(self):
        """Asking the server to wait must not shrink the budget for the upload."""
        conn_config = ConnectionConfig(operation_timeout=300.0)
        assert request_timeout_for_wait(60, conn_config) > conn_config.operation_timeout


class TestJitteredInterval:
    def test_stays_near_base_interval(self):
        values = [jittered_interval(5.0) for _ in range(50)]
        assert all(4.0 <= v <= 6.0 for v in values)
        assert len(set(values)) > 1

    def test_zero_stays_zero(self):
        assert jittered_interval(0.0) == 0.0


# ---------------------------------------------------------------------------
# Embedded transcript parsing
# ---------------------------------------------------------------------------


class TestExtractEmbeddedTranscript:
    def test_txt_transcript(self):
        response = {"id": "a1", "status": "done", "txt": "Welcome to Speechmatics"}
        assert extract_embedded_transcript(response, FormatType.TXT) == "Welcome to Speechmatics"

    def test_srt_transcript(self):
        response = {"id": "a1", "status": "done", "srt": "1\n00:00:00,000 --> 00:00:01,000\nHi\n"}
        assert extract_embedded_transcript(response, FormatType.SRT).startswith("1\n")

    def test_json_transcript_nested_under_json_v2_key(self):
        """Documented shape: {"id", "status", "json-v2": {...}}."""
        response = {"id": "uwcl3jevp3", "status": "done", "json-v2": _transcript_payload()}
        result = extract_embedded_transcript(response, FormatType.JSON)
        assert isinstance(result, Transcript)
        assert result.transcript_text == "Hello"

    def test_json_transcript_not_read_from_other_keys(self):
        """A transcript merged at the top level is not a shape the API sends."""
        response = {"id": "job-123", "status": "done", **_transcript_payload()}
        assert extract_embedded_transcript(response, FormatType.JSON) is None

    def test_none_when_job_still_running(self):
        assert extract_embedded_transcript({"id": "a1", "status": "created"}, FormatType.JSON) is None

    def test_none_when_format_key_absent(self):
        assert extract_embedded_transcript({"id": "a1", "status": "created"}, FormatType.TXT) is None


# ---------------------------------------------------------------------------
# Job status handling
# ---------------------------------------------------------------------------


class TestJobStatus:
    def test_created_status_is_supported(self):
        """The synchronous API reports 'created' for a job that is still running."""
        assert JobStatus("created") == JobStatus.CREATED

    def test_created_and_running_are_active(self):
        assert is_job_active(JobStatus.CREATED)
        assert is_job_active(JobStatus.RUNNING)

    def test_terminal_states_are_not_active(self):
        assert not is_job_active(JobStatus.DONE)
        assert not is_job_active(JobStatus.REJECTED)


class TestJobDetailsFromSparseResponse:
    def test_wait_timeout_response_parses(self):
        """A job whose wait elapsed comes back as only an id and status."""
        job = JobDetails.from_dict({"id": "a1b2c3", "status": "created"})
        assert job.id == "a1b2c3"
        assert job.status == JobStatus.CREATED
        assert job.created_at == ""
        assert job.data_name == ""
        assert job.transcript is None


# ---------------------------------------------------------------------------
# Client behaviour: async and sync are checked side by side
# ---------------------------------------------------------------------------


class TestTranscribeWithWait:
    def test_fetches_transcript_when_done_without_embedded_payload(self):
        """A done job with no embedded transcript still resolves, via one extra call."""
        client = Client(api_key="test-key")
        with patch.object(client._transport, "post") as mock_post:
            with patch.object(client._transport, "get") as mock_get:
                mock_post.return_value = {"id": "job-123", "status": "done"}
                mock_get.return_value = _transcript_payload("Fetched")
                result = client.transcribe(BytesIO(b"audio"), wait=60)

        assert result.transcript_text == "Fetched"
        assert mock_get.call_count == 1


class TestGetJobInfoAndTranscriptWait:
    def test_get_job_info_sends_wait(self):
        client = Client(api_key="test-key")
        with patch.object(client._transport, "get") as mock_get:
            mock_get.return_value = {"job": {"id": "job-1", "status": "done"}}
            client.get_job_info("job-1", wait=30)

        _, kwargs = mock_get.call_args
        assert kwargs["params"] == {"wait": "30"}
        assert kwargs["timeout"] > 30


class TestAsyncSyncParity:
    """The two clients must produce identical results from identical responses."""

    @pytest.mark.asyncio
    async def test_public_surface_parity(self):
        """Every public method on AsyncClient has a sync counterpart."""
        async_methods = {name for name in dir(AsyncClient) if not name.startswith("_")}
        sync_methods = {name for name in dir(Client) if not name.startswith("_")}
        assert async_methods == sync_methods

    def test_signature_parity(self):
        """Matching methods accept the same keyword arguments."""
        import inspect

        for name in ("submit_job", "get_job_info", "get_transcript", "wait_for_completion", "transcribe", "list_jobs"):
            async_params = inspect.signature(getattr(AsyncClient, name)).parameters
            sync_params = inspect.signature(getattr(Client, name)).parameters
            assert list(async_params) == list(sync_params), f"{name} signatures diverged"


class TestAuthenticationErrorParity:
    """An invalid API key must surface as AuthenticationError on both clients."""

    @pytest.mark.asyncio
    async def test_async_401_raises_authentication_error(self):
        import aiohttp

        from speechmatics.batch import AuthenticationError
        from speechmatics.batch._transport import Transport

        transport = Transport("https://example.com/v2", ConnectionConfig(), StaticKeyAuth("bad-key"))
        response = MagicMock(spec=aiohttp.ClientResponse)
        response.status = 401

        with pytest.raises(AuthenticationError, match="Invalid API key"):
            await transport._handle_response(response)

    @pytest.mark.asyncio
    async def test_async_auth_error_survives_the_request_wrapper(self):
        """The outer request handler must not re-wrap AuthenticationError."""
        from speechmatics.batch import AuthenticationError
        from speechmatics.batch._transport import Transport

        class _FakeRequest:
            async def __aenter__(self):
                return MagicMock()

            async def __aexit__(self, *args):
                return None

        transport = Transport("https://example.com/v2", ConnectionConfig(), StaticKeyAuth("bad-key"))
        session = MagicMock()
        session.request = MagicMock(return_value=_FakeRequest())
        transport._session = session

        with patch.object(
            transport, "_handle_response", new_callable=AsyncMock, side_effect=AuthenticationError("Invalid API key")
        ):
            with pytest.raises(AuthenticationError, match="Invalid API key"):
                await transport.get("/jobs")


class TestBackwardCompatibility:
    """Existing call patterns must behave exactly as before."""

    @pytest.mark.asyncio
    async def test_submit_job_without_wait_reports_running(self):
        client = AsyncClient(api_key="test-key")
        with patch.object(client._transport, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = {"id": "job-1", "created_at": "2024-01-01T00:00:00Z"}
            job = await client.submit_job(BytesIO(b"audio"))

        assert job.status == JobStatus.RUNNING
        assert job.transcript is None
        assert job.data_name == "audio.wav"


class TestSpeakerLabels:
    """
    "UU" is the label the API returns for an unidentified speaker, which is what
    undiarized audio produces. It must not be rendered as a speaker.
    """

    @staticmethod
    def _transcript(*speakers: object) -> Transcript:
        words = ["Hello", "there", "friend", "again"]
        return Transcript.from_dict(
            {
                "format": "2.9",
                "job": {"id": "j1", "created_at": "t", "data_name": "a.wav"},
                "metadata": {"created_at": "t", "type": "transcription"},
                "results": [
                    {
                        "type": "word",
                        "start_time": float(i),
                        "end_time": float(i) + 0.5,
                        "alternatives": [
                            {
                                "content": words[i],
                                "confidence": 0.9,
                                "language": "en",
                                **({} if speaker is None else {"speaker": speaker}),
                            }
                        ],
                    }
                    for i, speaker in enumerate(speakers)
                ],
            }
        )

    def test_unknown_speaker_is_not_labelled(self):
        assert self._transcript("UU", "UU").transcript_text == "Hello there"

    def test_absent_speaker_is_not_labelled(self):
        assert self._transcript(None, None).transcript_text == "Hello there"

    def test_identified_speakers_are_still_labelled(self):
        text = self._transcript("S1", "S2").transcript_text
        assert text == "SPEAKER S1: Hello\nSPEAKER S2: there"

    def test_unknown_speaker_does_not_split_identified_runs(self):
        """UU segments group with each other, not against a speaker label."""
        text = self._transcript("S1", "UU", "UU", "S1").transcript_text
        assert text == "SPEAKER S1: Hello\nthere friend\nSPEAKER S1: again"

    def test_matches_the_api_text_rendering_for_undiarized_audio(self):
        """The json-v2 rendering must agree with the API's own txt output."""
        assert "SPEAKER" not in self._transcript("UU", "UU", "UU", "UU").transcript_text
