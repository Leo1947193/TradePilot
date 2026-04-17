CREATE INDEX IF NOT EXISTS idx_analysis_reports_ticker_time
    ON analysis_reports (ticker, analysis_time DESC, id DESC);

CREATE INDEX IF NOT EXISTS idx_analysis_reports_bias_time
    ON analysis_reports (overall_bias, analysis_time DESC);

CREATE INDEX IF NOT EXISTS idx_analysis_reports_actionability_time
    ON analysis_reports (actionability_state, analysis_time DESC);

CREATE INDEX IF NOT EXISTS idx_analysis_reports_analysis_time
    ON analysis_reports (analysis_time DESC);

CREATE INDEX IF NOT EXISTS idx_analysis_reports_pipeline_time
    ON analysis_reports (pipeline_version, analysis_time DESC);

CREATE INDEX IF NOT EXISTS idx_analysis_module_reports_module_status
    ON analysis_module_reports (module_name, status);

CREATE INDEX IF NOT EXISTS idx_analysis_module_reports_module_direction
    ON analysis_module_reports (module_name, direction);

CREATE INDEX IF NOT EXISTS idx_analysis_module_reports_analysis_report_id
    ON analysis_module_reports (analysis_report_id);

CREATE INDEX IF NOT EXISTS idx_analysis_module_reports_module_direction_report
    ON analysis_module_reports (module_name, direction, analysis_report_id);
