from __future__ import annotations


INTERNAL_TO_PUBLIC_COMMAND = {
    "cgc-plan": "cgc-plan",
    "cgc-build": "cgc-build",
    "cgc-fix": "cgc-fix",
    "cgc-test": "cgc-test",
    "cgc-review": "cgc-review",
    "cgc-route": "cgc-route",
}

PUBLIC_TO_INTERNAL_COMMAND = {value: key for key, value in INTERNAL_TO_PUBLIC_COMMAND.items()}


def to_public_command(command: str) -> str:
    normalized = str(command or "").strip()
    return INTERNAL_TO_PUBLIC_COMMAND.get(normalized, normalized)


def to_internal_command(command: str) -> str:
    normalized = str(command or "").strip()
    return PUBLIC_TO_INTERNAL_COMMAND.get(normalized, normalized)


def matches_command(command: str, *aliases: str) -> bool:
    normalized = to_internal_command(command)
    return normalized in {to_internal_command(alias) for alias in aliases}
