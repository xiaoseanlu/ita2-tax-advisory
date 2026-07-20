"""SEP-IRA deterministic tools."""

from .sep_ira import (
    assess_applicability,
    assess_from_dict,
    estimate_savings,
    savings_from_dict,
)

__all__ = [
    "assess_applicability",
    "assess_from_dict",
    "estimate_savings",
    "savings_from_dict",
]
