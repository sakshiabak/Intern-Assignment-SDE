import re
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app import geo

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class Industry(str, Enum):
    mining = "mining"
    infrastructure = "infrastructure"
    energy = "energy"
    utilities = "utilities"


class SurveyStatus(str, Enum):
    planned = "planned"
    flying = "flying"
    processing = "processing"
    completed = "completed"


# ---------- auth ----------
class UserCreate(BaseModel):
    email: str
    password: str = Field(min_length=8, max_length=128)

    @field_validator("email")
    @classmethod
    def check_email(cls, v: str) -> str:
        v = v.strip().lower()
        if not EMAIL_RE.match(v):
            raise ValueError("invalid email address")
        return v


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    email: str
    created_at: datetime


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


# ---------- projects ----------
class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    industry: Industry = Industry.mining
    description: str | None = None


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    industry: Industry | None = None
    description: str | None = None


class ProjectOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    industry: str
    description: str | None
    created_at: datetime


# ---------- surveys ----------
class SurveyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    status: SurveyStatus = SurveyStatus.planned
    captured_at: datetime | None = None
    image_count: int = Field(default=0, ge=0)
    area: dict = Field(description="GeoJSON Polygon, coordinates as [lon, lat]")

    @field_validator("area")
    @classmethod
    def check_area(cls, v: dict) -> dict:
        geo.validate_polygon(v)
        return v


class SurveyUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    status: SurveyStatus | None = None
    captured_at: datetime | None = None
    image_count: int | None = Field(default=None, ge=0)


class SurveyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    project_id: int
    name: str
    status: str
    captured_at: datetime | None
    image_count: int
    area_sq_km: float
    area: dict
    created_at: datetime


class Page(BaseModel):
    total: int
    limit: int
    offset: int
    items: list[SurveyOut]


class ProjectStats(BaseModel):
    project_id: int
    survey_count: int
    total_area_sq_km: float
    total_images: int
    by_status: dict[str, int]
