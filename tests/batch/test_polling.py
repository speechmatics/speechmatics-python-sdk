"""
Unit tests for the status-polling primitives.

These cover the backoff schedule and the transient-failure classification in
isolation; the behaviour they drive is exercised end to end against both
clients in test_client_parity.py.
"""

import pytest

from speechmatics.batch import AuthenticationError
from speechmatics.batch import ConnectionError as SMConnectionError
from speechmatics.batch import JobError
from speechmatics.batch import JobExpiredError
from speechmatics.batch import TransportError
from speechmatics.batch._common import PollingInterval
from speechmatics.batch._common import is_transient_poll_error
from speechmatics.batch._common import jittered_interval


def _reraise_as_job_error(cause: Exception) -> JobError:
    """A failure shaped the way get_job_info() re-raises transport errors."""
    error = JobError(f"Failed to get job info: {cause}")
    error.__cause__ = cause
    return error


class TestPollingInterval:
    def test_ramps_by_multiplier_up_to_the_cap(self):
        interval = PollingInterval(1.0, 8.0, multiplier=2.0)

        # Jitter is +/-20%, so assert the band each step should land in.
        for expected in (1.0, 2.0, 4.0, 8.0, 8.0, 8.0):
            assert interval.next() == pytest.approx(expected, rel=0.2)

    def test_never_exceeds_the_cap_beyond_jitter(self):
        interval = PollingInterval(0.5, 5.0)

        values = [interval.next() for _ in range(20)]

        assert max(values) <= 5.0 * 1.2
        # The tail has converged on the cap rather than still climbing.
        assert values[-1] == pytest.approx(5.0, rel=0.2)

    def test_starts_at_min_interval(self):
        assert PollingInterval(0.5, 5.0).next() == pytest.approx(0.5, rel=0.2)

    def test_min_above_max_is_clamped_to_max(self):
        """A caller who inverts the two gets the cap, not a wait longer than it."""
        interval = PollingInterval(30.0, 5.0)

        assert interval.next() == pytest.approx(5.0, rel=0.2)

    @pytest.mark.parametrize(
        ("kwargs", "message"),
        [
            ({"min_interval": -1.0, "max_interval": 5.0}, "min_polling_interval"),
            ({"min_interval": 0.5, "max_interval": -5.0}, "polling_interval"),
            ({"min_interval": 0.5, "max_interval": 5.0, "multiplier": 1.0}, "multiplier"),
        ],
    )
    def test_rejects_invalid_arguments(self, kwargs, message):
        with pytest.raises(ValueError, match=message):
            PollingInterval(**kwargs)

    @pytest.mark.parametrize(
        ("kwargs", "message"),
        [
            ({"min_interval": 0, "max_interval": 5.0}, "min_polling_interval"),
            ({"min_interval": 0.5, "max_interval": 0}, "polling_interval"),
        ],
    )
    def test_rejects_zero(self, kwargs, message):
        """Zero never grows, so it would poll in an unthrottled loop."""
        with pytest.raises(ValueError, match=message):
            PollingInterval(**kwargs)


class TestJitteredInterval:
    def test_stays_within_twenty_percent(self):
        values = [jittered_interval(10.0) for _ in range(100)]

        assert all(8.0 <= value <= 12.0 for value in values)
        # Jitter actually varies, rather than returning the base every time.
        assert len(set(values)) > 1


class TestTransientPollErrors:
    @pytest.mark.parametrize("status_code", [408, 429, 500, 502, 503, 504])
    def test_retryable_status_codes(self, status_code):
        error = _reraise_as_job_error(TransportError(f"HTTP {status_code}", status_code=status_code))

        assert is_transient_poll_error(error) is True

    def test_request_timeout_without_status_code_is_retryable(self):
        error = _reraise_as_job_error(TransportError("Request timeout for GET /jobs/job-1"))

        assert is_transient_poll_error(error) is True

    def test_connection_failure_is_retryable(self):
        error = _reraise_as_job_error(SMConnectionError("Request failed: connection reset"))

        assert is_transient_poll_error(error) is True

    @pytest.mark.parametrize("status_code", [400, 404, 410, 422])
    def test_client_errors_are_not_retryable(self, status_code):
        error = _reraise_as_job_error(TransportError(f"HTTP {status_code}", status_code=status_code))

        assert is_transient_poll_error(error) is False

    def test_authentication_errors_are_not_retryable(self):
        assert is_transient_poll_error(AuthenticationError("bad key")) is False

    def test_expired_jobs_are_not_retryable(self):
        error = JobExpiredError("Job job-1 has expired")
        error.__cause__ = TransportError("HTTP 410", status_code=410)

        assert is_transient_poll_error(error) is False

    def test_job_error_without_a_transport_cause_is_not_retryable(self):
        """A malformed response body is an answer, not a blip worth repeating."""
        error = _reraise_as_job_error(JobError("No job information found for job ID: job-1"))

        assert is_transient_poll_error(error) is False
