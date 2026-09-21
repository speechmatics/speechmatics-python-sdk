"""Unit tests for the synchronous Client, SyncTransport and sync authentication."""

import json
import logging
import time
from io import BytesIO
from unittest.mock import patch

import httpx
import pytest

from speechmatics.batch import PROCESSING_DATA_HEADER
from speechmatics.batch import AuthBase
from speechmatics.batch import AuthenticationError
from speechmatics.batch import Client
from speechmatics.batch import ConnectionConfig
from speechmatics.batch import FetchData
from speechmatics.batch import FormatType
from speechmatics.batch import JobConfig
from speechmatics.batch import JobStatus
from speechmatics.batch import JobType
from speechmatics.batch import JWTAuth
from speechmatics.batch import StaticKeyAuth
from speechmatics.batch import TimeoutError as SMTimeoutError
from speechmatics.batch import TranscriptionConfig
from speechmatics.batch import TransportError
from speechmatics.batch._sync_transport import SyncTransport

# Polling intervals must be positive, so tests use the smallest interval that
# keeps them fast rather than disabling the wait entirely.
MIN_SLEEP = 0.001


def _transport_with_handler(handler, **kwargs) -> SyncTransport:
    """A SyncTransport whose HTTP calls are served by an in-process handler."""
    transport = SyncTransport(
        "https://asr.api.speechmatics.com/v2",
        ConnectionConfig(),
        StaticKeyAuth("test-key"),
        request_id="req-1",
        **kwargs,
    )
    transport._client = httpx.Client(transport=httpx.MockTransport(handler))
    return transport


def _json_response(payload: dict, status_code: int = 200) -> httpx.Response:
    return httpx.Response(status_code, json=payload)


# ---------------------------------------------------------------------------
# Sync authentication
# ---------------------------------------------------------------------------


class TestSyncAuth:
    def test_static_key_auth_headers(self):
        assert StaticKeyAuth("abc").get_auth_headers_sync() == {"Authorization": "Bearer abc"}

    def test_custom_auth_without_sync_support_raises_clear_error(self):
        class CustomAuth(AuthBase):
            async def get_auth_headers(self):
                return {"Authorization": "Bearer custom"}

        # Existing custom auth classes still instantiate; only sync use fails.
        auth = CustomAuth()
        with pytest.raises(NotImplementedError, match="does not support synchronous authentication"):
            auth.get_auth_headers_sync()

    def test_sync_only_auth_can_be_implemented(self):
        """A blocking caller must not have to write an async method."""

        class SyncOnlyAuth(AuthBase):
            def get_auth_headers_sync(self):
                return {"Authorization": "Bearer sync-only"}

        client = Client(auth=SyncOnlyAuth())
        assert client._auth.get_auth_headers_sync() == {"Authorization": "Bearer sync-only"}

    @pytest.mark.asyncio
    async def test_sync_only_auth_reports_clearly_when_used_async(self):
        class SyncOnlyAuth(AuthBase):
            def get_auth_headers_sync(self):
                return {"Authorization": "Bearer sync-only"}

        with pytest.raises(NotImplementedError, match="does not support asynchronous authentication"):
            await SyncOnlyAuth().get_auth_headers()

    def test_constructible_without_an_event_loop(self):
        """
        Sync callers have no event loop. On Python 3.9 asyncio.Lock() binds to
        the current loop when constructed, so building JWTAuth outside a loop
        used to raise RuntimeError.
        """
        import asyncio

        previous = None
        try:
            previous = asyncio.get_event_loop_policy().get_event_loop()
        except RuntimeError:
            pass

        asyncio.set_event_loop(None)
        try:
            auth = JWTAuth("api-key")
            with patch("httpx.post", return_value=httpx.Response(201, json={"key_value": "t"})):
                assert auth.get_auth_headers_sync() == {"Authorization": "Bearer t"}
        finally:
            asyncio.set_event_loop(previous)

    def test_jwt_auth_mints_token_synchronously(self):
        auth = JWTAuth("api-key", ttl=300)
        response = httpx.Response(201, json={"key_value": "jwt-token"})

        with patch("httpx.post", return_value=response) as mock_post:
            headers = auth.get_auth_headers_sync()

        assert headers == {"Authorization": "Bearer jwt-token"}
        assert mock_post.call_args.kwargs["json"]["ttl"] == 300

    def test_jwt_auth_caches_token(self):
        auth = JWTAuth("api-key", ttl=300)
        response = httpx.Response(201, json={"key_value": "jwt-token"})

        with patch("httpx.post", return_value=response) as mock_post:
            auth.get_auth_headers_sync()
            auth.get_auth_headers_sync()

        assert mock_post.call_count == 1

    def test_jwt_auth_error_is_not_double_wrapped(self):
        auth = JWTAuth("api-key")

        with patch("httpx.post", return_value=httpx.Response(401, text="nope")):
            with pytest.raises(AuthenticationError, match="Failed to generate JWT: HTTP 401"):
                auth.get_auth_headers_sync()


