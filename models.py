from __future__ import annotations

from pydantic import BaseModel, Field


class GenerateDocsRequest(BaseModel):
    text: str = Field(min_length=1, max_length=200_000)


class DocsResponse(BaseModel):
    title: str
    overview: str
    workflow: str
    diagram: str
    technical: str
    use_cases: str

