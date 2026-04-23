from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Literal

HealthStatus = Literal["pass", "warning", "fail", "unavailable"]
HealthRating = Literal["Low", "Medium", "High"]
HealthCategory = Literal[
    "cashflow_quality",
    "liquidity_pressure",
    "earnings_quality",
    "leverage_pressure",
]
HardRiskReason = Literal[
    "near_term_debt_coverage_failure",
    "cash_burn_against_short_term_debt",
    "working_capital_crunch",
]


@dataclass(frozen=True)
class Threshold:
    pass_gte: float | None = None
    warning_gte: float | None = None
    warning_lte: float | None = None
    fail_lt: float | None = None
    fail_gt: float | None = None


@dataclass(frozen=True)
class FinancialQuarter:
    report_period_end: date
    cash_and_equivalents: float | None = None
    short_term_debt: float | None = None
    current_assets: float | None = None
    current_liabilities: float | None = None
    accounts_receivable: float | None = None
    inventory: float | None = None
    total_debt: float | None = None
    operating_cash_flow: float | None = None
    capital_expenditure: float | None = None
    net_income: float | None = None
    revenue: float | None = None
    operating_income: float | None = None
    interest_expense: float | None = None
    depreciation_and_amortization: float | None = None
    source: str = "standardized_financial_snapshot"


@dataclass(frozen=True)
class FinancialHealthInput:
    analysis_date: date
    quarterly_results: tuple[FinancialQuarter, ...]
    missing_fields: tuple[str, ...] = ()


@dataclass(frozen=True)
class HealthCheckItem:
    category: HealthCategory
    name: str
    status: HealthStatus
    value: float | int | None
    unit: str | None
    threshold: Threshold
    window: Literal["latest_quarter", "ttm", "latest_2q", "latest_q_vs_4q_ago"]
    hard_risk_candidate: bool
    reason: str
    source: str
    as_of_date: str


@dataclass(frozen=True)
class FinancialHealthResult:
    overall_rating: HealthRating
    disqualify: bool
    hard_risk_reasons: tuple[HardRiskReason, ...]
    category_ratings: dict[HealthCategory, HealthRating]
    red_flag_categories: tuple[HealthCategory, ...]
    checks: tuple[HealthCheckItem, ...]
    health_score: int
    data_staleness_days: int | None
    missing_fields: tuple[str, ...]
    low_confidence: bool
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class _MetricValue:
    status: HealthStatus
    value: float | int | None
    reason: str
    source: str
    as_of_date: str


