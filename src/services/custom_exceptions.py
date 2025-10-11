"""
This module defines custom, shareable exception classes for simulating API errors
during testing, avoiding circular import issues.
"""

class MockHttpError(Exception):
    """Base class for mock HTTP errors."""
    def __init__(self, message, status_code):
        super().__init__(message)
        self.status_code = status_code
        self.reason = message

class MockHttpError429(MockHttpError):
    """Simulates a 'Too Many Requests' (429) error."""
    def __init__(self, message="Rate limit exceeded"):
        super().__init__(message, 429)

class MockHttpError503(MockHttpError):
    """Simulates a 'Service Unavailable' (503) error."""
    def __init__(self, message="Service temporarily unavailable"):
        super().__init__(message, 503)

class MockQuotaExceededError(MockHttpError):
    """Simulates a 'Quota Exceeded' error, often a 403 or 429 status."""
    def __init__(self, message="Daily query quota exceeded"):
        super().__init__(message, 403)