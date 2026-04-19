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
from models import DocsResponse, PreviewPagesResponse
from services.prompt import (
    PREVIEW_PROMPT_TEMPLATE,
    PREVIEW_SYSTEM_INSTRUCTIONS,
    SYSTEM_INSTRUCTIONS,
    USER_PROMPT_TEMPLATE,
)


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

PREVIEW_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "summary": {"type": "string"},
        "pages": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "page_number": {"type": "integer"},
                    "title": {"type": "string"},
                    "summary": {"type": "string"},
                    "sections": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
                "required": ["page_number", "title", "summary", "sections"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["title", "summary", "pages"],
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


def _looks_like_diagram_section(title: str, content: str) -> bool:
    normalized_title = title.strip().lower()
    normalized_content = content.strip().lower()
    if "diagram" in normalized_title or "mermaid" in normalized_title or "graphviz" in normalized_title:
        return True
    if normalized_content.startswith("flowchart ") or normalized_content.startswith("sequencediagram"):
        return True
    if normalized_content.startswith("graph ") or normalized_content.startswith("digraph "):
        return True
    return "classdef " in normalized_content or "linkstyle " in normalized_content


def _coerce_sections(data: dict[str, Any]) -> list[dict[str, str]]:
    sections = data.get("sections")
    if isinstance(sections, list) and sections:
        normalized_sections = []
        for item in sections:
            if not isinstance(item, dict):
                continue
            title = str(item.get("title", "")).strip() or "Section"
            content = str(item.get("content", "")).strip()
            if not content:
                continue
            if _looks_like_diagram_section(title, content):
                continue
            normalized_sections.append({"title": title, "content": content})
        if normalized_sections:
            return normalized_sections

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
                        title = str(section.get("title", "")).strip() or "Section"
                        content = str(section.get("content", "")).strip()
                        if not content:
                            continue
                        if _looks_like_diagram_section(title, content):
                            continue
                        normalized_page_sections.append(
                            {
                                "title": title,
                                "content": content,
                            }
                        )
            if not normalized_page_sections:
                continue
            normalized_pages.append(
                {
                    "title": str(page.get("title", "")).strip() or "Documentation Page",
                    "sections": normalized_page_sections,
                }
            )
        if normalized_pages:
            if len(normalized_pages) > requested_page_count:
                normalized_pages = normalized_pages[:requested_page_count]
            return _merge_sparse_pages(normalized_pages)

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

    return _merge_sparse_pages(pages)


def _section_weight(section: dict[str, str]) -> int:
    title = str(section.get("title", "")).strip()
    content = str(section.get("content", "")).strip()
    return len(title) + len(content)


def _page_weight(page: dict[str, Any]) -> int:
    return sum(_section_weight(section) for section in page.get("sections", []))


def _merge_sparse_pages(pages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not pages:
        return pages

    min_page_weight = 900
    min_sections = 2
    merged_pages: list[dict[str, Any]] = []

    for page in pages:
        current_sections = [
            section
            for section in page.get("sections", [])
            if str(section.get("content", "")).strip()
        ]
        if not current_sections:
            continue

        candidate = {
            "title": str(page.get("title", "")).strip() or "Documentation Page",
            "sections": current_sections,
        }

        if not merged_pages:
            merged_pages.append(candidate)
            continue

        if _page_weight(candidate) < min_page_weight or len(current_sections) < min_sections:
            merged_pages[-1]["sections"].extend(current_sections)
            continue

        merged_pages.append(candidate)

    return [
        {
            "title": f"Documentation Page {index}",
            "sections": page["sections"],
        }
        for index, page in enumerate(merged_pages, start=1)
    ]


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


def _normalize_preview_payload(data: dict[str, Any], requested_page_count: int) -> dict[str, Any]:
    pages = data.get("pages")
    normalized_pages: list[dict[str, Any]] = []

    if isinstance(pages, list):
        for index, page in enumerate(pages[:requested_page_count], start=1):
            if not isinstance(page, dict):
                continue
            sections = page.get("sections")
            normalized_sections = []
            if isinstance(sections, list):
                for section in sections:
                    section_text = str(section).strip()
                    if section_text:
                        normalized_sections.append(section_text)
            if not normalized_sections:
                normalized_sections = ["Overview", "Key concepts"]
            summary = str(page.get("summary", "")).strip()
            if not summary:
                summary = "Planned content for this page."
            normalized_pages.append(
                {
                    "page_number": index,
                    "title": str(page.get("title", "")).strip() or f"Page {index}",
                    "summary": summary,
                    "sections": normalized_sections[:5],
                }
            )

    if not normalized_pages:
        page_total = max(1, min(requested_page_count, 50))
        normalized_pages = [
            {
                "page_number": index,
                "title": f"Page {index}",
                "summary": "Planned documentation content.",
                "sections": ["Overview", "Key details"],
            }
            for index in range(1, page_total + 1)
        ]

    data["title"] = str(data.get("title", "")).strip() or "Documentation Plan"
    data["summary"] = str(data.get("summary", "")).strip() or "Page-wise documentation preview."
    data["pages"] = normalized_pages
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


def preview_pages(user_input: str, page_count: int = 5) -> PreviewPagesResponse:
    if not settings.llm_api_key:
        raise RuntimeError("GROQ_API_KEY is not set.")

    client = _openai_client()
    requested_page_count = max(1, min(page_count, 50))
    prompt = PREVIEW_PROMPT_TEMPLATE.format(
        user_input=user_input,
        page_count=requested_page_count,
    )

    last_error: Exception | None = None
    retry_input = prompt
    for _ in range(3):
        try:
            completion = client.chat.completions.create(
                model=settings.llm_model,
                messages=[
                    {
                        "role": "system",
                        "content": PREVIEW_SYSTEM_INSTRUCTIONS
                        + "\nReturn JSON only that matches the schema exactly."
                        + "\nDo not wrap the JSON in markdown fences.",
                    },
                    {"role": "user", "content": retry_input},
                ],
                temperature=0.2,
                response_format={"type": "json_object"},
            )
            content = (completion.choices[0].message.content or "").strip()
            data = _extract_json_candidate(content)
            data = _normalize_preview_payload(data, requested_page_count)
            return PreviewPagesResponse.model_validate(data)
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            retry_input += (
                "\n\nIMPORTANT: Return valid JSON matching the required preview schema exactly."
            )

    assert last_error is not None
    raise last_error
