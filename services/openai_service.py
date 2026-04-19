from __future__ import annotations

import json
import re
from typing import Any

try:
    # openai>=1.x
    from openai import OpenAI  # type: ignore
except Exception:  # noqa: BLE001
    OpenAI = None  # type: ignore[assignment]

from config import settings
from models import DocsResponse
from services.prompt import SYSTEM_INSTRUCTIONS, USER_PROMPT_TEMPLATE


DOCS_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "overview": {"type": "string"},
        "workflow": {"type": "string"},
        "diagram": {"type": "string"},
        "technical": {"type": "string"},
        "use_cases": {"type": "string"},
        "sections": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "content": {"type": "string"},
                },
                "required": ["title", "content"],
                "additionalProperties": False,
            },
        },
        "diagrams": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "type": {"type": "string"},
                    "code": {"type": "string"},
                    "summary": {"type": "string"},
                },
                "required": ["title", "type", "code", "summary"],
                "additionalProperties": False,
            },
        },
        "pages": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "sections": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "title": {"type": "string"},
                                "content": {"type": "string"},
                            },
                            "required": ["title", "content"],
                            "additionalProperties": False,
                        },
                    },
                },
                "required": ["title", "sections"],
                "additionalProperties": False,
            },
        },
    },
    "required": [
        "title",
        "overview",
        "workflow",
        "diagram",
        "technical",
        "use_cases",
        "sections",
        "diagrams",
        "pages",
    ],
    "additionalProperties": False,
}


def _openai_client():
    if OpenAI is None:
        raise RuntimeError(
            "Your installed `openai` package is too old. "
            "Create a venv and run `pip install -r requirements.txt`."
        )
    return OpenAI(api_key=settings.llm_api_key, base_url=settings.llm_base_url)


def _strip_code_fences(text: str) -> str:
    t = (text or "").strip()
    if not t.startswith("```"):
        return t
    lines = [ln for ln in t.splitlines() if not ln.strip().startswith("```")]
    return "\n".join(lines).strip()


def _ensure_colorful_mermaid(code: str) -> str:
    c = _strip_code_fences(code)
    c = re.sub(r"^%%\{init:.*?%%\s*", "", c, flags=re.DOTALL)
    if not c:
        c = (
            "flowchart LR\n"
            "  A[Input]:::in --> B{Validate}:::dec\n"
            "  B -->|OK| C[Generate Docs JSON]:::ai --> D[Export PDF/HTML]:::out\n"
            "  B -->|Fix| A\n"
            "  classDef in fill:#0b1220,stroke:#38bdf8,color:#e2e8f0,stroke-width:2px;\n"
            "  classDef ai fill:#111827,stroke:#a78bfa,color:#e2e8f0,stroke-width:2px;\n"
            "  classDef out fill:#0f172a,stroke:#34d399,color:#e2e8f0,stroke-width:2px;\n"
            "  classDef dec fill:#0b1220,stroke:#f59e0b,color:#e2e8f0,stroke-width:2px;\n"
            "  linkStyle 0 stroke:#38bdf8,stroke-width:2px;\n"
            "  linkStyle 1 stroke:#a78bfa,stroke-width:2px;\n"
            "  linkStyle 2 stroke:#34d399,stroke-width:2px;\n"
        )
    if "flowchart" not in c and "sequenceDiagram" not in c and "graph" not in c:
        c = "flowchart LR\n" + c
    if "classDef" not in c:
        c += (
            "\n\n"
            "classDef in fill:#0b1220,stroke:#38bdf8,color:#e2e8f0,stroke-width:2px;\n"
            "classDef ai fill:#111827,stroke:#a78bfa,color:#e2e8f0,stroke-width:2px;\n"
            "classDef out fill:#0f172a,stroke:#34d399,color:#e2e8f0,stroke-width:2px;\n"
        )
    if "%%{init:" not in c:
        c = (
            "%%{init: {\"theme\":\"dark\",\"themeVariables\":{"
            "\"primaryColor\":\"#0b1220\",\"primaryTextColor\":\"#e2e8f0\","
            "\"primaryBorderColor\":\"#38bdf8\",\"lineColor\":\"#94a3b8\","
            "\"tertiaryColor\":\"#111827\"}}}%%\n"
            + c
        )
    return c.strip()


