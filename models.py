from __future__ import annotations

from pydantic import BaseModel, Field


class GenerateDocsRequest(BaseModel):
    text: str = Field(min_length=1, max_length=200_000)
    page_count: int = Field(default=5, ge=1, le=50)


class PreviewPagesRequest(BaseModel):
    text: str = Field(min_length=1, max_length=200_000)
    page_count: int = Field(default=5, ge=1, le=50)


class PreviewPageItem(BaseModel):
    page_number: int
    title: str
    summary: str
    sections: list[str] = Field(default_factory=list)


class PreviewPagesResponse(BaseModel):
    title: str
    summary: str
    pages: list[PreviewPageItem] = Field(default_factory=list)


class DiagramItem(BaseModel):
    title: str
    type: str = Field(description="Expected values: mermaid or graphviz")
    code: str
    summary: str


class DocSection(BaseModel):
    title: str
    content: str


class DocPage(BaseModel):
    title: str
    sections: list[DocSection]


class DocsResponse(BaseModel):
    title: str
    overview: str
    workflow: str
    diagram: str
    technical: str
    use_cases: str
    sections: list[DocSection] = Field(default_factory=list)
    diagrams: list[DiagramItem] = Field(default_factory=list)
    pages: list[DocPage] = Field(default_factory=list)