def analyze_financial_health(dataset: FinancialHealthInput) -> FinancialHealthResult:
    quarters = tuple(
        sorted(dataset.quarterly_results, key=lambda item: item.report_period_end, reverse=True)
    )
    missing_fields = set(dataset.missing_fields)
    warnings: list[str] = []

    if not quarters:
        warnings.append("financial_health_input_missing_quarters")
        return FinancialHealthResult(
            overall_rating="Low",
            disqualify=False,
            hard_risk_reasons=(),
            category_ratings={
                "cashflow_quality": "Low",
                "liquidity_pressure": "Low",
                "earnings_quality": "Low",
                "leverage_pressure": "Low",
            },
            red_flag_categories=(),
            checks=(),
            health_score=50,
            data_staleness_days=None,
            missing_fields=tuple(sorted(missing_fields | {"quarterly_results"})),
            low_confidence=True,
            warnings=tuple(warnings),
        )

    latest = quarters[0]
    latest_date = latest.report_period_end
    data_staleness_days = (dataset.analysis_date - latest_date).days
    ttm_quarters = quarters[:4]
    quality_quarters = quarters[:5]

    def mark_missing(group: str, condition: bool) -> None:
        if condition:
            missing_fields.add(group)

    def require_values(rows: tuple[FinancialQuarter, ...], field_name: str) -> list[float] | None:
        values: list[float] = []
        for row in rows:
            value = getattr(row, field_name)
            if value is None:
                return None
            values.append(float(value))
        return values

    fcf_latest_two = _fcf_series(quarters[:2], missing_fields)
    cfo_latest_two = require_values(quarters[:2], "operating_cash_flow")
    if cfo_latest_two is None and len(quarters) >= 2:
        mark_missing("cfo_latest_2q", True)

    fcf_negative_streak = _negative_streak(fcf_latest_two)
    cfo_negative_streak = _negative_streak(cfo_latest_two)

    cfo_ttm_values = require_values(ttm_quarters, "operating_cash_flow") if len(ttm_quarters) == 4 else None
    capex_ttm_values = require_values(ttm_quarters, "capital_expenditure") if len(ttm_quarters) == 4 else None
    net_income_ttm_values = require_values(ttm_quarters, "net_income") if len(ttm_quarters) == 4 else None
    operating_income_ttm_values = (
        require_values(ttm_quarters, "operating_income") if len(ttm_quarters) == 4 else None
    )
    interest_expense_ttm_values = (
        require_values(ttm_quarters, "interest_expense") if len(ttm_quarters) == 4 else None
    )
    da_ttm_values = (
        require_values(ttm_quarters, "depreciation_and_amortization") if len(ttm_quarters) == 4 else None
    )
    mark_missing("ttm_cashflow_core", cfo_ttm_values is None or capex_ttm_values is None)
    mark_missing("ttm_income_core", net_income_ttm_values is None or operating_income_ttm_values is None)
    mark_missing("ttm_leverage_core", interest_expense_ttm_values is None or da_ttm_values is None)

    cfo_ttm = sum(cfo_ttm_values) if cfo_ttm_values is not None else None
    fcf_ttm = (
        cfo_ttm - sum(abs(value) for value in capex_ttm_values)
        if cfo_ttm is not None and capex_ttm_values is not None
        else None
    )
    net_income_ttm = sum(net_income_ttm_values) if net_income_ttm_values is not None else None
    operating_income_ttm = (
        sum(operating_income_ttm_values) if operating_income_ttm_values is not None else None
    )
    interest_expense_ttm = (
        sum(abs(value) for value in interest_expense_ttm_values)
        if interest_expense_ttm_values is not None
        else None
    )
    ebitda_ttm = (
        operating_income_ttm + sum(da_ttm_values)
        if operating_income_ttm is not None and da_ttm_values is not None
        else None
    )

    fcf_to_net_income = _ratio_metric(
        numerator=fcf_ttm,
        denominator=net_income_ttm,
        pass_gte=0.80,
        warning_gte=0.50,
        fail_lt=0.50,
        unavailable_reason="net_income_ttm_non_positive",
        unavailable_when_denominator_non_positive=True,
        source=latest.source,
        as_of_date=latest_date.isoformat(),
        missing_group="fcf_to_net_income",
        missing_fields=missing_fields,
    )
    cfo_to_net_income = _ratio_metric(
        numerator=cfo_ttm,
        denominator=net_income_ttm,
        pass_gte=0.90,
        warning_gte=0.60,
        fail_lt=0.60,
        unavailable_reason="net_income_ttm_non_positive",
        unavailable_when_denominator_non_positive=True,
        source=latest.source,
        as_of_date=latest_date.isoformat(),
        missing_group="cfo_to_net_income",
        missing_fields=missing_fields,
    )
    cash_to_short_term_debt = _latest_ratio_metric(
        numerator=latest.cash_and_equivalents,
        denominator=latest.short_term_debt,
        pass_gte=1.50,
        warning_gte=1.00,
        fail_lt=1.00,
        zero_denominator_status="pass",
        zero_denominator_reason="no_short_term_debt",
        source=latest.source,
        as_of_date=latest_date.isoformat(),
        missing_group="cash_to_short_term_debt",
        missing_fields=missing_fields,
    )
    current_ratio = _latest_ratio_metric(
        numerator=latest.current_assets,
        denominator=latest.current_liabilities,
        pass_gte=1.20,
        warning_gte=1.00,
        fail_lt=1.00,
        zero_denominator_status="unavailable",
        zero_denominator_reason="current_liabilities_non_positive",
        source=latest.source,
        as_of_date=latest_date.isoformat(),
        missing_group="current_ratio",
        missing_fields=missing_fields,
    )
    interest_coverage = _interest_coverage_metric(
        latest_total_debt=latest.total_debt,
        operating_income_ttm=operating_income_ttm,
        interest_expense_ttm=interest_expense_ttm,
        source=latest.source,
        as_of_date=latest_date.isoformat(),
        missing_fields=missing_fields,
    )
    net_debt_to_ebitda = _net_debt_to_ebitda_metric(
        total_debt=latest.total_debt,
        cash=latest.cash_and_equivalents,
        ebitda_ttm=ebitda_ttm,
        source=latest.source,
        as_of_date=latest_date.isoformat(),
        missing_fields=missing_fields,
    )
    receivables_gap = _growth_gap_metric(
        rows=quality_quarters,
        subject_field="accounts_receivable",
        revenue_field="revenue",
        warning_gt=10.0,
        fail_gt=25.0,
        missing_group="receivables_growth_gap_pp",
        missing_fields=missing_fields,
        source=latest.source,
        as_of_date=latest_date.isoformat(),
    )
    inventory_gap = _growth_gap_metric(
        rows=quality_quarters,
        subject_field="inventory",
        revenue_field="revenue",
        warning_gt=15.0,
        fail_gt=30.0,
        missing_group="inventory_growth_gap_pp",
        missing_fields=missing_fields,
        source=latest.source,
        as_of_date=latest_date.isoformat(),
    )

    fcf_negative_streak_metric = _streak_metric(
        streak=fcf_negative_streak,
        pass_value=0,
        warning_value=1,
        fail_value=2,
        unavailable_reason="latest_2q_fcf_missing",
        source=latest.source,
        as_of_date=latest_date.isoformat(),
    )
    cfo_negative_streak_metric = _streak_metric(
        streak=cfo_negative_streak,
        pass_value=0,
        warning_value=1,
        fail_value=2,
        unavailable_reason="latest_2q_cfo_missing",
        source=latest.source,
        as_of_date=latest_date.isoformat(),
    )
    if fcf_negative_streak is None:
        mark_missing("fcf_negative_streak_2q", True)
    if cfo_negative_streak is None:
        mark_missing("cfo_negative_streak_2q", True)

    checks = (
        HealthCheckItem(
            category="cashflow_quality",
            name="fcf_to_net_income",
            status=fcf_to_net_income.status,
            value=_round_value(fcf_to_net_income.value),
            unit="ratio",
            threshold=Threshold(pass_gte=0.80, warning_gte=0.50, warning_lte=0.79, fail_lt=0.50),
            window="ttm",
            hard_risk_candidate=False,
            reason=fcf_to_net_income.reason,
            source=fcf_to_net_income.source,
            as_of_date=fcf_to_net_income.as_of_date,
        ),
        HealthCheckItem(
            category="cashflow_quality",
            name="cfo_to_net_income",
            status=cfo_to_net_income.status,
            value=_round_value(cfo_to_net_income.value),
            unit="ratio",
            threshold=Threshold(pass_gte=0.90, warning_gte=0.60, warning_lte=0.89, fail_lt=0.60),
            window="ttm",
            hard_risk_candidate=False,
            reason=cfo_to_net_income.reason,
            source=cfo_to_net_income.source,
            as_of_date=cfo_to_net_income.as_of_date,
        ),
        HealthCheckItem(
            category="cashflow_quality",
            name="fcf_negative_streak_2q",
            status=fcf_negative_streak_metric.status,
            value=fcf_negative_streak_metric.value,
            unit="quarters",
            threshold=Threshold(pass_gte=0, warning_gte=1, warning_lte=1, fail_gt=1),
            window="latest_2q",
            hard_risk_candidate=True,
            reason=fcf_negative_streak_metric.reason,
            source=fcf_negative_streak_metric.source,
            as_of_date=fcf_negative_streak_metric.as_of_date,
        ),
        HealthCheckItem(
            category="liquidity_pressure",
            name="cash_to_short_term_debt",
            status=cash_to_short_term_debt.status,
            value=_round_value(cash_to_short_term_debt.value),
            unit="ratio",
            threshold=Threshold(pass_gte=1.50, warning_gte=1.00, warning_lte=1.49, fail_lt=1.00),
            window="latest_quarter",
            hard_risk_candidate=True,
            reason=cash_to_short_term_debt.reason,
            source=cash_to_short_term_debt.source,
            as_of_date=cash_to_short_term_debt.as_of_date,
        ),
        HealthCheckItem(
            category="liquidity_pressure",
            name="current_ratio",
            status=current_ratio.status,
            value=_round_value(current_ratio.value),
            unit="ratio",
            threshold=Threshold(pass_gte=1.20, warning_gte=1.00, warning_lte=1.19, fail_lt=1.00),
            window="latest_quarter",
            hard_risk_candidate=False,
            reason=current_ratio.reason,
            source=current_ratio.source,
            as_of_date=current_ratio.as_of_date,
        ),
        HealthCheckItem(
            category="liquidity_pressure",
            name="cfo_negative_streak_2q",
            status=cfo_negative_streak_metric.status,
            value=cfo_negative_streak_metric.value,
            unit="quarters",
            threshold=Threshold(pass_gte=0, warning_gte=1, warning_lte=1, fail_gt=1),
            window="latest_2q",
            hard_risk_candidate=True,
            reason=cfo_negative_streak_metric.reason,
            source=cfo_negative_streak_metric.source,
            as_of_date=cfo_negative_streak_metric.as_of_date,
        ),
        HealthCheckItem(
            category="earnings_quality",
            name="receivables_growth_gap_pp",
            status=receivables_gap.status,
            value=_round_value(receivables_gap.value),
            unit="pct_points",
            threshold=Threshold(warning_gte=10.01, warning_lte=25.0, fail_gt=25.0),
            window="latest_q_vs_4q_ago",
            hard_risk_candidate=False,
            reason=receivables_gap.reason,
            source=receivables_gap.source,
            as_of_date=receivables_gap.as_of_date,
        ),
        HealthCheckItem(
            category="earnings_quality",
            name="inventory_growth_gap_pp",
            status=inventory_gap.status,
            value=_round_value(inventory_gap.value),
            unit="pct_points",
            threshold=Threshold(warning_gte=15.01, warning_lte=30.0, fail_gt=30.0),
            window="latest_q_vs_4q_ago",
            hard_risk_candidate=False,
            reason=inventory_gap.reason,
            source=inventory_gap.source,
            as_of_date=inventory_gap.as_of_date,
        ),
        HealthCheckItem(
            category="leverage_pressure",
            name="net_debt_to_ebitda",
            status=net_debt_to_ebitda.status,
            value=_round_value(net_debt_to_ebitda.value),
            unit="ratio",
            threshold=Threshold(warning_gte=3.01, warning_lte=4.5, fail_gt=4.5),
            window="ttm",
            hard_risk_candidate=False,
            reason=net_debt_to_ebitda.reason,
            source=net_debt_to_ebitda.source,
            as_of_date=net_debt_to_ebitda.as_of_date,
        ),
        HealthCheckItem(
            category="leverage_pressure",
            name="interest_coverage",
            status=interest_coverage.status,
            value=_round_value(interest_coverage.value),
            unit="ratio",
            threshold=Threshold(pass_gte=3.0, warning_gte=1.5, warning_lte=2.99, fail_lt=1.5),
            window="ttm",
            hard_risk_candidate=True,
            reason=interest_coverage.reason,
            source=interest_coverage.source,
            as_of_date=interest_coverage.as_of_date,
        ),
    )

    category_ratings = {
        "cashflow_quality": _rate_cashflow_category(
            fcf_to_net_income.status,
            cfo_to_net_income.status,
            fcf_negative_streak_metric.status,
            net_income_ttm,
            cfo_ttm,
            fcf_ttm,
        ),
        "liquidity_pressure": _rate_liquidity_category(
            cash_to_short_term_debt.status,
            current_ratio.status,
            cfo_negative_streak_metric.status,
        ),
        "earnings_quality": _rate_earnings_quality_category(
            receivables_gap.status,
            inventory_gap.status,
        ),
        "leverage_pressure": _rate_leverage_category(
            net_debt_to_ebitda.status,
            interest_coverage.status,
        ),
    }
    red_flag_categories = tuple(
        category for category, rating in category_ratings.items() if rating == "High"
    )

    hard_risk_reasons = _hard_risk_reasons(
        cash_to_short_term_debt=cash_to_short_term_debt.value,
        current_ratio=current_ratio.value,
        interest_coverage=interest_coverage.value,
        fcf_negative_streak=fcf_negative_streak,
        cfo_negative_streak=cfo_negative_streak,
        data_staleness_days=data_staleness_days,
    )
    disqualify = bool(hard_risk_reasons)
    overall_rating = _overall_rating(category_ratings, disqualify)
    health_score = _health_score(
        {
            "fcf_to_net_income": fcf_to_net_income.status,
            "cfo_to_net_income": cfo_to_net_income.status,
            "fcf_negative_streak_2q": fcf_negative_streak_metric.status,
            "cash_to_short_term_debt": cash_to_short_term_debt.status,
            "current_ratio": current_ratio.status,
            "cfo_negative_streak_2q": cfo_negative_streak_metric.status,
            "receivables_growth_gap_pp": receivables_gap.status,
            "inventory_growth_gap_pp": inventory_gap.status,
            "net_debt_to_ebitda": net_debt_to_ebitda.status,
            "interest_coverage": interest_coverage.status,
        },
        net_income_ttm=net_income_ttm,
        fcf_ttm=fcf_ttm,
        cfo_ttm=cfo_ttm,
    )
    low_confidence = bool(missing_fields) or data_staleness_days > 120 or any(
        item.status == "unavailable" for item in checks
    )
    if data_staleness_days > 90:
        warnings.append("financial_health_data_stale")

    return FinancialHealthResult(
        overall_rating=overall_rating,
        disqualify=disqualify,
        hard_risk_reasons=hard_risk_reasons,
        category_ratings=category_ratings,
        red_flag_categories=red_flag_categories,
        checks=checks,
        health_score=health_score,
        data_staleness_days=data_staleness_days,
        missing_fields=tuple(sorted(missing_fields)),
        low_confidence=low_confidence,
        warnings=tuple(warnings),
    )


