# -*- coding: utf-8 -*-
"""Integration service exceptions — never include credentials in messages."""


class EiIntegrationError(Exception):
    """Base integration error."""

    error_class = 'EiIntegrationError'
    retryable = False

    def __init__(self, message, error_class=None, retryable=None, details=None):
        super().__init__(message)
        if error_class:
            self.error_class = error_class
        if retryable is not None:
            self.retryable = retryable
        self.details = details or {}


class EiAuthenticationError(EiIntegrationError):
    error_class = 'AuthenticationError'
    retryable = False


class EiAuthorizationError(EiIntegrationError):
    error_class = 'AuthorizationError'
    retryable = False


class EiValidationError(EiIntegrationError):
    error_class = 'ValidationError'
    retryable = False


class EiTimeoutError(EiIntegrationError):
    error_class = 'TimeoutError'
    retryable = True


class EiConnectionError(EiIntegrationError):
    error_class = 'ConnectionError'
    retryable = True


class EiRateLimitError(EiIntegrationError):
    error_class = 'RateLimitError'
    retryable = True


class EiServerError(EiIntegrationError):
    error_class = 'ServerError'
    retryable = True


class EiConflictError(EiIntegrationError):
    error_class = 'ConflictError'
    retryable = False


class EiDuplicateError(EiIntegrationError):
    error_class = 'DuplicateError'
    retryable = False