# ---------------------------------------------------------------------------
# SyncTransport
# ---------------------------------------------------------------------------


class TestSyncTransportRequests:
    def test_get_sends_auth_and_tracking_headers(self):
        captured = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["headers"] = request.headers
            return _json_response({"jobs": []})

        transport = _transport_with_handler(handler)
        transport.get("/jobs")

        assert captured["headers"]["authorization"] == "Bearer test-key"
        assert captured["headers"]["x-request-id"] == "req-1"
        assert captured["headers"]["user-agent"].startswith("speechmatics-batch-v")

    def test_get_sends_query_params(self):
        captured = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["url"] = str(request.url)
            return _json_response({"job": {"id": "j1", "status": "done"}})

        transport = _transport_with_handler(handler)
        transport.get("/jobs/j1", params={"wait": "60"})

        assert captured["url"] == "https://asr.api.speechmatics.com/v2/jobs/j1?wait=60"

    def test_post_encodes_config_and_file_as_multipart(self):
        captured = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["content_type"] = request.headers["content-type"]
            captured["body"] = request.content
            return _json_response({"id": "j1"}, status_code=201)

        transport = _transport_with_handler(handler)
        transport.post(
            "/jobs",
            multipart_data={
                "config": {"type": "transcription"},
                "data_file": ("audio.wav", b"RIFF", "audio/wav"),
            },
        )

        assert captured["content_type"].startswith("multipart/form-data")
        assert b'name="config"' in captured["body"]
        assert b'name="data_file"; filename="audio.wav"' in captured["body"]
        assert b"RIFF" in captured["body"]

    def test_post_uses_multipart_even_without_a_file(self):
        """fetch_data submissions have no file, but the API still requires multipart."""
        captured = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["content_type"] = request.headers["content-type"]
            captured["body"] = request.content
            return _json_response({"id": "j1"}, status_code=201)

        transport = _transport_with_handler(handler)
        transport.post("/jobs", multipart_data={"config": {"type": "transcription"}})

        assert captured["content_type"].startswith("multipart/form-data")
        assert b'name="config"' in captured["body"]

    def test_post_sends_extra_headers_as_json(self):
        captured = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["headers"] = request.headers
            return _json_response({"id": "j1"}, status_code=201)

        transport = _transport_with_handler(handler)
        transport.post(
            "/jobs",
            multipart_data={"config": {"type": "transcription"}},
            extra_headers={PROCESSING_DATA_HEADER: {"user_id": "u1"}},
        )

        assert json.loads(captured["headers"][PROCESSING_DATA_HEADER]) == {"user_id": "u1"}

    def test_delete_request(self):
        captured = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["method"] = request.method
            return _json_response({})

        transport = _transport_with_handler(handler)
        transport.delete("/jobs/j1")

        assert captured["method"] == "DELETE"


class TestSyncTransportResponses:
    def test_401_raises_authentication_error(self):
        transport = _transport_with_handler(lambda request: httpx.Response(401))
        with pytest.raises(AuthenticationError, match="Invalid API key"):
            transport.get("/jobs")

    def test_403_raises_authentication_error(self):
        transport = _transport_with_handler(lambda request: httpx.Response(403))
        with pytest.raises(AuthenticationError, match="Access forbidden"):
            transport.get("/jobs")

    def test_server_error_raises_transport_error(self):
        transport = _transport_with_handler(lambda request: httpx.Response(500, text="boom"))
        with pytest.raises(TransportError, match="HTTP 500"):
            transport.get("/jobs")

    def test_speechmatics_json_content_type_is_parsed(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                content=json.dumps({"id": "j1"}).encode(),
                headers={"content-type": "application/vnd.speechmatics.v2+json"},
            )

        transport = _transport_with_handler(handler)
        assert transport.get("/jobs/j1") == {"id": "j1"}

    def test_json_content_type_with_charset_is_parsed(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                content=json.dumps({"id": "j1"}).encode(),
                headers={"content-type": "application/json; charset=utf-8"},
            )

        transport = _transport_with_handler(handler)
        assert transport.get("/jobs/j1") == {"id": "j1"}

    def test_plain_text_response_is_wrapped(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, text="hello world", headers={"content-type": "text/plain"})

        transport = _transport_with_handler(handler)
        result = transport.get("/jobs/j1/transcript")

        assert result["content"] == "hello world"
        assert result["content_type"] == "text/plain"

    def test_timeout_raises_transport_error(self):
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ReadTimeout("too slow", request=request)

        transport = _transport_with_handler(handler)
        with pytest.raises(TransportError, match="Request timeout"):
            transport.get("/jobs")

    def test_network_error_raises_connection_error(self):
        from speechmatics.batch import ConnectionError as SMConnectionError

        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("no route", request=request)

        transport = _transport_with_handler(handler)
        with pytest.raises(SMConnectionError, match="Request failed"):
            transport.get("/jobs")


