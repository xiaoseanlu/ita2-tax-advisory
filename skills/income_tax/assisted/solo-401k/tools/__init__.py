"""Solo 401(k) contribution tool package — Part 1 applicability, Part 2 savings."""

from .solo_401k import (
    AssessInput,
    EstimateInput,
    PersonInput,
    RatesInput,
    RetirementBaseline,
    assess_applicability,
    assess_from_dict,
    compute_employee_headroom,
    estimate_savings,
    savings_from_dict,
)

__all__ = [
    "AssessInput",
    "EstimateInput",
    "PersonInput",
    "RatesInput",
    "RetirementBaseline",
    "assess_applicability",
    "assess_from_dict",
    "compute_employee_headroom",
    "estimate_savings",
    "savings_from_dict",
]