def _round_value(value: float | int | None) -> float | int | None:
    if isinstance(value, float):
        return round(value, 2)
    return value


def _negative_streak(values: list[float] | None) -> int | None:
    if values is None or len(values) < 2:
        return None
    streak = 0
    for value in values[:2]:
        if value < 0:
            streak += 1
        else:
            break
    return streak


def _fcf_series(rows: tuple[FinancialQuarter, ...], missing_fields: set[str]) -> list[float] | None:
    values: list[float] = []
    for row in rows:
        if row.operating_cash_flow is None or row.capital_expenditure is None:
            missing_fields.add("fcf_latest_2q")
            return None
        values.append(float(row.operating_cash_flow) - abs(float(row.capital_expenditure)))
    return values


def _ratio_metric(
    *,
    numerator: float | None,
    denominator: float | None,
    pass_gte: float,
    warning_gte: float,
    fail_lt: float,
    unavailable_reason: str,
    unavailable_when_denominator_non_positive: bool,
    source: str,
    as_of_date: str,
    missing_group: str,
    missing_fields: set[str],
) -> _MetricValue:
    if numerator is None or denominator is None:
        missing_fields.add(missing_group)
        return _MetricValue("unavailable", None, "required_inputs_missing", source, as_of_date)
    if unavailable_when_denominator_non_positive and denominator <= 0:
        return _MetricValue("unavailable", None, unavailable_reason, source, as_of_date)
    value = numerator / denominator
    if value >= pass_gte:
        status = "pass"
        reason = "ratio_above_pass_threshold"
    elif value >= warning_gte:
        status = "warning"
        reason = "ratio_in_warning_band"
    elif value < fail_lt:
        status = "fail"
        reason = "ratio_below_fail_threshold"
    else:
        status = "warning"
        reason = "ratio_in_warning_band"
    return _MetricValue(status, value, reason, source, as_of_date)


