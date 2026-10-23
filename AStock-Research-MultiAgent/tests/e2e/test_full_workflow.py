import json
import os
from pathlib import Path
import subprocess
import sys

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[2]
LOGS_DIR = PROJECT_ROOT / "logs"
EXPECTED_AGENTS = {
    "fundamental_agent",
    "main",
    "news_agent",
    "summary_agent",
    "technical_agent",
    "value_agent",
}
REQUIRED_SECTIONS = (
    "基本面分析",
    "技术分析",
    "估值分析",
    "新闻分析",
    "风险因素",
    "投资建议",
)


def _execution_dirs():
    if not LOGS_DIR.exists():
        return set()
    return {path.resolve() for path in LOGS_DIR.iterdir() if path.is_dir()}


@pytest.mark.live_llm
def test_full_workflow_generates_a_complete_report():
    if os.getenv("RUN_LIVE_LLM") != "1":
        pytest.skip("set RUN_LIVE_LLM=1 to allow a paid LLM workflow")

    before = _execution_dirs()
    env = os.environ.copy()
    env.update({"PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"})
    completed = subprocess.run(
        [sys.executable, "-m", "src.main", "--command", "分析贵州茅台(600519)"],
        cwd=PROJECT_ROOT,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=900,
        check=False,
    )

    created = _execution_dirs() - before
    assert completed.returncode == 0, completed.stderr[-4000:]
    assert created, "workflow did not create an execution log directory"
    execution_dir = max(created, key=lambda path: path.stat().st_mtime)

    execution_info = json.loads(
        (execution_dir / "execution_info.json").read_text(encoding="utf-8")
    )
    assert execution_info["success"] is True

    report = (execution_dir / "reports" / "final_report.md").read_text(
        encoding="utf-8"
    )
    assert len(report) >= 3000
    assert report.count("分析基准时间") == 1
    for section in REQUIRED_SECTIONS:
        assert section in report

    statuses = {}
    for path in (execution_dir / "agents").glob("*_execution.json"):
        data = json.loads(path.read_text(encoding="utf-8"))
        statuses[data["agent_name"]] = data["status"]

    assert set(statuses) == EXPECTED_AGENTS
    assert all(status == "completed" for status in statuses.values())
