"""Randomness boundary for deterministic tests and server-side production use."""

from __future__ import annotations

import math
import secrets
from typing import Protocol

from .errors import EngineValidationError


class RandomSource(Protocol):
    """Return a finite value in the half-open interval [0, 1)."""

    def random(self) -> float: ...


class SystemRandomSource:
    """Production source intended to be instantiated only by trusted server code."""

    def __init__(self) -> None:
        self._random = secrets.SystemRandom()

    def random(self) -> float:
        return self._random.random()


def draw_unit_interval(random_source: RandomSource) -> float:
    random_method = getattr(random_source, "random", None)
    if not callable(random_method):
        raise EngineValidationError(
            "random.invalid_source",
            "Random sources must provide a callable random method.",
        )
    value = random_method()
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise EngineValidationError(
            "random.invalid_type",
            "Random sources must return a numeric value.",
        )
    normalized = float(value)
    if not math.isfinite(normalized) or normalized < 0.0 or normalized >= 1.0:
        raise EngineValidationError(
            "random.out_of_range",
            "Random sources must return a finite value in [0, 1).",
        )
    return normalized


def draw_index(size: int, random_source: RandomSource) -> int:
    if isinstance(size, bool) or not isinstance(size, int) or size <= 0:
        raise EngineValidationError(
            "random.invalid_population_size",
            "Population size must be a positive integer.",
        )
    return int(draw_unit_interval(random_source) * size)
