from typing import Optional, Literal

from pydantic import BaseModel, Field, model_validator


class TaskCreate(BaseModel):
    title: str
    section: Literal["work", "personal", "leisure"]
    brief: Optional[str] = None

    schedule_type: Literal["flexible", "scheduled"] = "flexible"
    deadline: Optional[str] = None
    scheduled_start: Optional[str] = None
    scheduled_end: Optional[str] = None
    has_explicit_time: Optional[bool] = None

    is_recurring: bool = False
    recurrence: Optional[str] = None
    recurrence_end: Optional[str] = None

    duration: Optional[int] = Field(default=None, gt=0)
    estimated_time_minutes: Optional[int] = Field(default=None, gt=0)
    is_blocked: bool = False

    effort: Optional[Literal["low", "medium", "high"]] = None
    urgency: Optional[Literal["low", "medium", "high", "urgent"]] = None

    source_type: Literal["text", "voice", "screenshot"] = "text"

    @model_validator(mode="after")
    def check_schedule(self):
        if self.schedule_type == "scheduled":
            if not self.scheduled_start:
                raise ValueError(
                    "scheduled task requires scheduled_start"
                )

            if self.deadline is not None:
                raise ValueError(
                    "scheduled task cannot have deadline"
                )

        else:
            if self.scheduled_start or self.scheduled_end:
                raise ValueError(
                    "flexible task cannot have scheduled_start/end"
                )

        if self.duration is not None:
            if self.estimated_time_minutes not in (None, self.duration):
                raise ValueError(
                    "estimated_time_minutes must equal duration when duration is provided."
                )
            self.estimated_time_minutes = self.duration

        if not self.is_recurring and (self.recurrence or self.recurrence_end):
            raise ValueError(
                "recurrence and recurrence_end require is_recurring=true."
            )

        return self


class TaskUpdate(BaseModel):
    title: Optional[str] = None
    section: Optional[Literal["work", "personal", "leisure"]] = None
    brief: Optional[str] = None

    schedule_type: Optional[Literal["flexible", "scheduled"]] = None
    deadline: Optional[str] = None
    scheduled_start: Optional[str] = None
    scheduled_end: Optional[str] = None
    has_explicit_time: Optional[bool] = None

    is_recurring: Optional[bool] = None
    recurrence: Optional[str] = None
    recurrence_end: Optional[str] = None

    duration: Optional[int] = Field(default=None, gt=0)
    estimated_time_minutes: Optional[int] = Field(default=None, gt=0)
    is_blocked: Optional[bool] = None

    effort: Optional[Literal["low", "medium", "high"]] = None
    urgency: Optional[Literal["low", "medium", "high", "urgent"]] = None

    status: Optional[
        Literal["pending", "in_progress", "completed", "blocked"]
    ] = None