def _latest_ratio_metric(
    *,
    numerator: float | None,
    denominator: float | None,
    pass_gte: float,
    warning_gte: float,
    fail_lt: float,
    zero_denominator_status: HealthStatus,
    zero_denominator_reason: str,
    source: str,
    as_of_date: str,
    missing_group: str,
    missing_fields: set[str],
) -> _MetricValue:
    if numerator is None or denominator is None:
        missing_fields.add(missing_group)
        return _MetricValue("unavailable", None, "required_inputs_missing", source, as_of_date)
    if denominator == 0:
        return _MetricValue(zero_denominator_status, None, zero_denominator_reason, source, as_of_date)
    if denominator < 0:
        return _MetricValue("unavailable", None, "denominator_non_positive", source, as_of_date)
    value = numerator / denominator
    if value >= pass_gte:
        return _MetricValue("pass", value, "ratio_above_pass_threshold", source, as_of_date)
    if value >= warning_gte:
        return _MetricValue("warning", value, "ratio_in_warning_band", source, as_of_date)
    if value < fail_lt:
        return _MetricValue("fail", value, "ratio_below_fail_threshold", source, as_of_date)
    return _MetricValue("warning", value, "ratio_in_warning_band", source, as_of_date)


def _interest_coverage_metric(
    *,
    latest_total_debt: float | None,
    operating_income_ttm: float | None,
    interest_expense_ttm: float | None,
    source: str,
    as_of_date: str,
    missing_fields: set[str],
) -> _MetricValue:
    if latest_total_debt is None:
        missing_fields.add("interest_coverage")
        return _MetricValue("unavailable", None, "total_debt_missing", source, as_of_date)
    if latest_total_debt == 0:
        return _MetricValue("pass", None, "debt_free_balance_sheet", source, as_of_date)
    if operating_income_ttm is None or interest_expense_ttm is None:
        missing_fields.add("interest_coverage")
        return _MetricValue("unavailable", None, "required_inputs_missing", source, as_of_date)
    if interest_expense_ttm <= 0:
        return _MetricValue(
            "unavailable",
            None,
            "interest_expense_missing_or_non_positive",
            source,
            as_of_date,
        )
    value = operating_income_ttm / interest_expense_ttm
    if value >= 3.0:
        return _MetricValue("pass", value, "coverage_above_pass_threshold", source, as_of_date)
    if value >= 1.5:
        return _MetricValue("warning", value, "coverage_in_warning_band", source, as_of_date)
    return _MetricValue("fail", value, "coverage_below_fail_threshold", source, as_of_date)


