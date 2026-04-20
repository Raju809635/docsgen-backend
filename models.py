from __future__ import annotations

from datetime import datetime

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


class GenerateImageRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=2_000)
    negative_prompt: str = Field(default="", max_length=2_000)
    width: int = Field(default=1024, ge=256, le=1536)
    height: int = Field(default=768, ge=256, le=1536)


class GenerateImageResponse(BaseModel):
    prompt: str
    model: str
    mime_type: str
    image_data_url: str


class VideoSceneItem(BaseModel):
    scene_number: int
    title: str
    narration: str
    image_prompt: str
    duration_seconds: int
    image_data_url: str = ""


class GenerateVideoRequest(BaseModel):
    story: str = Field(min_length=1, max_length=20_000)
    scene_count: int = Field(default=4, ge=1, le=8)
    clip_duration_seconds: int = Field(default=3, ge=1, le=8)
    width: int = Field(default=768, ge=320, le=1280)
    height: int = Field(default=432, ge=240, le=1280)


class GenerateVideoResponse(BaseModel):
    title: str
    summary: str
    pipeline: str
    mime_type: str
    captions: list[str] = Field(default_factory=list)
    scenes: list[VideoSceneItem] = Field(default_factory=list)
    video_data_url: str


class SubmitVideoJobRequest(BaseModel):
    story: str = Field(min_length=1, max_length=20_000)
    scene_count: int = Field(default=4, ge=1, le=8)
    clip_duration_seconds: int = Field(default=3, ge=1, le=8)
    width: int = Field(default=768, ge=320, le=1280)
    height: int = Field(default=432, ge=240, le=1280)


class VideoJobScene(BaseModel):
    scene_number: int
    title: str
    narration: str
    image_prompt: str = ""
    image_url: str = ""


class VideoJob(BaseModel):
    job_id: str
    status: str
    story: str
    scene_count: int
    clip_duration_seconds: int
    width: int
    height: int
    provider: str = "colab"
    title: str = ""
    summary: str = ""
    video_url: str = ""
    error: str = ""
    captions: list[str] = Field(default_factory=list)
    scenes: list[VideoJobScene] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class VideoJobListResponse(BaseModel):
    jobs: list[VideoJob] = Field(default_factory=list)


class UpdateVideoJobRequest(BaseModel):
    status: str = Field(pattern="^(processing|completed|failed)$")
    title: str = ""
    summary: str = ""
    video_url: str = ""
    error: str = ""
    captions: list[str] = Field(default_factory=list)
    scenes: list[VideoJobScene] = Field(default_factory=list)
