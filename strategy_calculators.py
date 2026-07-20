"""
Strategy Calculators - Backend calculation logic for tax strategies.
Ported from ita-tax-savings-ai. Each calculator is isolated, testable, and maintainable.
"""


class StrategyCalculator:
    """Base class for all strategy calculators"""

    def __init__(self, strategy_id):
        self.strategy_id = strategy_id

    def calculate(self, inputs):
        """
        Calculate tax savings based on inputs
        Returns: dict with 'savings', 'breakdown', and 'warnings'
        """
        raise NotImplementedError("Subclasses must implement calculate()")


class BonusDepreciationCalculator(StrategyCalculator):
    """Calculator for Bonus Depreciation (ita_025)"""

    def __init__(self):
        super().__init__("ita_025")

    def calculate(self, inputs):
        equipment_cost = float(inputs.get("equipment_cost", 0))
        bonus_percentage = float(inputs.get("bonus_percentage", 100))
        tax_rate = float(inputs.get("tax_rate", 0.24))

        deductible_amount = equipment_cost * (bonus_percentage / 100)
        tax_savings = deductible_amount * tax_rate

        breakdown = {
            "equipment_cost": equipment_cost,
            "bonus_percentage": bonus_percentage,
            "deductible_amount": deductible_amount,
            "tax_rate": tax_rate,
            "tax_savings": tax_savings,
        }

        return {
            "savings": tax_savings,
            "breakdown": breakdown,
            "warnings": [],
            "display": {
                "main": f"${int(tax_savings):,}",
                "details": [
                    f"Equipment Cost: ${int(equipment_cost):,}",
                    f"Bonus %: {int(bonus_percentage)}%",
                    f"Deductible Amount: ${int(deductible_amount):,}",
                    "",
                    f"<strong>Tax Savings ({int(tax_rate * 100)}% rate):</strong> ${int(tax_savings):,}",
                ],
            },
        }


class SCorpConversionCalculator(StrategyCalculator):
    """Calculator for S-Corp Conversion (ita_002)"""

    def __init__(self):
        super().__init__("ita_002")

    def calculate(self, inputs):
        schedule_c_income = float(inputs.get("schedule_c_income", 0))
        comp_percentage = float(inputs.get("comp_percentage", 40))
        reasonable_comp = schedule_c_income * (comp_percentage / 100)
        distribution_income = schedule_c_income - reasonable_comp
        se_tax_rate = 0.153
        se_tax_savings = distribution_income * se_tax_rate
        qbi_reduction_cost = reasonable_comp * 0.04
        payroll_costs = 2000

        return {
            "savings": se_tax_savings,
            "breakdown": {
                "schedule_c_income": schedule_c_income,
                "comp_percentage": comp_percentage,
                "reasonable_comp": reasonable_comp,
                "distribution_income": distribution_income,
                "se_tax_savings": se_tax_savings,
                "qbi_reduction_cost": qbi_reduction_cost,
                "payroll_costs": payroll_costs,
            },
            "warnings": [],
            "display": {
                "main": f"${int(se_tax_savings):,}",
                "details": [
                    f"Schedule C Income: ${int(schedule_c_income):,}",
                    f"W-2 Salary ({int(comp_percentage)}%): ${int(reasonable_comp):,}",
                    f"Distribution Income: ${int(distribution_income):,}",
                    "",
                    f"<strong>SE Tax Avoided (15.3%):</strong> ${int(se_tax_savings):,}",
                    "",
                    f"<em>Note: Actual savings may vary due to QBI deduction changes (~${int(qbi_reduction_cost):,}) and payroll costs (~${int(payroll_costs):,})</em>",
                ],
            },
        }


class HireYourKidsCalculator(StrategyCalculator):
    """Calculator for Hire Your Kids (ita_020)"""

    def __init__(self):
        super().__init__("ita_020")

    def calculate(self, inputs):
        num_children = int(inputs.get("num_children", 1))
        wages_per_child = float(inputs.get("wages_per_child", 12000))
        parent_tax_rate = float(inputs.get("parent_tax_rate", 0.24))
        total_wages = num_children * wages_per_child
        fica_savings = total_wages * 0.153
        standard_deduction = 15000
        taxable_to_child = max(0, wages_per_child - standard_deduction)
        child_tax = taxable_to_child * 0.10 * num_children
        parent_tax_savings = total_wages * parent_tax_rate
        income_shift_savings = parent_tax_savings - child_tax
        total_savings = fica_savings + income_shift_savings

        return {
            "savings": total_savings,
            "breakdown": {"total_wages": total_wages, "fica_savings": fica_savings},
            "warnings": [],
            "display": {"main": f"${int(total_savings):,}"},
        }


