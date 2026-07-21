from typing import Any

from app.core.enums import ErrorCategory


class AppError(Exception):
    status_code = 400
    code = "APP_ERROR"

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class NotFoundError(AppError):
    status_code = 404
    code = "NOT_FOUND"


class ConflictError(AppError):
    status_code = 409
    code = "CONFLICT"


class ConfigurationError(AppError):
    status_code = 500
    code = "CONFIGURATION_ERROR"


class ProviderUnavailableError(AppError):
    status_code = 503
    code = "MODEL_PROVIDER_UNAVAILABLE"


class ProviderError(AppError):
    status_code = 503
    code = "PROVIDER_ERROR"

    def __init__(
        self,
        message: str,
        *,
        category: ErrorCategory = ErrorCategory.UNKNOWN,
        provider_code: str | None = None,
        retryable: bool = False,
        fallback_allowed: bool = True,
        global_stop: bool = False,
    ) -> None:
        super().__init__(message)
        self.category = category
        self.provider_code = provider_code
        self.retryable = retryable
        self.fallback_allowed = fallback_allowed
        self.global_stop = global_stop
