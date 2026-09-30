"""HTTP intent DTOs, not Game Engine domain models."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class IntentModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class MoveDistribution(IntentModel):
    rock: Annotated[int, Field(ge=0, le=100)]
    paper: Annotated[int, Field(ge=0, le=100)]
    scissors: Annotated[int, Field(ge=0, le=100)]

    @model_validator(mode="after")
    def must_total_one_hundred(self) -> "MoveDistribution":
        if self.rock + self.paper + self.scissors != 100:
            raise ValueError("Each distribution must total 100.")
        return self


class StrategyIntent(IntentModel):
    """All ten server-validated distributions specified by the product core."""

    initial: MoveDistribution
    lost_to_rock: MoveDistribution
    lost_to_paper: MoveDistribution
    lost_to_scissors: MoveDistribution
    won_against_rock: MoveDistribution
    won_against_paper: MoveDistribution
    won_against_scissors: MoveDistribution
    tied_with_rock: MoveDistribution
    tied_with_paper: MoveDistribution
    tied_with_scissors: MoveDistribution


class CreateTournamentIntent(IntentModel):
    capacity: Annotated[int, Field(ge=1)]
    hearts_required: Annotated[int, Field(ge=1)]
    sound_effects_enabled: bool = True
    background_music_enabled: bool = True
    movement_speed: Literal["0.5", "1", "2", "4", "8"] = "1"
    countdown_speed: Literal["0.5", "1", "2", "4", "8"] = "1"


class JoinTournamentIntent(IntentModel):
    tournament_code: Annotated[str, Field(min_length=4, max_length=32)]
    display_name: Annotated[str, Field(min_length=1, max_length=80)]
    animal_id: Annotated[str, Field(pattern=r"^[a-z0-9][a-z0-9_-]{0,63}$")]

    @field_validator("tournament_code")
    @classmethod
    def normalize_code(cls, value: str) -> str:
        return value.strip().upper()

    @field_validator("display_name")
    @classmethod
    def normalize_display_name(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if not normalized:
            raise ValueError("Display name cannot be blank.")
        return normalized


class TournamentConfigurationIntent(IntentModel):
    capacity: Annotated[int, Field(ge=1)]
    hearts_required: Annotated[int, Field(ge=1)]
    sound_effects_enabled: bool = True
    background_music_enabled: bool = True
    movement_speed: Literal["0.5", "1", "2", "4", "8"] = "1"
    countdown_speed: Literal["0.5", "1", "2", "4", "8"] = "1"


class EmptyIntent(IntentModel):
    """Explicitly rejects forged official state on bodyless commands."""


class TrainingChoiceIntent(IntentModel):
    move: Annotated[str, Field(pattern=r"^(rock|paper|scissors)$")]