def _net_debt_to_ebitda_metric(
    *,
    total_debt: float | None,
    cash: float | None,
    ebitda_ttm: float | None,
    source: str,
    as_of_date: str,
    missing_fields: set[str],
) -> _MetricValue:
    if total_debt is None or cash is None:
        missing_fields.add("net_debt_to_ebitda")
        return _MetricValue("unavailable", None, "required_inputs_missing", source, as_of_date)
    net_debt = max(total_debt - cash, 0.0)
    if net_debt == 0:
        return _MetricValue("pass", None, "net_cash_or_zero_net_debt", source, as_of_date)
    if ebitda_ttm is None:
        missing_fields.add("net_debt_to_ebitda")
        return _MetricValue("unavailable", None, "ebitda_missing", source, as_of_date)
    if ebitda_ttm <= 0:
        return _MetricValue("fail", None, "positive_net_debt_with_non_positive_ebitda", source, as_of_date)
    value = net_debt / ebitda_ttm
    if value <= 3.0:
        return _MetricValue("pass", value, "leverage_within_bounds", source, as_of_date)
    if value <= 4.5:
        return _MetricValue("warning", value, "leverage_in_warning_band", source, as_of_date)
    return _MetricValue("fail", value, "leverage_above_fail_threshold", source, as_of_date)


