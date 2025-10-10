"""
This module provides utility functions and decorators for handling API interactions,
such as implementing robust retry mechanisms with exponential backoff.
"""
import time
import random
import logging
from functools import wraps
from typing import Callable, Any

# Using the mock exceptions for type hinting and to avoid circular dependencies
# In a real scenario, these might be defined in a more central error module.
from src.services.mock_google_api_client import MockHttpError429, MockHttpError503, MockQuotaExceededError

# A more generic way to handle real google exceptions if they were to be used.
# from googleapiclient.errors import HttpError as GoogleHttpError
# from google.api_core import exceptions as google_exceptions

logger = logging.getLogger(__name__)

def retry_with_backoff(
    retries: int = 3,
    initial_delay: int = 2,
    backoff_factor: int = 2,
    jitter: bool = True
) -> Callable:
    """
    A decorator to retry a function with an exponential backoff strategy.

    Args:
        retries (int): The maximum number of times to retry the function.
        initial_delay (int): The initial delay in seconds before the first retry.
        backoff_factor (int): The factor by which the delay increases for each retry.
        jitter (bool): Whether to add a small random jitter to the delay to
                       prevent thundering herd problems.
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            delay = initial_delay
            for i in range(retries + 1):
                try:
                    return func(*args, **kwargs)
                except (MockHttpError429, MockHttpError503) as e:
                    if i == retries:
                        logger.error(
                            "API call failed after %d retries for function '%s'. Final error: %s",
                            retries, func.__name__, e
                        )
                        raise  # Re-raise the final exception

                    current_delay = delay + (random.uniform(0, 1) if jitter else 0)
                    logger.warning(
                        "API call failed with %s for function '%s'. Retrying in %.2f seconds... (Attempt %d/%d)",
                        type(e).__name__, func.__name__, current_delay, i + 1, retries
                    )
                    time.sleep(current_delay)
                    delay *= backoff_factor
                except MockQuotaExceededError:
                    logger.error(
                        "API call failed for function '%s' due to a non-retriable quota error. Aborting.",
                        func.__name__
                    )
                    raise # Do not retry on quota errors
                except Exception as e:
                    logger.error(
                        "An unexpected, non-retriable error occurred in function '%s': %s",
                        func.__name__, e
                    )
                    raise # Re-raise unexpected exceptions immediately
        return wrapper
    return decorator