from __future__ import annotations

from datetime import datetime, timezone

from app.analysis.fundamental.aggregate import (
    aggregate_fundamental_signals,
    analyze_financial_snapshot,
)
from app.analysis.fundamental.earnings_momentum import (
    CurrentQuarterConsensus,
    EarningsMomentumInput,
    EarningsQuarter,
    GuidanceRecord,
    RevisionSnapshot,
    analyze_earnings_momentum,
)
from app.analysis.fundamental.financial_health import (
    FinancialHealthInput,
    FinancialQuarter,
    analyze_financial_health,
)
from app.analysis.fundamental.schemas import FundamentalAggregateResult
from app.analysis.fundamental.schemas import FundamentalSubmoduleBundle
from app.analysis.fundamental.valuation_anchor import analyze_valuation_anchor_from_snapshot
from app.schemas.modules import (
    AnalysisModuleName,
    AnalysisModuleResult,
    ModuleExecutionStatus,
)
from app.services.providers.dtos import FinancialSnapshot


def analyze_fundamental_module(snapshot: FinancialSnapshot) -> AnalysisModuleResult:
    aggregate_result = analyze_fundamental_aggregate(snapshot)
    module_summary = _resolve_module_summary(aggregate_result)
    module_low_confidence = _resolve_module_low_confidence(aggregate_result)
    return AnalysisModuleResult(
        module=AnalysisModuleName.FUNDAMENTAL,
        status=ModuleExecutionStatus.USABLE,
        summary=module_summary,
        direction=aggregate_result.fundamental_bias,
        data_completeness_pct=aggregate_result.data_completeness_pct,
        low_confidence=module_low_confidence,
        reason=None,
    )


def analyze_fundamental_aggregate(snapshot: FinancialSnapshot) -> FundamentalAggregateResult:
    snapshot_signal = analyze_financial_snapshot(snapshot)
    submodules = _build_fundamental_submodule_bundle(snapshot)
    return aggregate_fundamental_signals(snapshot_signal, submodules=submodules)


def _build_fundamental_submodule_bundle(snapshot: FinancialSnapshot) -> FundamentalSubmoduleBundle:
    analysis_date = snapshot.as_of_date
    financial_health = analyze_financial_health(
        FinancialHealthInput(
            analysis_date=analysis_date,
            quarterly_results=(
                FinancialQuarter(
                    report_period_end=snapshot.as_of_date,
                    cash_and_equivalents=None,
                    short_term_debt=None,
                    current_assets=None,
                    current_liabilities=None,
                    accounts_receivable=None,
                    inventory=None,
                    total_debt=None,
                    operating_cash_flow=None,
                    capital_expenditure=None,
                    net_income=snapshot.net_income,
                    revenue=snapshot.revenue,
                    operating_income=None,
                    interest_expense=None,
                    depreciation_and_amortization=None,
                ),
            ),
            missing_fields=(
                "cash_and_equivalents",
                "short_term_debt",
                "current_assets",
                "current_liabilities",
                "accounts_receivable",
                "inventory",
                "total_debt",
                "operating_cash_flow",
                "capital_expenditure",
                "operating_income",
                "interest_expense",
                "depreciation_and_amortization",
            ),
        )
    )
    earnings_momentum = analyze_earnings_momentum(
        EarningsMomentumInput(
            analysis_timestamp=datetime.combine(analysis_date, datetime.min.time(), tzinfo=timezone.utc),
            quarterly_results=(
                EarningsQuarter(
                    report_date=snapshot.as_of_date,
                    eps_actual=snapshot.eps,
                    eps_consensus_pre_report=None,
                    revenue_actual=snapshot.revenue,
                    revenue_consensus_pre_report=None,
                ),
            ),
            revision_summary=RevisionSnapshot(as_of_date=analysis_date),
            current_quarter_consensus=CurrentQuarterConsensus(as_of_date=analysis_date),
            guidance_history=(GuidanceRecord(as_of_date=analysis_date, explicit_no_guidance=True),),
            ticker=snapshot.symbol,
            missing_fields=("eps_consensus_pre_report", "revenue_consensus_pre_report"),
        )
    )
    valuation_anchor = analyze_valuation_anchor_from_snapshot(snapshot, analysis_date=analysis_date)
    snapshot_signal = analyze_financial_snapshot(snapshot)
    return FundamentalSubmoduleBundle(
        financial_snapshot=snapshot_signal,
        financial_health=financial_health,
        earnings_momentum=earnings_momentum,
        valuation_anchor=valuation_anchor,
    )


def _resolve_module_summary(aggregate_result: FundamentalAggregateResult) -> str:
    snapshot_signal = aggregate_result.subresults.get("financial_snapshot")
    if snapshot_signal is None:
        return aggregate_result.summary

    snapshot_summary = getattr(snapshot_signal, "summary", None)
    if isinstance(snapshot_summary, str) and snapshot_summary:
        return snapshot_summary

    return aggregate_result.summary


def _resolve_module_low_confidence(aggregate_result: FundamentalAggregateResult) -> bool:
    snapshot_signal = aggregate_result.subresults.get("financial_snapshot")
    if snapshot_signal is None:
        return aggregate_result.low_confidence

    snapshot_low_confidence = getattr(snapshot_signal, "low_confidence", None)
    if isinstance(snapshot_low_confidence, bool):
        return snapshot_low_confidence

    return aggregate_result.low_confidence
