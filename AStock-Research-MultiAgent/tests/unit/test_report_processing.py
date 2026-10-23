from src.agents.summary_agent import ensure_baseline_time_footer


def test_baseline_time_at_top_does_not_truncate_report():
    timestamp = "2026年09月22日 星期二 10:00:00"
    source = f"""# 测试报告

**分析基准时间：{timestamp}**

## 执行摘要
摘要内容

## 投资建议
建议内容
"""

    result = ensure_baseline_time_footer(source, timestamp)

    assert "## 执行摘要" in result
    assert "## 投资建议" in result
    assert result.count("分析基准时间") == 1
    assert result.rstrip().endswith(f"**分析基准时间：{timestamp}**")


def test_existing_footer_is_normalized_without_duplicate():
    timestamp = "2026年09月22日 星期二 10:00:00"
    source = f"# 报告\n\n正文\n\n**分析基准时间：{timestamp}**\n"

    result = ensure_baseline_time_footer(source, timestamp)

    assert "正文" in result
    assert result.count("分析基准时间") == 1
