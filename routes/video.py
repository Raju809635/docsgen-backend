from __future__ import annotations

from fastapi import APIRouter, HTTPException

from models import GenerateVideoRequest, GenerateVideoResponse
from services.video_service import generate_video


router = APIRouter(tags=["video"])


@router.post("/generate-video", response_model=GenerateVideoResponse)
def generate_video_route(payload: GenerateVideoRequest) -> GenerateVideoResponse:
    try:
        return generate_video(
            story=payload.story,
            scene_count=payload.scene_count,
            clip_duration_seconds=payload.clip_duration_seconds,
            width=payload.width,
            height=payload.height,
        )
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Video generation failed: {exc}") from exc