def _growth_gap_metric(
    *,
    rows: tuple[FinancialQuarter, ...],
    subject_field: str,
    revenue_field: str,
    warning_gt: float,
    fail_gt: float,
    missing_group: str,
    missing_fields: set[str],
    source: str,
    as_of_date: str,
) -> _MetricValue:
    if len(rows) < 5:
        missing_fields.add(missing_group)
        return _MetricValue("unavailable", None, "five_quarters_required", source, as_of_date)
    latest = rows[0]
    prior = rows[4]
    latest_subject = getattr(latest, subject_field)
    prior_subject = getattr(prior, subject_field)
    latest_revenue = getattr(latest, revenue_field)
    prior_revenue = getattr(prior, revenue_field)
    if None in (latest_subject, prior_subject, latest_revenue, prior_revenue):
        missing_fields.add(missing_group)
        return _MetricValue("unavailable", None, "required_inputs_missing", source, as_of_date)
    if prior_subject <= 0 or prior_revenue <= 0:
        return _MetricValue("unavailable", None, "historical_denominator_non_positive", source, as_of_date)
    subject_growth = ((latest_subject - prior_subject) / prior_subject) * 100
    revenue_growth = ((latest_revenue - prior_revenue) / prior_revenue) * 100
    value = subject_growth - revenue_growth
    if value > fail_gt:
        return _MetricValue("fail", value, "growth_gap_above_fail_threshold", source, as_of_date)
    if value > warning_gt:
        return _MetricValue("warning", value, "growth_gap_in_warning_band", source, as_of_date)
    return _MetricValue("pass", value, "growth_gap_within_bounds", source, as_of_date)


