"""Define exceptions."""


class SnooError(Exception):
    """Define a base exception."""

    pass


class InvalidCredentialsError(SnooError):
    """Define an exception related to invalid credentials."""

    pass


class AuthenticationError(SnooError):
    """Define an exception related to invalid credentials."""

    pass


class RequestError(SnooError):
    """Define an exception related to bad HTTP requests."""

    pass
