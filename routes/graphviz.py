from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from services.graphviz_service import render_dot_to_svg


router = APIRouter()


class GraphvizRequest(BaseModel):
    dot: str = Field(min_length=1, max_length=200_000)


class GraphvizResponse(BaseModel):
    svg: str | None = None
    error: str | None = None


@router.post("/render-graphviz", response_model=GraphvizResponse)
def post_render_graphviz(body: GraphvizRequest) -> GraphvizResponse:
    try:
        return GraphvizResponse(svg=render_dot_to_svg(body.dot))
    except Exception as exc:  # noqa: BLE001
        # Keep a 200 response for UX; the frontend displays `error`.
        return GraphvizResponse(
            svg=None,
            error=(
                "Graphviz rendering failed. Ensure Graphviz is installed and `dot` is on PATH. "
                f"Details: {exc}"
            ),
        )
