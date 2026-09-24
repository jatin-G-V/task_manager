from typing import Optional, Literal

from pydantic import BaseModel, model_validator


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

    effort: Optional[Literal["low", "medium", "high"]] = None
    urgency: Optional[Literal["low", "medium", "high"]] = None

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

    effort: Optional[Literal["low", "medium", "high"]] = None
    urgency: Optional[Literal["low", "medium", "high"]] = None

    status: Optional[
        Literal["pending", "in_progress", "completed", "blocked"]
    ] = None