class TestSyncTransportLifecycle:
    def test_close_is_idempotent(self):
        transport = _transport_with_handler(lambda request: _json_response({}))
        transport.close()
        transport.close()
        assert not transport.is_connected

    def test_context_manager_closes_client(self):
        with SyncTransport("https://asr.api.speechmatics.com/v2", ConnectionConfig(), StaticKeyAuth("k")) as transport:
            assert transport.is_connected
        assert not transport.is_connected


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------


class TestSyncClientBasics:
    def test_requires_api_key(self, monkeypatch):
        monkeypatch.delenv("SPEECHMATICS_API_KEY", raising=False)
        with pytest.raises(ValueError, match="API key required"):
            Client()

    def test_uses_url_from_environment(self, monkeypatch):
        monkeypatch.setenv("SPEECHMATICS_BATCH_URL", "https://example.com/v2")
        client = Client(api_key="k")
        assert client._url == "https://example.com/v2"

    def test_context_manager_closes_transport(self):
        client = Client(api_key="k")
        with patch.object(client._transport, "close") as mock_close:
            with client:
                pass
            mock_close.assert_called_once()

    def test_submit_job_posts_to_jobs(self):
        client = Client(api_key="k")
        with patch.object(client._transport, "post") as mock_post:
            mock_post.return_value = {"id": "job-1", "created_at": "2024-01-01T00:00:00Z"}
            job = client.submit_job(BytesIO(b"audio"))

        assert mock_post.call_args.args[0] == "/jobs"
        assert job.id == "job-1"
        assert job.status == JobStatus.RUNNING

    def test_submit_job_sends_processing_data_header(self):
        client = Client(api_key="k")
        with patch.object(client._transport, "post") as mock_post:
            mock_post.return_value = {"id": "job-1"}
            client.submit_job(BytesIO(b"audio"), parallel_engines=4, user_id="u1")

        extra_headers = mock_post.call_args.kwargs["extra_headers"]
        assert extra_headers[PROCESSING_DATA_HEADER] == {"parallel_engines": 4, "user_id": "u1"}

    def test_submit_job_reads_file_from_path(self, tmp_path):
        audio_path = tmp_path / "sample.wav"
        audio_path.write_bytes(b"RIFF-data")

        client = Client(api_key="k")
        with patch.object(client._transport, "post") as mock_post:
            mock_post.return_value = {"id": "job-1"}
            job = client.submit_job(str(audio_path))

        # The file handle is passed through, not its contents, so the upload streams.
        filename, file_data, content_type = mock_post.call_args.kwargs["multipart_data"]["data_file"]
        assert (filename, content_type) == ("sample.wav", "audio/wav")
        assert hasattr(file_data, "read")
        assert job.data_name == "sample.wav"

    def test_submit_job_with_fetch_data(self):
        client = Client(api_key="k")
        config = JobConfig(
            type=JobType.TRANSCRIPTION,
            fetch_data=FetchData(url="https://example.com/audio.wav"),
            transcription_config=TranscriptionConfig(language="en"),
        )
        with patch.object(client._transport, "post") as mock_post:
            mock_post.return_value = {"id": "job-1"}
            job = client.submit_job(None, config=config)

        multipart = mock_post.call_args.kwargs["multipart_data"]
        assert "data_file" not in multipart
        assert job.data_name == "https://example.com/audio.wav"

    def test_rejects_missing_audio_source(self):
        client = Client(api_key="k")
        with pytest.raises(ValueError, match="Must provide either"):
            client.submit_job(None)

    def test_list_jobs(self):
        client = Client(api_key="k")
        with patch.object(client._transport, "get") as mock_get:
            mock_get.return_value = {
                "jobs": [
                    {"id": "j1", "status": "done", "created_at": "t", "data_name": "a.wav"},
                    {"id": "j2", "status": "running", "created_at": "t", "data_name": "b.wav"},
                ]
            }
            jobs = client.list_jobs(limit=2)

        assert [job.id for job in jobs] == ["j1", "j2"]
        assert mock_get.call_args.kwargs["params"] == {"limit": "2"}

    def test_authentication_error_is_not_wrapped(self):
        client = Client(api_key="k")
        with patch.object(client._transport, "get", side_effect=AuthenticationError("bad key")):
            with pytest.raises(AuthenticationError):
                client.get_job_info("job-1")


