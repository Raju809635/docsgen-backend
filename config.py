from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


load_dotenv()


def _truthy(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


@dataclass(frozen=True)
class Settings:
    # Groq (preferred). OpenAI env fallbacks kept for compatibility.
    llm_api_key: str | None = os.getenv("GROQ_API_KEY") or os.getenv("OPENAI_API_KEY")
    llm_model: str = os.getenv("GROQ_MODEL", os.getenv("OPENAI_MODEL", "llama-3.3-70b-versatile"))
    llm_base_url: str = os.getenv(
        "GROQ_BASE_URL",
        os.getenv("OPENAI_BASE_URL", "https://api.groq.com/openai/v1"),
    )
    llm_use_json_schema: bool = _truthy(
        os.getenv("GROQ_USE_JSON_SCHEMA"),
        _truthy(os.getenv("OPENAI_USE_JSON_SCHEMA"), False),
    )
    hf_api_key: str | None = os.getenv("HUGGINGFACE_API_KEY")
    hf_image_model: str = os.getenv(
        "HUGGINGFACE_IMAGE_MODEL",
        "black-forest-labs/FLUX.1-schnell",
    )
    video_worker_token: str | None = os.getenv("VIDEO_WORKER_TOKEN")
    frontend_origin: str = os.getenv("FRONTEND_ORIGIN", "http://localhost:5173")


settings = Settings()
