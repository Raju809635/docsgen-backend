from __future__ import annotations

from fastapi import APIRouter, HTTPException

from models import DocsResponse, GenerateDocsRequest
from services.openai_service import generate_docs

router = APIRouter()


@router.post("/generate-docs", response_model=DocsResponse)
def post_generate_docs(body: GenerateDocsRequest) -> DocsResponse:
    try:
        return generate_docs(body.text)
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Generation failed: {exc}") from exc
