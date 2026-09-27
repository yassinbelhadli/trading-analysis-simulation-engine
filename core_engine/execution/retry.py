"""Retry logic for broker operations — configurable attempts, backoff, jitter."""

from __future__ import annotations
import time
import random
import logging
from functools import wraps
from typing import Callable, Type, Tuple

from .errors import RetryExhaustedError

logger = logging.getLogger(__name__)


def retry(
    max_attempts: int = 3,
    base_delay: float = 0.5,
    max_delay: float = 10.0,
    backoff: float = 2.0,
    jitter: float = 0.1,
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
):
    """Decorator: retry a broker operation with exponential backoff.

    Args:
        max_attempts: max retries (including first attempt)
        base_delay: initial delay in seconds
        max_delay: max delay in seconds
        backoff: multiplier per attempt
        jitter: random jitter fraction (0.1 = +-10%)
        exceptions: exception types to retry on

    Raises:
        RetryExhaustedError after all attempts fail.
    """
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exc = None
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exc = e
                    if attempt == max_attempts:
                        logger.error("All %d retries exhausted for %s: %s",
                                     max_attempts, func.__name__, e)
                        raise RetryExhaustedError(
                            f"{func.__name__} failed after {max_attempts} attempts"
                        ) from e
                    delay = min(base_delay * (backoff ** (attempt - 1)), max_delay)
                    jit = delay * random.uniform(-jitter, jitter)
                    total_delay = delay + jit
                    logger.warning("Retry %d/%d for %s in %.2fs (error: %s)",
                                   attempt, max_attempts, func.__name__, total_delay, e)
                    time.sleep(total_delay)
            return None  # unreachable
        return wrapper
    return decorator
