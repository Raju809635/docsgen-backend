from __future__ import annotations

from fastapi import APIRouter

from models import GenerateImageRequest, GenerateImageResponse
from services.image_service import generate_image


router = APIRouter(tags=["images"])


@router.post("/generate-image", response_model=GenerateImageResponse)
def generate_image_route(payload: GenerateImageRequest) -> GenerateImageResponse:
    return GenerateImageResponse(
        **generate_image(
            prompt=payload.prompt,
            negative_prompt=payload.negative_prompt,
            width=payload.width,
            height=payload.height,
        )
    )
