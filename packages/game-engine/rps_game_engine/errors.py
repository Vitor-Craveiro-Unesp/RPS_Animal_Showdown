"""Stable, non-localized errors emitted by the domain engine."""

from __future__ import annotations


class EngineError(Exception):
    """Base error carrying a stable code for integration boundaries."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class EngineValidationError(EngineError):
    """Input or reconstructed state violates a domain invariant."""


class InvalidTransitionError(EngineError):
    """A valid domain object cannot perform the requested transition."""
