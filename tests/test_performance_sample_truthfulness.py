"""Guard the WF010 sample dataset against misleading 100% success-only metrics."""
import pandas as pd
from app import tools


def test_default_performance_dataset_keeps_failures_and_calculates_rates():
    logs = pd.read_csv(tools.DATA / "workflow_logs.csv")
    assert len(logs) == 133
    statuses = logs["status"].astype(str).str.strip().str.lower()
    assert int((statuses == "success").sum()) == 122
    assert int((statuses != "success").sum()) == 11
    result = tools.performance_report()
    assert result["success_rate_percent"] == 91.73
    assert result["failure_rate_percent"] == 8.27