class Solo401kCalculator(StrategyCalculator):
    """Calculator for Solo 401k (ita_044)"""

    def __init__(self):
        super().__init__("ita_044")

    def calculate(self, inputs):
        se_income = float(inputs.get("se_income", 100000))
        employee_deferral = float(inputs.get("employee_deferral", 23500))
        employer_contribution = float(inputs.get("employer_contribution", 10000))
        tax_rate = float(inputs.get("tax_rate", 0.24))
        total_contribution = employee_deferral + employer_contribution
        tax_savings = total_contribution * tax_rate

        return {
            "savings": tax_savings,
            "breakdown": {"total_contribution": total_contribution},
            "warnings": [],
            "display": {"main": f"${int(tax_savings):,}"},
        }


class AugustaRuleCalculator(StrategyCalculator):
    """Calculator for Augusta Rule (ita_018)"""

    def __init__(self):
        super().__init__("ita_018")

    def calculate(self, inputs):
        rental_days = min(int(inputs.get("rental_days", 14)), 14)
        daily_rate = float(inputs.get("daily_rate", 500))
        tax_rate = float(inputs.get("tax_rate", 0.24))
        total_rental_income = rental_days * daily_rate
        tax_savings = total_rental_income * tax_rate

        return {
            "savings": total_rental_income,
            "breakdown": {"total_rental_income": total_rental_income},
            "warnings": [],
            "display": {"main": f"${int(total_rental_income):,}"},
        }


class TravelDeductionCalculator(StrategyCalculator):
    """Calculator for Combined Business/Personal Travel (ita_010)"""

    def __init__(self):
        super().__init__("ita_010")

    def calculate(self, inputs):
        total_days = int(inputs.get("total_days", 7))
        business_days = int(inputs.get("business_days", 5))
        transportation_cost = float(inputs.get("transportation_cost", 500))
        daily_lodging_meals = float(inputs.get("daily_lodging_meals", 200))
        tax_rate = float(inputs.get("tax_rate", 0.24))
        primary_purpose_business = business_days > (total_days - business_days)
        deductible_transportation = transportation_cost if primary_purpose_business else 0
        deductible_lodging_meals = daily_lodging_meals * business_days * 0.5
        total_deduction = deductible_transportation + deductible_lodging_meals
        tax_savings = total_deduction * tax_rate

        return {
            "savings": tax_savings,
            "breakdown": {"total_deduction": total_deduction},
            "warnings": [],
            "display": {"main": f"${int(tax_savings):,}"},
        }


class MERPCalculator(StrategyCalculator):
    """Calculator for Medical Expense Reimbursement Plan (ita_016)"""

    def __init__(self):
        super().__init__("ita_016")

    def calculate(self, inputs):
        annual_medical_expenses = float(inputs.get("annual_medical_expenses", 10000))
        tax_rate = float(inputs.get("tax_rate", 0.24))
        include_se_tax = inputs.get("include_se_tax", False)
        income_tax_savings = annual_medical_expenses * tax_rate
        se_savings = annual_medical_expenses * 0.153 if include_se_tax else 0
        total_savings = income_tax_savings + se_savings

        return {
            "savings": total_savings,
            "breakdown": {"annual_medical_expenses": annual_medical_expenses},
            "warnings": [],
            "display": {"main": f"${int(total_savings):,}"},
        }


CALCULATORS = {
    "ita_002": SCorpConversionCalculator,
    "ita_010": TravelDeductionCalculator,
    "ita_016": MERPCalculator,
    "ita_018": AugustaRuleCalculator,
    "ita_020": HireYourKidsCalculator,
    "ita_025": BonusDepreciationCalculator,
    "ita_044": Solo401kCalculator,
}


def get_calculator(strategy_id):
    """Factory function to get the appropriate calculator."""
    calculator_class = CALCULATORS.get(strategy_id)
    if calculator_class:
        return calculator_class()
    return None


def calculate_strategy_savings(strategy_id, inputs):
    """
    Main entry point for strategy calculations.

    Args:
        strategy_id: Strategy identifier (e.g., 'ita_025')
        inputs: Dict of input values

    Returns:
        Dict with calculation results or error
    """
    calculator = get_calculator(strategy_id)
    if not calculator:
        return {"error": f"Calculator not available for strategy {strategy_id}", "savings": 0}
    try:
        return calculator.calculate(inputs)
    except Exception as e:
        return {"error": f"Calculation error: {str(e)}", "savings": 0}
