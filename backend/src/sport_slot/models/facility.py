import datetime
import re

from pydantic import BaseModel, field_validator, model_validator

_TIME = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


class FacilityBase(BaseModel):
    name: str
    sport: str
    slot_duration_minutes: int
    open_time: str
    close_time: str
    active: bool = True

    @field_validator("open_time", "close_time")
    @classmethod
    def _hhmm(cls, v: str) -> str:
        if not _TIME.match(v):
            raise ValueError("time must be HH:MM (24h)")
        return v

    @field_validator("slot_duration_minutes")
    @classmethod
    def _duration(cls, v: int) -> int:
        if not 15 <= v <= 240:
            raise ValueError("slot_duration_minutes must be 15–240")
        return v

    @model_validator(mode="after")
    def _window(self):
        if self.open_time >= self.close_time:
            raise ValueError("open_time must be before close_time")
        return self


class FacilityCreate(FacilityBase):
    pass


class FacilityUpdate(BaseModel):
    name: str | None = None
    slot_duration_minutes: int | None = None
    open_time: str | None = None
    close_time: str | None = None
    active: bool | None = None


class Facility(FacilityBase):
    id: str
    created_at: datetime.datetime
