class AppError(Exception):
    """Ошибка с текстом, который можно показать пользователю."""

    def __init__(self, message, status=0):
        super().__init__(message)
        self.status = status


class ValidationError(AppError):
    pass


class NetworkError(AppError):
    pass


class AuthError(AppError):
    """Сессия недействительна — нужен повторный вход."""
