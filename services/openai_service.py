from __future__ import annotations

import json
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
    },
    "required": ["title", "overview", "workflow", "diagram", "technical", "use_cases"],
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


def _parse_json(output_text: str) -> dict[str, Any]:
    return json.loads((output_text or "").strip())


def generate_docs(user_input: str) -> DocsResponse:
    if not settings.llm_api_key:
        raise RuntimeError("GROQ_API_KEY is not set.")

    client = _openai_client()
    prompt = USER_PROMPT_TEMPLATE.format(user_input=user_input)

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
            data = _parse_json(content)
            data["diagram"] = _ensure_colorful_mermaid(data.get("diagram", ""))
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
                        + "\nReturn JSON only that matches the schema exactly.",
                    },
                    {"role": "user", "content": retry_input},
                ],
                response_format={"type": "json_object"},
            )
            content = (completion.choices[0].message.content or "").strip()
            data = _parse_json(content)
            data["diagram"] = _ensure_colorful_mermaid(data.get("diagram", ""))
            return DocsResponse.model_validate(data)
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            retry_input += (
                "\n\nIMPORTANT: Your last response was invalid. Return JSON matching the schema exactly."
            )

    assert last_error is not None
    raise last_error
