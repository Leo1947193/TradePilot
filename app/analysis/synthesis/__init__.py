from __future__ import annotations

from app.analysis.synthesis.adapt import adapt_module_signals
from app.analysis.synthesis.output import build_decision_output
from app.analysis.synthesis.scoring import score_decision
from app.schemas.api import DecisionSynthesis
from app.schemas.graph_state import ModuleReports, ModuleResults


def build_decision_synthesis(
    module_results: ModuleResults,
    module_reports: ModuleReports | None = None,
) -> DecisionSynthesis:
    normalized_signals = adapt_module_signals(module_results, module_reports)
    scored_decision = score_decision(normalized_signals)
    return build_decision_output(scored_decision)
