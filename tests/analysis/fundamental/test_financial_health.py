from __future__ import annotations

import importlib.util
import sys
from datetime import date
from pathlib import Path


def _load_module():
    module_path = (
        Path(__file__).resolve().parents[3]
        / "app"
        / "analysis"
        / "fundamental"
        / "financial_health.py"
    )
    spec = importlib.util.spec_from_file_location("tradepilot_financial_health", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


financial_health = _load_module()


def _quarter(
    period_end: date,
    *,
    cash: float,
    short_debt: float,
    current_assets: float,
    current_liabilities: float,
    receivables: float,
    inventory: float,
    total_debt: float,
    cfo: float,
    capex: float,
    net_income: float,
    revenue: float,
    operating_income: float,
    interest_expense: float,
    da: float,
):
    return financial_health.FinancialQuarter(
        report_period_end=period_end,
        cash_and_equivalents=cash,
        short_term_debt=short_debt,
        current_assets=current_assets,
        current_liabilities=current_liabilities,
        accounts_receivable=receivables,
        inventory=inventory,
        total_debt=total_debt,
        operating_cash_flow=cfo,
        capital_expenditure=capex,
        net_income=net_income,
        revenue=revenue,
        operating_income=operating_income,
        interest_expense=interest_expense,
        depreciation_and_amortization=da,
    )


def test_financial_health_triggers_near_term_debt_coverage_failure():
    dataset = financial_health.FinancialHealthInput(
        analysis_date=date(2026, 4, 22),
        quarterly_results=(
            _quarter(
                date(2026, 3, 31),
                cash=80,
                short_debt=120,
                current_assets=210,
                current_liabilities=220,
                receivables=160,
                inventory=110,
                total_debt=400,
                cfo=30,
                capex=-10,
                net_income=20,
                revenue=600,
                operating_income=10,
                interest_expense=-12,
                da=6,
            ),
            _quarter(date(2025, 12, 31), cash=90, short_debt=130, current_assets=215, current_liabilities=210, receivables=150, inventory=105, total_debt=410, cfo=28, capex=-12, net_income=22, revenue=590, operating_income=12, interest_expense=-10, da=6),
            _quarter(date(2025, 9, 30), cash=95, short_debt=120, current_assets=220, current_liabilities=205, receivables=145, inventory=100, total_debt=415, cfo=26, capex=-11, net_income=24, revenue=575, operating_income=13, interest_expense=-9, da=5),
            _quarter(date(2025, 6, 30), cash=100, short_debt=115, current_assets=225, current_liabilities=200, receivables=140, inventory=98, total_debt=420, cfo=25, capex=-10, net_income=26, revenue=560, operating_income=14, interest_expense=-8, da=5),
            _quarter(date(2025, 3, 31), cash=110, short_debt=110, current_assets=230, current_liabilities=195, receivables=130, inventory=95, total_debt=425, cfo=24, capex=-10, net_income=25, revenue=540, operating_income=15, interest_expense=-8, da=5),
        ),
    )

    result = financial_health.analyze_financial_health(dataset)

    assert result.disqualify is True
    assert result.hard_risk_reasons == ("near_term_debt_coverage_failure",)
    assert result.overall_rating == "High"
    assert result.category_ratings["liquidity_pressure"] in {"Medium", "High"}
    assert result.category_ratings["leverage_pressure"] in {"Medium", "High"}


def test_financial_health_marks_high_without_disqualifying_on_quality_red_flags():
    dataset = financial_health.FinancialHealthInput(
        analysis_date=date(2026, 4, 22),
        quarterly_results=(
            _quarter(date(2026, 3, 31), cash=300, short_debt=100, current_assets=350, current_liabilities=200, receivables=220, inventory=190, total_debt=320, cfo=10, capex=-40, net_income=-5, revenue=520, operating_income=12, interest_expense=-3, da=8),
            _quarter(date(2025, 12, 31), cash=320, short_debt=100, current_assets=360, current_liabilities=210, receivables=205, inventory=175, total_debt=330, cfo=12, capex=-38, net_income=-4, revenue=500, operating_income=13, interest_expense=-3, da=8),
            _quarter(date(2025, 9, 30), cash=330, short_debt=95, current_assets=370, current_liabilities=215, receivables=190, inventory=160, total_debt=335, cfo=14, capex=-35, net_income=-3, revenue=490, operating_income=14, interest_expense=-3, da=8),
            _quarter(date(2025, 6, 30), cash=340, short_debt=95, current_assets=380, current_liabilities=220, receivables=180, inventory=150, total_debt=340, cfo=15, capex=-32, net_income=-2, revenue=480, operating_income=14, interest_expense=-3, da=8),
            _quarter(date(2025, 3, 31), cash=350, short_debt=90, current_assets=390, current_liabilities=225, receivables=120, inventory=100, total_debt=345, cfo=16, capex=-30, net_income=-1, revenue=470, operating_income=15, interest_expense=-3, da=8),
        ),
    )

    result = financial_health.analyze_financial_health(dataset)

    assert result.disqualify is False
    assert result.overall_rating == "High"
    assert result.hard_risk_reasons == ()
    assert "earnings_quality" in result.red_flag_categories
    assert result.health_score < 60


def test_financial_health_suppresses_disqualify_when_data_is_stale():
    dataset = financial_health.FinancialHealthInput(
        analysis_date=date(2026, 9, 1),
        quarterly_results=(
            _quarter(date(2026, 3, 31), cash=50, short_debt=120, current_assets=100, current_liabilities=130, receivables=140, inventory=120, total_debt=420, cfo=-30, capex=-15, net_income=-20, revenue=500, operating_income=8, interest_expense=-12, da=5),
            _quarter(date(2025, 12, 31), cash=55, short_debt=115, current_assets=105, current_liabilities=125, receivables=135, inventory=118, total_debt=425, cfo=-28, capex=-14, net_income=-18, revenue=495, operating_income=9, interest_expense=-11, da=5),
            _quarter(date(2025, 9, 30), cash=60, short_debt=110, current_assets=110, current_liabilities=120, receivables=130, inventory=116, total_debt=430, cfo=-20, capex=-12, net_income=-16, revenue=490, operating_income=10, interest_expense=-10, da=5),
            _quarter(date(2025, 6, 30), cash=65, short_debt=105, current_assets=115, current_liabilities=118, receivables=125, inventory=112, total_debt=435, cfo=-15, capex=-10, net_income=-14, revenue=485, operating_income=11, interest_expense=-10, da=5),
            _quarter(date(2025, 3, 31), cash=70, short_debt=100, current_assets=120, current_liabilities=116, receivables=120, inventory=108, total_debt=440, cfo=-10, capex=-9, net_income=-12, revenue=480, operating_income=12, interest_expense=-9, da=5),
        ),
    )

    result = financial_health.analyze_financial_health(dataset)

    assert result.data_staleness_days > 120
    assert result.disqualify is False
    assert result.hard_risk_reasons == ()
    assert result.overall_rating == "High"
    assert "financial_health_data_stale" in result.warnings