class TestSyncClientWaitForCompletion:

    def test_sleep_is_bounded_by_remaining_timeout(self):
        from speechmatics.batch import TimeoutError as SMTimeoutError

        client = Client(api_key="k")
        with patch.object(client._transport, "get") as mock_get:
            mock_get.return_value = {"job": {"id": "job-1", "status": "running"}}
            with patch("speechmatics.batch._sync_client.time.sleep") as mock_sleep:
                with pytest.raises(SMTimeoutError):
                    client.wait_for_completion("job-1", polling_interval=100.0, timeout=0.5)

        assert all(call.args[0] <= 0.5 for call in mock_sleep.call_args_list)

    def test_requests_are_bounded_by_remaining_timeout(self):
        """
        Bounding only the sleeps lets one hung request overrun the caller's
        timeout by a whole operation timeout, so the requests are bounded too.
        """
        from speechmatics.batch import TimeoutError as SMTimeoutError

        client = Client(api_key="k")
        client._conn_config.operation_timeout = 300.0
        with patch.object(client._transport, "get") as mock_get:
            mock_get.return_value = {"job": {"id": "job-1", "status": "running"}}
            with pytest.raises(SMTimeoutError):
                client.wait_for_completion("job-1", polling_interval=MIN_SLEEP, timeout=0.5)

        timeouts = [call.kwargs["timeout"] for call in mock_get.call_args_list]
        assert timeouts
        assert all(timeout is not None and timeout <= 0.5 for timeout in timeouts)

    def test_deadline_is_not_reported_as_a_transport_failure(self, caplog):
        """
        The server holds a status request for an unspecified time, so a request
        cut short by the caller's deadline is the timeout arriving, not a blip.
        """
        client = Client(api_key="k")

        def held_past_the_deadline(*args, **kwargs):
            time.sleep(0.15)
            raise TransportError("Request timeout for GET /jobs/job-1")

        with patch.object(client._transport, "get", side_effect=held_past_the_deadline):
            with caplog.at_level(logging.WARNING, logger="speechmatics.batch"):
                with pytest.raises(SMTimeoutError):
                    client.wait_for_completion("job-1", polling_interval=MIN_SLEEP, timeout=0.05)

        assert "retrying" not in caplog.text

    def test_get_job_info_keeps_the_default_request_timeout(self):
        """Bounding polling requests must not change a plain get_job_info()."""
        client = Client(api_key="k")
        with patch.object(client._transport, "get") as mock_get:
            mock_get.return_value = {"job": {"id": "job-1", "status": "running"}}
            client.get_job_info("job-1")

        assert mock_get.call_args.kwargs["timeout"] is None


class TestSyncClientEndToEnd:
    """The full submit-and-fetch flow over a mocked HTTP layer."""

    def test_transcribe_with_wait(self):
        def handler(request: httpx.Request) -> httpx.Response:
            assert request.url.params["wait"] == "60"
            assert request.url.params["format"] == "txt"
            return _json_response({"id": "job-1", "status": "done", "txt": "End to end"}, status_code=201)

        client = Client(api_key="k")
        client._transport = _transport_with_handler(handler)

        result = client.transcribe(BytesIO(b"audio"), wait=60, format_type=FormatType.TXT)

        assert result == "End to end"

    def test_submit_then_poll_then_fetch(self):
        calls = []

        def handler(request: httpx.Request) -> httpx.Response:
            calls.append((request.method, request.url.path))
            if request.method == "POST":
                return _json_response({"id": "job-1", "status": "created"}, status_code=201)
            if request.url.path.endswith("/transcript"):
                return _json_response(
                    {
                        "format": "2.9",
                        "job": {"id": "job-1", "created_at": "t", "data_name": "audio.wav"},
                        "metadata": {"created_at": "t", "type": "transcription"},
                        "results": [],
                    }
                )
            return _json_response({"job": {"id": "job-1", "status": "done"}})

        client = Client(api_key="k")
        client._transport = _transport_with_handler(handler)

        job = client.submit_job(BytesIO(b"audio"))
        result = client.wait_for_completion(job.id, polling_interval=MIN_SLEEP)

        assert result.results == []
        assert calls == [
            ("POST", "/v2/jobs"),
            ("GET", "/v2/jobs/job-1"),
            ("GET", "/v2/jobs/job-1/transcript"),
        ]
