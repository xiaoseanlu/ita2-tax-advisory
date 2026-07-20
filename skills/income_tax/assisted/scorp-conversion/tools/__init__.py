"""S-Corp conversion tool package — Part 1 applicability, Part 2 savings."""

from .scorp_conversion import (
    ApplyScorpInput,
    BusinessActivityInput,
    RatesInput,
    apply_from_dict,
    apply_scorp_conversion,
    assess_applicability,
    assess_from_dict,
    estimate_scorp_savings,
    savings_from_dict,
    tool_spec,
)

__all__ = [
    "ApplyScorpInput",
    "BusinessActivityInput",
    "RatesInput",
    "apply_from_dict",
    "apply_scorp_conversion",
    "assess_applicability",
    "assess_from_dict",
    "estimate_scorp_savings",
    "savings_from_dict",
    "tool_spec",
]
