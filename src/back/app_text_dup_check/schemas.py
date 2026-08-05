# src/back/app_text_dup_check/schemas.py
from pydantic import BaseModel, Field
from typing import List


class TextSaveRequest(BaseModel):
    """Схема для сохранения нового текста."""
    text: str = Field(..., min_length=1, max_length=10000, description="Текст для сохранения")
    code: str = Field(..., min_length=1, max_length=50, description="Код текста")
    model_config = {"from_attributes": True, "extra": "ignore"}


class MatchResult(BaseModel):
    """Результат поиска дубликата (для ответа /check)."""
    percentage: float = Field(..., ge=0.0, le=100.0)
    matched_text: str = Field(...)
    matched_code: str = Field(...)


class SimilarityResponse(BaseModel):
    pg_trgm: List[MatchResult] = Field(default_factory=list)
    sequence: List[MatchResult] = Field(default_factory=list)
    jaccard: List[MatchResult] = Field(default_factory=list)
    cosine: List[MatchResult] = Field(default_factory=list)
