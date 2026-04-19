from __future__ import annotations

try:
    from graphviz import Source  # type: ignore
except Exception:  # noqa: BLE001
    Source = None  # type: ignore[assignment]


def render_dot_to_svg(dot: str) -> str:
    dot = (dot or "").strip()
    if not dot:
        raise ValueError("DOT input is empty.")
    if Source is None:
        raise RuntimeError(
            "Graphviz Python package is not installed. "
            "Create a venv and run `pip install -r backend/requirements.txt`."
        )
    svg_bytes = Source(dot).pipe(format="svg")
    return svg_bytes.decode("utf-8", errors="replace")
