"""Deterministic design planning for the governed AEGIS builder.

The planner turns a natural-language request into a small, inspectable brief.
It deliberately returns only allow-listed features. Generated files never use
planner output as executable code.
"""
from __future__ import annotations

from typing import Any

from .fabric import ActionError

SUPPORTED_FEATURES = (
    "contact_form",
    "booking",
    "quote_request",
    "newsletter",
    "faq",
    "calculator",
    "task_list",
)

FEATURE_LABELS = {
    "contact_form": "Contact capture",
    "booking": "Booking request",
    "quote_request": "Quote request",
    "newsletter": "Newsletter capture",
    "faq": "FAQ accordion",
    "calculator": "Interactive calculator",
    "task_list": "Local task list",
}

_KEYWORDS = {
    "contact_form": ("contact", "message", "inquiry", "enquire", "email us"),
    "booking": ("book", "booking", "appointment", "schedule", "reservation", "reserve"),
    "quote_request": ("quote", "estimate", "request pricing", "get a price"),
    "newsletter": ("newsletter", "subscribe", "updates", "mailing list"),
    "faq": ("faq", "frequently asked", "questions"),
    "calculator": ("calculator", "calculate", "estimate", "cost", "price"),
    "task_list": ("task", "todo", "to-do", "checklist", "track items"),
}


def _request_text(args: dict[str, Any]) -> str:
    values = [args.get("request"), args.get("title"), args.get("description")]
    return " ".join(str(value).strip().lower() for value in values if isinstance(value, str))


def normalize_features(args: dict[str, Any], *, kind: str | None = None) -> list[str]:
    """Validate explicit features, or infer conservative features from a request."""
    raw = args.get("features", args.get("feature", []))
    if isinstance(raw, str):
        raw = [item.strip() for item in raw.split(",") if item.strip()]
    if raw is None:
        raw = []
    if not isinstance(raw, (list, tuple)) or not all(isinstance(item, str) for item in raw):
        raise ActionError("features must be a list of feature names")

    explicit = [item.strip().lower().replace("-", "_") for item in raw if item.strip()]
    invalid = sorted(set(explicit) - set(SUPPORTED_FEATURES))
    if invalid:
        raise ActionError(f"unsupported features: {', '.join(invalid)}")
    if len(explicit) > len(SUPPORTED_FEATURES):
        raise ActionError("a project may use at most seven features")

    selected = list(dict.fromkeys(explicit))
    if not selected:
        text = _request_text(args)
        for feature in SUPPORTED_FEATURES:
            if any(keyword in text for keyword in _KEYWORDS[feature]):
                selected.append(feature)
    if kind == "app" and not selected:
        selected = ["task_list"]
    return selected


def design_brief(args: dict[str, Any], *, kind: str) -> dict[str, Any]:
    """Create a serializable brief used for generation and audit evidence."""
    features = normalize_features(args, kind=kind)
    layout = "utility" if kind == "app" else ("conversion" if features else "editorial")
    sections = ["hero"]
    if kind == "website":
        sections.extend(["proof", "about"])
    sections.extend(feature for feature in features if feature not in sections)
    sections.append("footer")
    return {
        "kind": kind,
        "layout": layout,
        "features": features,
        "feature_labels": [FEATURE_LABELS[feature] for feature in features],
        "sections": sections,
        "interaction_boundary": "local_browser_storage",
        "generated_by": "aegis-governed-design-planner",
    }