def _normalize_graphviz(code: str) -> str:
    c = _strip_code_fences(code)
    if c.startswith("digraph") or c.startswith("graph"):
        return c.strip()
    return (
        "digraph G {\n"
        "  rankdir=LR;\n"
        "  node [shape=box, style=\"rounded,filled\", fillcolor=\"#0b1220\", color=\"#38bdf8\", fontcolor=\"#e2e8f0\"];\n"
        "  edge [color=\"#94a3b8\"];\n"
        "  Input -> Processing -> Output;\n"
        "}\n"
    )


def _coerce_sections(data: dict[str, Any]) -> list[dict[str, str]]:
    sections = data.get("sections")
    if isinstance(sections, list) and sections:
        return [
            {
                "title": str(item.get("title", "")).strip() or "Section",
                "content": str(item.get("content", "")).strip(),
            }
            for item in sections
            if isinstance(item, dict)
        ]

    return [
        {"title": "Overview", "content": str(data.get("overview", "")).strip()},
        {"title": "Workflow", "content": str(data.get("workflow", "")).strip()},
        {"title": "Technical Breakdown", "content": str(data.get("technical", "")).strip()},
        {"title": "Use Cases", "content": str(data.get("use_cases", "")).strip()},
    ]


def _coerce_diagrams(data: dict[str, Any]) -> list[dict[str, str]]:
    diagrams = data.get("diagrams")
    normalized: list[dict[str, str]] = []

    if isinstance(diagrams, list):
        for item in diagrams:
            if not isinstance(item, dict):
                continue
            diagram_type = str(item.get("type", "mermaid")).strip().lower() or "mermaid"
            code = str(item.get("code", "")).strip()
            if diagram_type == "graphviz":
                code = _normalize_graphviz(code)
            else:
                diagram_type = "mermaid"
                code = _ensure_colorful_mermaid(code)
            normalized.append(
                {
                    "title": str(item.get("title", "Diagram")).strip() or "Diagram",
                    "type": diagram_type,
                    "code": code,
                    "summary": str(item.get("summary", "")).strip(),
                }
            )

    if not normalized:
        normalized = [
            {
                "title": "Primary Workflow",
                "type": "mermaid",
                "code": _ensure_colorful_mermaid(str(data.get("diagram", ""))),
                "summary": "High-level system flow.",
            }
        ]

    if not any(item["type"] == "mermaid" for item in normalized):
        normalized.insert(
            0,
            {
                "title": "Primary Workflow",
                "type": "mermaid",
                "code": _ensure_colorful_mermaid(str(data.get("diagram", ""))),
                "summary": "High-level system flow.",
            },
        )

    return normalized


def _coerce_pages(
    data: dict[str, Any],
    sections: list[dict[str, str]],
    requested_page_count: int,
) -> list[dict[str, Any]]:
    pages = data.get("pages")
    if isinstance(pages, list) and pages:
        normalized_pages: list[dict[str, Any]] = []
        for page in pages:
            if not isinstance(page, dict):
                continue
            page_sections = page.get("sections")
            normalized_page_sections = []
            if isinstance(page_sections, list):
                for section in page_sections:
                    if isinstance(section, dict):
                        normalized_page_sections.append(
                            {
                                "title": str(section.get("title", "")).strip() or "Section",
                                "content": str(section.get("content", "")).strip(),
                            }
                        )
            normalized_pages.append(
                {
                    "title": str(page.get("title", "")).strip() or "Documentation Page",
                    "sections": normalized_page_sections,
                }
            )
        if normalized_pages:
            if len(normalized_pages) > requested_page_count:
                return normalized_pages[:requested_page_count]
            return normalized_pages

    if not sections:
        sections = [{"title": "Overview", "content": str(data.get("overview", "")).strip()}]

    page_count = max(1, min(requested_page_count, 50))
    page_count = min(page_count, max(1, len(sections)))
    pages: list[dict[str, Any]] = []
    section_count = len(sections)

    for page_index in range(page_count):
        start = (page_index * section_count) // page_count
        end = ((page_index + 1) * section_count) // page_count
        chunk = sections[start:end]
        if not chunk:
            source = sections[min(page_index, section_count - 1)]
            chunk = [source]
        pages.append(
            {
                "title": f"Documentation Page {page_index + 1}",
                "sections": chunk,
            }
        )

    return pages


