"""Offline replica of Unity AiJobPollPolicy — no OpenAI, no database.

Keep this table in sync with
FashionRise/Assets/FashionRise/Infrastructure/Api/AiJobPollPolicy.cs
"""

from __future__ import annotations

from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
POLICY_CS = REPO / "FashionRise/Assets/FashionRise/Infrastructure/Api/AiJobPollPolicy.cs"
PIPELINE_CS = REPO / "FashionRise/Assets/FashionRise/Infrastructure/Api/SketchPipelineApiService.cs"

STATUS_REQUEST_TIMEOUT = 408
STATUS_TOO_MANY_REQUESTS = 429


class _ApiException(Exception):
    def __init__(self, status_code: int):
        self.status_code = status_code


class _HttpRequestException(Exception):
    pass


class _TaskCanceledException(Exception):
    pass


class _OperationCanceledException(Exception):
    pass


def is_retryable_http_status(status_code: int) -> bool:
    if status_code == STATUS_REQUEST_TIMEOUT:
        return True
    return 500 <= status_code <= 599


def is_fail_fast_http_status(status_code: int) -> bool:
    if status_code == STATUS_TOO_MANY_REQUESTS:
        return True
    if is_retryable_http_status(status_code):
        return False
    return 400 <= status_code <= 499


def should_retry_poll_exception(ex: Exception, user_cancel_requested: bool) -> bool:
    if user_cancel_requested:
        return False
    if isinstance(ex, _TaskCanceledException):
        return True
    if isinstance(ex, _OperationCanceledException):
        return False
    if isinstance(ex, _ApiException):
        return not is_fail_fast_http_status(ex.status_code)
    if isinstance(ex, _HttpRequestException):
        return True
    return True


def should_attempt_polish_recovery(ex: Exception, user_cancel_requested: bool) -> bool:
    if user_cancel_requested:
        return False
    if isinstance(ex, _TaskCanceledException):
        return True
    if isinstance(ex, _OperationCanceledException):
        return False
    if isinstance(ex, _ApiException) and is_fail_fast_http_status(ex.status_code):
        return False
    return True


@pytest.mark.parametrize(
    "status, fail_fast, retryable",
    [
        (401, True, False),
        (403, True, False),
        (404, True, False),
        (400, True, False),
        (409, True, False),
        (422, True, False),
        (429, True, False),
        (408, False, True),
        (500, False, True),
        (502, False, True),
        (503, False, True),
        (504, False, True),
        (0, False, False),
        (200, False, False),
    ],
)
def test_http_status_classification(status: int, fail_fast: bool, retryable: bool) -> None:
    assert is_fail_fast_http_status(status) is fail_fast
    assert is_retryable_http_status(status) is retryable


@pytest.mark.parametrize("status", [401, 403, 404, 400, 429])
def test_fail_fast_statuses_are_not_retried_or_recovered(status: int) -> None:
    ex = _ApiException(status)
    assert should_retry_poll_exception(ex, False) is False
    assert should_attempt_polish_recovery(ex, False) is False


@pytest.mark.parametrize("status", [408, 500, 503])
def test_retryable_http_is_retried_and_may_recover(status: int) -> None:
    ex = _ApiException(status)
    assert should_retry_poll_exception(ex, False) is True
    assert should_attempt_polish_recovery(ex, False) is True


def test_transport_timeout_retries_and_may_recover() -> None:
    assert should_retry_poll_exception(_HttpRequestException(), False) is True
    assert should_retry_poll_exception(_TaskCanceledException(), False) is True
    assert should_attempt_polish_recovery(_HttpRequestException(), False) is True
    assert should_attempt_polish_recovery(_TaskCanceledException(), False) is True


def test_user_cancellation_never_retries_or_recovers() -> None:
    for ex in (
        _OperationCanceledException(),
        _TaskCanceledException(),
        _ApiException(503),
        _HttpRequestException(),
    ):
        assert should_retry_poll_exception(ex, True) is False
        assert should_attempt_polish_recovery(ex, True) is False
    assert should_retry_poll_exception(_OperationCanceledException(), False) is False
    assert should_attempt_polish_recovery(_OperationCanceledException(), False) is False


def test_completed_job_timeout_status_zero_still_recovers() -> None:
    """Poll budget exhausted (ApiException 0) is transient enough to recover a finished job."""
    ex = _ApiException(0)
    assert is_fail_fast_http_status(0) is False
    assert should_attempt_polish_recovery(ex, False) is True
    assert should_retry_poll_exception(ex, False) is True


def test_csharp_policy_encodes_the_same_status_table() -> None:
    src = POLICY_CS.read_text(encoding="utf-8")
    assert "StatusRequestTimeout = 408" in src
    assert "StatusTooManyRequests = 429" in src
    assert "statusCode >= 500 && statusCode <= 599" in src
    assert "statusCode >= 400 && statusCode <= 499" in src
    assert "IsFailFastHttpStatus" in src
    assert "ShouldAttemptPolishRecovery" in src
    assert "ShouldRetryPollException" in src


def test_pipeline_uses_policy_and_does_not_bare_catch_all_api_errors() -> None:
    src = PIPELINE_CS.read_text(encoding="utf-8")
    assert "AiJobPollPolicy.IsFailFastHttpStatus" in src
    assert "AiJobPollPolicy.ShouldAttemptPolishRecovery" in src
    assert "catch (OperationCanceledException) when (cancellationToken.IsCancellationRequested)" in src
    assert "ex.IsRateLimited" in src
    # The unfiltered catch is only the retryable leftover after fail-fast filters.
    assert src.count("catch (ApiException ex) when (AiJobPollPolicy.IsFailFastHttpStatus") == 1
    assert src.count("catch (ApiException)") == 1
