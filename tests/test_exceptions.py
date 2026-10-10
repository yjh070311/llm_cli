import pytest

from exceptions import (
    AuthenticationError,
    HTTPStatusError,
    ModelError,
    NetworkError,
    RateLimitError,
    should_retry,
)


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (NetworkError("temporary network issue"), True),
        (RateLimitError("rate limited"), True),
        (HTTPStatusError("server error", 503), True),
        (HTTPStatusError("bad request", 400), False),
        (AuthenticationError("invalid key"), False),
        (ModelError("missing model"), False),
        (ValueError("unknown"), False),
    ],
)
def test_should_retry(error: Exception, expected: bool) -> None:
    assert should_retry(error) is expected
