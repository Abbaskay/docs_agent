class AppError(Exception):
    status: int = 500
    message: str = "Internal server error"

    def __init__(self, message: str | None = None, status: int | None = None):
        if message:
            self.message = message
        if status:
            self.status = status
        super().__init__(self.message)

    def to_dict(self):
        return {"error": self.message, "status": self.status}


class ValidationError(AppError):
    def __init__(self, message: str = "Validation failed", status: int = 422):
        super().__init__(message, status)


class RateLimitError(AppError):
    def __init__(
        self,
        message: str = "Rate limit exceeded. Please slow down.",
        status: int = 429,
        retry_after: int | None = None,
    ):
        super().__init__(message, status)
        self.retry_after = retry_after


class AuthError(AppError):
    def __init__(self, message: str = "Unauthorized", status: int = 401):
        super().__init__(message, status)


class NotFoundError(AppError):
    def __init__(self, message: str = "Resource not found", status: int = 404):
        super().__init__(message, status)


class FileValidationError(ValidationError):
    def __init__(self, message: str = "Invalid file"):
        super().__init__(message, 422)


class AIError(AppError):
    def __init__(self, message: str = "AI service error", status: int = 502):
        super().__init__(message, status)


class ExportError(AppError):
    def __init__(self, message: str = "Export failed", status: int = 500):
        super().__init__(message, status)
