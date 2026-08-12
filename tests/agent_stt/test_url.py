from urllib.parse import parse_qs
from urllib.parse import urlparse

import pytest

from speechmatics.agent_stt import DEFAULT_AGENT_STT_URL
from speechmatics.agent_stt import resolve_url


@pytest.fixture(autouse=True)
def _clear_env(monkeypatch):
    monkeypatch.delenv("SPEECHMATICS_AGENT_STT_URL", raising=False)
    monkeypatch.delenv("SPEECHMATICS_RT_URL", raising=False)


def _path(url):
    return urlparse(url).path


def test_default_url():
    assert _path(resolve_url()) == _path(DEFAULT_AGENT_STT_URL)


def test_agent_segment_appended_to_rt_url(monkeypatch):
    monkeypatch.setenv("SPEECHMATICS_RT_URL", "wss://example.com/v2")
    assert _path(resolve_url()) == "/v2/agent"


def test_agent_stt_env_takes_precedence(monkeypatch):
    monkeypatch.setenv("SPEECHMATICS_RT_URL", "wss://rt.example.com/v2")
    monkeypatch.setenv("SPEECHMATICS_AGENT_STT_URL", "wss://agent.example.com/v2/agent")
    url = resolve_url()
    assert urlparse(url).hostname == "agent.example.com"
    assert _path(url) == "/v2/agent"


def test_explicit_url_wins_over_env(monkeypatch):
    monkeypatch.setenv("SPEECHMATICS_AGENT_STT_URL", "wss://agent.example.com/v2/agent")
    assert urlparse(resolve_url("wss://custom.example.com/v2")).hostname == "custom.example.com"


def test_agent_segment_not_duplicated():
    assert _path(resolve_url("wss://example.com/v2/agent")) == "/v2/agent"


def test_trailing_slash_normalized():
    assert _path(resolve_url("wss://example.com/v2/")) == "/v2/agent"


def test_profile_appended():
    assert _path(resolve_url("wss://example.com/v2", profile="default")) == "/v2/agent/default"


def test_profile_not_duplicated():
    assert _path(resolve_url("wss://example.com/v2/agent/default", profile="default")) == "/v2/agent/default"


def test_profile_slashes_stripped():
    assert _path(resolve_url("wss://example.com/v2", profile="/default/")) == "/v2/agent/default"


def test_app_reported():
    params = parse_qs(urlparse(resolve_url("wss://example.com/v2", app="pipecat/1.0")).query)
    assert params["sm-app"] == ["pipecat/1.0"]


def test_default_app_reported():
    params = parse_qs(urlparse(resolve_url("wss://example.com/v2")).query)
    assert params["sm-app"][0].startswith("agent-stt-sdk/")


def test_existing_query_params_kept():
    params = parse_qs(urlparse(resolve_url("wss://example.com/v2?foo=bar&sm-app=existing")).query)
    assert params["foo"] == ["bar"]
    assert params["sm-app"] == ["existing"]
