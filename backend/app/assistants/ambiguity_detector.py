"""Ambiguity detection for analytical intent handling."""

from __future__ import annotations

from dataclasses import dataclass

from app.assistants.intent_mapper import IntentMatch


@dataclass(frozen=True, slots=True)
class AmbiguityResult:
    missing: list[str]


def detect_analytical_ambiguity(match: IntentMatch) -> AmbiguityResult | None:
    missing = [
        param
        for param in match.intent.required_parameters
        if match.parameters.get(param) in (None, "", [])
    ]
    if not missing:
        return None
    return AmbiguityResult(missing=missing)
