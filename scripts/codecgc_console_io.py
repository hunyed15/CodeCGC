from __future__ import annotations

import json
import sys
from typing import Any


def configure_utf8_stdio() -> None:
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if stream is None:
            continue
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass


def print_json(payload: dict[str, Any], *, file: Any | None = None) -> None:
    target = file or sys.stdout
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    target.write(text)
    target.write("\n")


def render_summary_block(title: str, base_lines: list[str], next_actions: list[str]) -> str:
    lines = [title, *base_lines]
    unique_actions: list[str] = []
    seen: set[str] = set()
    for item in next_actions:
        normalized = str(item).strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        unique_actions.append(normalized)

    if unique_actions:
        lines.append(f"- 下一步: {unique_actions[0]}")
        for item in unique_actions[1:]:
            lines.append(f"- 备选动作: {item}")
    else:
        lines.append("- 下一步: 无")
    return "\n".join(lines)
