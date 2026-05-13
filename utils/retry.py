import sys
import time
from collections.abc import Callable
from typing import TypeVar

T = TypeVar("T")


def retry_with_backoff(
    func: Callable[[], T],
    max_retries: int = 3,
    base_delay: float = 1.0,
    backoff_factor: float = 2.0,
) -> T:
    """Call func with exponential backoff on exception."""
    last_exc = None
    for attempt in range(max_retries + 1):
        try:
            return func()
        except Exception as e:
            last_exc = e
            if attempt == max_retries:
                break
            delay = base_delay * (backoff_factor ** attempt)
            print(f"  Retry {attempt + 1}/{max_retries} in {delay:.0f}s: {e}", file=sys.stderr)
            time.sleep(delay)
    raise last_exc  # type: ignore[misc]
