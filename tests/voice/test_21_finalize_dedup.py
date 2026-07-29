import asyncio

import pytest

from speechmatics.voice import VoiceAgentClient
from speechmatics.voice._models import EndOfUtteranceMode
from speechmatics.voice._models import VoiceAgentConfig


async def _run_client_with_concurrent_finalize(force_eou: bool) -> int:
    """Fire two finalize() calls in the same tick and count how many times segments
    are emitted. Returns the emit count. Fully offline / deterministic.
    """
    client = VoiceAgentClient(
        api_key="test",
        config=VoiceAgentConfig(end_of_utterance_mode=EndOfUtteranceMode.FIXED),
    )

    # Simulate the VAD/adaptive path where a forced EOU is awaited. The stub mirrors the
    # real _await_forced_eou: it flips _forced_eou_active around a small await, opening the
    # exact window the bug relied on (the flag is only set once the task is running).
    client._use_forced_eou = force_eou

    async def _fake_await_forced_eou(timeout: float = 1.0) -> None:
        client._forced_eou_active = True
        await asyncio.sleep(0.02)
        client._forced_eou_active = False

    client._await_forced_eou = _fake_await_forced_eou  # type: ignore[method-assign]

    # Count segment emissions instead of building real views.
    emit_count = 0

    async def _fake_emit_segments(finalize: bool = False, is_eou: bool = False) -> None:
        nonlocal emit_count
        emit_count += 1

    client._emit_segments = _fake_emit_segments  # type: ignore[method-assign]

    # Process the STT queue (where finalize() hands the emit off).
    queue_task = asyncio.create_task(client._run_stt_queue())
    try:
        # Two finalize() calls landing in the same tick (internal VAD + external client).
        client.finalize()
        client.finalize()

        # Let the emit task(s) and the queued emit run.
        await asyncio.sleep(0.1)
    finally:
        queue_task.cancel()
        try:
            await queue_task
        except asyncio.CancelledError:
            pass

    # The in-progress guard must be released again for future turns.
    assert client._finalize_in_progress is False
    return emit_count


@pytest.mark.asyncio
async def test_concurrent_finalize_forced_eou_emits_once():
    """Two finalize() calls in the same tick (VAD-triggered + client) must not duplicate.

    Reproduces the reported race: with a low VAD trigger the internal finalize and an
    external finalize() collide before _forced_eou_active is set, and previously both
    spawned emit tasks. The synchronous _finalize_in_progress guard must collapse them
    to a single emission.
    """
    assert await _run_client_with_concurrent_finalize(force_eou=True) == 1


@pytest.mark.asyncio
async def test_concurrent_finalize_direct_emits_once():
    """Same guarantee on the non-forced path (no forced-EOU wait)."""
    assert await _run_client_with_concurrent_finalize(force_eou=False) == 1