def _streak_metric(
    *,
    streak: int | None,
    pass_value: int,
    warning_value: int,
    fail_value: int,
    unavailable_reason: str,
    source: str,
    as_of_date: str,
) -> _MetricValue:
    if streak is None:
        return _MetricValue("unavailable", None, unavailable_reason, source, as_of_date)
    if streak >= fail_value:
        return _MetricValue("fail", streak, "two_quarter_negative_streak", source, as_of_date)
    if streak == warning_value:
        return _MetricValue("warning", streak, "one_quarter_negative_streak", source, as_of_date)
    return _MetricValue("pass", pass_value, "no_recent_negative_streak", source, as_of_date)


def _count_statuses(statuses: tuple[HealthStatus, ...]) -> tuple[int, int]:
    fail_count = sum(status == "fail" for status in statuses)
    warning_count = sum(status == "warning" for status in statuses)
    return fail_count, warning_count


def _rate_cashflow_category(
    fcf_to_net_income: HealthStatus,
    cfo_to_net_income: HealthStatus,
    fcf_negative_streak: HealthStatus,
    net_income_ttm: float | None,
    cfo_ttm: float | None,
    fcf_ttm: float | None,
) -> HealthRating:
    statuses = (fcf_to_net_income, cfo_to_net_income, fcf_negative_streak)
    fail_count, warning_count = _count_statuses(statuses)
    if fcf_negative_streak == "fail":
        return "High"
    if net_income_ttm is not None and net_income_ttm <= 0 and (cfo_ttm or 0) <= 0 and (fcf_ttm or 0) <= 0:
        return "High"
    if fail_count >= 2:
        return "High"
    if fail_count == 1 or warning_count >= 2:
        return "Medium"
    if net_income_ttm is not None and net_income_ttm <= 0 and (cfo_ttm or 0) > 0 and (fcf_ttm or 0) <= 0:
        return "Medium"
    return "Low"


def _rate_liquidity_category(
    cash_to_short_term_debt: HealthStatus,
    current_ratio: HealthStatus,
    cfo_negative_streak: HealthStatus,
) -> HealthRating:
    statuses = (cash_to_short_term_debt, current_ratio, cfo_negative_streak)
    fail_count, warning_count = _count_statuses(statuses)
    if cash_to_short_term_debt == "fail" and current_ratio == "fail":
        return "High"
    if cash_to_short_term_debt == "fail" and cfo_negative_streak == "fail":
        return "High"
    if fail_count >= 2:
        return "High"
    if fail_count == 1 or warning_count >= 2:
        return "Medium"
    return "Low"


def _rate_earnings_quality_category(
    receivables_gap: HealthStatus,
    inventory_gap: HealthStatus,
) -> HealthRating:
    if receivables_gap == "fail" and inventory_gap == "fail":
        return "High"
    if "fail" in (receivables_gap, inventory_gap) and "warning" in (receivables_gap, inventory_gap):
        return "High"
    if receivables_gap == "fail" or inventory_gap == "fail":
        return "Medium"
    if receivables_gap == "warning" and inventory_gap == "warning":
        return "Medium"
    return "Low"


