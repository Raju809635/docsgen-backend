from __future__ import annotations

import base64
import io
import re
import tempfile
from typing import Any

import imageio.v2 as imageio
import numpy as np
from fastapi import HTTPException
from PIL import Image

from models import GenerateVideoResponse
from services.image_service import generate_image
from services.openai_service import _extract_json_candidate, _openai_client
from services.prompt import VIDEO_PROMPT_TEMPLATE, VIDEO_SYSTEM_INSTRUCTIONS
from config import settings


VIDEO_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "summary": {"type": "string"},
        "scenes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "scene_number": {"type": "integer"},
                    "title": {"type": "string"},
                    "narration": {"type": "string"},
                    "image_prompt": {"type": "string"},
                },
                "required": ["scene_number", "title", "narration", "image_prompt"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["title", "summary", "scenes"],
    "additionalProperties": False,
}


def _split_story_into_scenes(story: str, scene_count: int) -> list[str]:
    parts = [part.strip() for part in re.split(r"[.\n]+", story) if len(part.strip()) > 12]
    if not parts:
        parts = [story.strip()]
    return parts[:scene_count]


def _fallback_video_plan(story: str, scene_count: int) -> dict[str, Any]:
    scenes = _split_story_into_scenes(story, scene_count)
    title = "AI Video Storyboard"
    summary = "A scene-by-scene storyboard derived from the provided story."
    return {
        "title": title,
        "summary": summary,
        "scenes": [
            {
                "scene_number": index,
                "title": f"Scene {index}",
                "narration": scene,
                "image_prompt": (
                    "Cinematic frame, polished lighting, high detail, storytelling composition: "
                    + scene
                ),
            }
            for index, scene in enumerate(scenes, start=1)
        ],
    }


def _plan_video(story: str, scene_count: int, clip_duration_seconds: int) -> dict[str, Any]:
    if not settings.llm_api_key:
        return _fallback_video_plan(story, scene_count)

    client = _openai_client()
    prompt = VIDEO_PROMPT_TEMPLATE.format(
        story=story,
        scene_count=scene_count,
        clip_duration_seconds=clip_duration_seconds,
    )

    try:
        completion = client.chat.completions.create(
            model=settings.llm_model,
            messages=[
                {
                    "role": "system",
                    "content": VIDEO_SYSTEM_INSTRUCTIONS
                    + "\nReturn JSON only that matches the schema exactly."
                    + "\nDo not wrap the JSON in markdown fences.",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.4,
            response_format={"type": "json_object"},
        )
        content = (completion.choices[0].message.content or "").strip()
        data = _extract_json_candidate(content)
        if not isinstance(data.get("scenes"), list) or not data["scenes"]:
            return _fallback_video_plan(story, scene_count)
        return data
    except Exception:
        return _fallback_video_plan(story, scene_count)


def _data_url_to_frame(image_data_url: str, width: int, height: int) -> np.ndarray:
    _, encoded = image_data_url.split(",", 1)
    image_bytes = base64.b64decode(encoded)
    pil_image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    pil_image = pil_image.resize((width, height))
    return np.array(pil_image).astype(np.uint8)


def _build_video_data_url(scene_images: list[str], width: int, height: int, clip_duration_seconds: int) -> str:
    fps = 8
    still_frames = max(8, clip_duration_seconds * fps)
    transition_frames = 6

    frames: list[np.ndarray] = []
    prepared_frames = [_data_url_to_frame(item, width, height) for item in scene_images if item]

    if not prepared_frames:
        raise HTTPException(status_code=500, detail="No scene frames were available to render the video.")

    for index, frame in enumerate(prepared_frames):
        frames.extend([frame] * still_frames)
        if index < len(prepared_frames) - 1:
            next_frame = prepared_frames[index + 1]
            for blend_index in range(1, transition_frames + 1):
                alpha = blend_index / (transition_frames + 1)
                blended = ((1 - alpha) * frame + alpha * next_frame).astype(np.uint8)
                frames.append(blended)

    with tempfile.NamedTemporaryFile(suffix=".mp4") as temp_file:
        with imageio.get_writer(temp_file.name, fps=fps, codec="libx264") as writer:
            for frame in frames:
                writer.append_data(frame)
        temp_file.seek(0)
        video_bytes = temp_file.read()

    encoded = base64.b64encode(video_bytes).decode("utf-8")
    return f"data:video/mp4;base64,{encoded}"


def generate_video(
    story: str,
    scene_count: int,
    clip_duration_seconds: int,
    width: int,
    height: int,
) -> GenerateVideoResponse:
    if not settings.hf_api_key:
        raise HTTPException(status_code=500, detail="Hugging Face API key is not configured.")

    plan = _plan_video(story, scene_count, clip_duration_seconds)
    raw_scenes = plan.get("scenes", [])[:scene_count]

    scenes: list[dict[str, Any]] = []
    image_data_urls: list[str] = []
    captions: list[str] = []

    for index, scene in enumerate(raw_scenes, start=1):
        narration = str(scene.get("narration", "")).strip()
        image_prompt = str(scene.get("image_prompt", "")).strip() or narration or story
        image_payload = generate_image(
            prompt=image_prompt,
            negative_prompt="blurry, distorted, watermark, low quality, extra limbs, unreadable text",
            width=width,
            height=height,
        )
        image_data_url = image_payload["image_data_url"]
        image_data_urls.append(image_data_url)
        captions.append(narration)
        scenes.append(
            {
                "scene_number": index,
                "title": str(scene.get("title", "")).strip() or f"Scene {index}",
                "narration": narration or f"Scene {index} narration.",
                "image_prompt": image_prompt,
                "duration_seconds": clip_duration_seconds,
                "image_data_url": image_data_url,
            }
        )

    if not scenes:
        raise HTTPException(status_code=500, detail="Video planning produced no scenes.")

    video_data_url = _build_video_data_url(
        image_data_urls,
        width=width,
        height=height,
        clip_duration_seconds=clip_duration_seconds,
    )

    return GenerateVideoResponse(
        title=str(plan.get("title", "")).strip() or "AI Video Storyboard",
        summary=str(plan.get("summary", "")).strip() or "Generated video storyboard.",
        pipeline="Story -> Scenes -> Image Prompts -> Scene Images -> Stitched MP4",
        mime_type="video/mp4",
        captions=captions,
        scenes=scenes,
        video_data_url=video_data_url,
    )
