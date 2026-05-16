from typing import Literal

from pydantic import BaseModel, Field


class PhotoRecord(BaseModel):
    id: str = Field(..., min_length=1, examples=["PHOTO-001"])
    latitude: str = Field(..., min_length=1, examples=["48.2082"])
    longitude: str = Field(..., min_length=1, examples=["16.3719"])
    image_name: str = Field(..., min_length=1, examples=["wall_crack_01.png"])
    category: str = Field(..., min_length=1, examples=["wall_crack"])
    status: str = Field(..., min_length=1, examples=["detected"])


class PhotoListResponse(BaseModel):
    photos: list[PhotoRecord]


class EvaluationFinding(BaseModel):
    severity: Literal["info", "low", "medium", "high"]
    target: str = Field(
        ...,
        min_length=1,
        description="Logical pointer to the report field, e.g. 'issues[ISS-001].severity' or 'executive_summary'.",
    )
    message: str = Field(..., min_length=1)


class ReportEvaluation(BaseModel):
    overall_score: int = Field(..., ge=0, le=100)
    summary: str = Field(..., min_length=1)
    findings: list[EvaluationFinding] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