def _rate_leverage_category(
    net_debt_to_ebitda: HealthStatus,
    interest_coverage: HealthStatus,
) -> HealthRating:
    if net_debt_to_ebitda == "fail" and interest_coverage == "fail":
        return "High"
    if net_debt_to_ebitda == "fail" and interest_coverage == "warning":
        return "High"
    if interest_coverage == "fail" and net_debt_to_ebitda == "warning":
        return "High"
    if "fail" in (net_debt_to_ebitda, interest_coverage):
        return "Medium"
    if net_debt_to_ebitda == "warning" and interest_coverage == "warning":
        return "Medium"
    return "Low"


def _hard_risk_reasons(
    *,
    cash_to_short_term_debt: float | None,
    current_ratio: float | None,
    interest_coverage: float | None,
    fcf_negative_streak: int | None,
    cfo_negative_streak: int | None,
    data_staleness_days: int,
) -> tuple[HardRiskReason, ...]:
    if data_staleness_days > 120:
        return ()
    reasons: list[HardRiskReason] = []
    if cash_to_short_term_debt is not None and interest_coverage is not None:
        if cash_to_short_term_debt < 1.0 and interest_coverage < 1.5:
            reasons.append("near_term_debt_coverage_failure")
    if cash_to_short_term_debt is not None and fcf_negative_streak is not None:
        if cash_to_short_term_debt < 1.0 and fcf_negative_streak >= 2:
            reasons.append("cash_burn_against_short_term_debt")
    if (
        cash_to_short_term_debt is not None
        and current_ratio is not None
        and cfo_negative_streak is not None
        and cash_to_short_term_debt < 0.75
        and current_ratio < 0.90
        and cfo_negative_streak >= 2
    ):
        reasons.append("working_capital_crunch")
    return tuple(reasons)


def _overall_rating(
    category_ratings: dict[HealthCategory, HealthRating],
    disqualify: bool,
) -> HealthRating:
    high_count = sum(rating == "High" for rating in category_ratings.values())
    medium_count = sum(rating == "Medium" for rating in category_ratings.values())
    if disqualify or high_count >= 2 or (high_count == 1 and medium_count >= 1):
        return "High"
    if (high_count == 1 and medium_count == 0) or (high_count == 0 and medium_count >= 2):
        return "Medium"
    return "Low"


def _status_points(status: HealthStatus, points: tuple[int, int, int, int]) -> int:
    pass_points, warning_points, fail_points, unavailable_points = points
    if status == "pass":
        return pass_points
    if status == "warning":
        return warning_points
    if status == "fail":
        return fail_points
    return unavailable_points


def _health_score(
    statuses: dict[str, HealthStatus],
    *,
    net_income_ttm: float | None,
    fcf_ttm: float | None,
    cfo_ttm: float | None,
) -> int:
    fcf_points = _status_points(statuses["fcf_to_net_income"], (12, 6, 0, 6))
    cfo_points = _status_points(statuses["cfo_to_net_income"], (10, 5, 0, 5))
    if net_income_ttm is not None and net_income_ttm <= 0:
        if (fcf_ttm or 0) <= 0:
            fcf_points = 0
        if (cfo_ttm or 0) <= 0:
            cfo_points = 0

    total = 0
    total += fcf_points
    total += cfo_points
    total += _status_points(statuses["fcf_negative_streak_2q"], (8, 4, 0, 4))
    total += _status_points(statuses["cash_to_short_term_debt"], (12, 6, 0, 6))
    total += _status_points(statuses["current_ratio"], (7, 3, 0, 3))
    total += _status_points(statuses["cfo_negative_streak_2q"], (6, 3, 0, 3))
    total += _status_points(statuses["receivables_growth_gap_pp"], (10, 5, 0, 5))
    total += _status_points(statuses["inventory_growth_gap_pp"], (10, 5, 0, 5))
    total += _status_points(statuses["net_debt_to_ebitda"], (12, 6, 0, 6))
    total += _status_points(statuses["interest_coverage"], (13, 6, 0, 6))
    return max(0, min(100, int(round(total))))