def _normalize_docs_payload(data: dict[str, Any], requested_page_count: int) -> dict[str, Any]:
    sections = _coerce_sections(data)
    diagrams = _coerce_diagrams(data)
    pages = _coerce_pages(data, sections, requested_page_count)

    data["sections"] = sections
    data["diagrams"] = diagrams
    data["pages"] = pages
    data["diagram"] = next(
        (item["code"] for item in diagrams if item["type"] == "mermaid"),
        _ensure_colorful_mermaid(str(data.get("diagram", ""))),
    )
    return data


def _parse_json(output_text: str) -> dict[str, Any]:
    return json.loads((output_text or "").strip())


def _extract_json_candidate(output_text: str) -> dict[str, Any]:
    text = (output_text or "").strip()
    if not text:
        raise ValueError("Model returned an empty response.")

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    stripped = _strip_code_fences(text)
    if stripped != text:
        try:
            return json.loads(stripped)
        except json.JSONDecodeError:
            pass

    match = re.search(r"\{.*\}", stripped, re.DOTALL)
    if match:
        return json.loads(match.group(0))

    raise ValueError("Model did not return valid JSON.")


def generate_docs(user_input: str, page_count: int = 5) -> DocsResponse:
    if not settings.llm_api_key:
        raise RuntimeError("GROQ_API_KEY is not set.")

    client = _openai_client()
    requested_page_count = max(1, min(page_count, 50))
    prompt = USER_PROMPT_TEMPLATE.format(
        user_input=user_input,
        page_count=requested_page_count,
    )

    # Prefer Structured Outputs via json_schema; fall back to JSON mode if unsupported.
    # Note: Groq supports Structured Outputs on Chat Completions (not the OpenAI Responses API).
    if settings.llm_use_json_schema:
        try:
            completion = client.chat.completions.create(
                model=settings.llm_model,
                messages=[
                    {"role": "system", "content": SYSTEM_INSTRUCTIONS},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.2,
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": "ai_docs",
                        "strict": False,
                        "schema": DOCS_SCHEMA,
                    },
                },
            )
            content = (completion.choices[0].message.content or "").strip()
            data = _extract_json_candidate(content)
            data = _normalize_docs_payload(data, requested_page_count)
            return DocsResponse.model_validate(data)
        except Exception:
            pass

    last_error: Exception | None = None
    retry_input = prompt
    for _ in range(3):
        try:
            completion = client.chat.completions.create(
                model=settings.llm_model,
                messages=[
                    {
                        "role": "system",
                        "content": SYSTEM_INSTRUCTIONS
                        + "\nReturn JSON only that matches the schema exactly."
                        + "\nDo not wrap the JSON in markdown fences."
                        + "\nDo not include any explanatory text before or after the JSON.",
                    },
                    {"role": "user", "content": retry_input},
                ],
                temperature=0.2,
                response_format={"type": "json_object"},
            )
            content = (completion.choices[0].message.content or "").strip()
            data = _extract_json_candidate(content)
            data = _normalize_docs_payload(data, requested_page_count)
            return DocsResponse.model_validate(data)
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            retry_input += (
                "\n\nIMPORTANT: Your last response was invalid. Return JSON matching the schema exactly."
            )

    assert last_error is not None
    raise last_error
