from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field, field_validator


class RecommendationRequest(BaseModel):
    query: str = Field(default='', max_length=600)
    latitude: float = Field(ge=-90, le=90, allow_inf_nan=False)
    longitude: float = Field(ge=-180, le=180, allow_inf_nan=False)
    minutes: int = Field(default=60, ge=15, le=180)
    radius_m: int = Field(default=2500, ge=100, le=10000)
    interests: list[Literal['park', 'cafe', 'museum', 'gallery', 'attraction', 'playground', 'viewpoint', 'public_space']] = Field(default_factory=list, max_length=8)
    with_child: bool = False
    accessible_only: bool = False
    open_now: bool = False
    sockets_required: bool = False
    return_to_start: bool = False
    language: Literal['ru'] = 'ru'
    starts_at: datetime | None = None

    @field_validator('starts_at')
    @classmethod
    def aware_datetime(cls, value):
        if value and value.tzinfo is None:
            raise ValueError('starts_at must include a timezone offset')
        return value


class GeneratedItem(BaseModel):
    poi_id: str
    reason: str = Field(max_length=300)
    fact_refs: list[str] = Field(max_length=8)
    suggested_activity: str = Field(max_length=300)
    visit_minutes: int = Field(ge=5, le=120)


class GeneratedResponse(BaseModel):
    recommendations: list[GeneratedItem] = Field(max_length=3)
