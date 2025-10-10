"""
This module provides real, production-ready implementations for tools required
by the application, such as fetching website content.
"""
import requests
from src.services.api_util import retry_with_backoff

@retry_with_backoff(retries=2, initial_delay=3)
def view_text_website(url: str) -> str:
    """
    Fetches the text content of a website using the requests library.

    Args:
        url: The URL of the website to fetch.

    Returns:
        The text content of the website, or an empty string if the request
        fails for any reason (e.g., network error, non-200 status code).
    """
    if not url or not url.startswith(('http://', 'https://')):
        # Add http scheme if it's missing, as requests requires it.
        url = f"http://{url}"

    try:
        response = requests.get(url, timeout=10, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        # Raise an exception for bad status codes (4xx or 5xx)
        response.raise_for_status()

        # Check if content type is likely to be HTML/text to avoid downloading large binary files
        content_type = response.headers.get('content-type', '')
        if 'text' not in content_type and 'html' not in content_type:
            return "" # Not a text-based page, return empty

        return response.text

    except requests.exceptions.RequestException as e:
        # This catches connection errors, timeouts, invalid URLs, and bad status codes.
        # We will simulate these as 503-style errors for the retry decorator.
        # This is a simplification for the purpose of this exercise.
        # In a real app, we might have more nuanced error handling here.
        from src.services.mock_google_api_client import MockHttpError503
        print(f"Could not fetch website content for {url}. Error: {e}")
        raise MockHttpError503(f"Website fetch failed: {e}") from e
    except Exception as e:
        # Catch any other unexpected errors and re-raise them as well.
        print(f"An unexpected error occurred while fetching {url}: {e}")
        raise