from __future__ import annotations

import base64
import io

from fastapi import HTTPException
from huggingface_hub import InferenceClient
from PIL import Image

from config import settings


def _to_png_bytes(image: Image.Image) -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def generate_image(prompt: str, negative_prompt: str, width: int, height: int) -> dict:
    if not settings.hf_api_key:
        raise HTTPException(status_code=500, detail="Hugging Face API key is not configured.")

    client = InferenceClient(api_key=settings.hf_api_key)

    try:
        image = client.text_to_image(
            prompt=prompt,
            negative_prompt=negative_prompt or None,
            model=settings.hf_image_model,
            width=width,
            height=height,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Image generation failed: {exc}") from exc

    png_bytes = _to_png_bytes(image)
    encoded = base64.b64encode(png_bytes).decode("utf-8")

    return {
        "prompt": prompt,
        "model": settings.hf_image_model,
        "mime_type": "image/png",
        "image_data_url": f"data:image/png;base64,{encoded}",
    }
