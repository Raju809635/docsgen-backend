from __future__ import annotations

from fastapi import APIRouter, HTTPException

from models import DocsResponse, GenerateDocsRequest, PreviewPagesRequest, PreviewPagesResponse
from services.openai_service import generate_docs, preview_pages

router = APIRouter()


@router.post("/generate-docs", response_model=DocsResponse)
def post_generate_docs(body: GenerateDocsRequest) -> DocsResponse:
    try:
        return generate_docs(body.text, body.page_count)
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Generation failed: {exc}") from exc


@router.post("/preview-pages", response_model=PreviewPagesResponse)
def post_preview_pages(body: PreviewPagesRequest) -> PreviewPagesResponse:
    try:
        return preview_pages(body.text, body.page_count)
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Preview failed: {exc}") from exc
