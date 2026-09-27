"""Explainability Engine — Structured Decision Graph from Snapshot.

Usage:
    from core_engine.explainability import build_explanation, explain_to_text

    exp = build_explanation(snapshot)
    text = explain_to_text(exp, detailed=True)
    print(text)
"""

from .engine import build_explanation
from .models import Explanation, Reason, Evidence, Warning_, Invalidation, Breakdown
from .reason_codes import ReasonCode
from .confidence import compute_confidence
from .invalidation import build_invalidations
from .formatter import explain_to_text, explain_to_dict

__all__ = [
    "build_explanation",
    "explain_to_text",
    "explain_to_dict",
    "Explanation",
    "Reason",
    "Evidence",
    "Warning_",
    "Invalidation",
    "Breakdown",
    "ReasonCode",
    "compute_confidence",
    "build_invalidations",
]
