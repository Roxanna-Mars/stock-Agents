from pathlib import Path

from evaluation.benchmark_schema import load_benchmark


def test_benchmark_v1_has_expected_coverage():
    path = Path(__file__).resolve().parents[2] / "evaluation" / "benchmark_v1.jsonl"
    cases = load_benchmark(path)
    categories = {case["category"] for case in cases}

    assert len(cases) == 100
    assert categories == {
        "single_stock",
        "focused_analysis",
        "multi_stock_comparison",
        "financial_calculation",
        "robustness",
    }
    assert len({case["id"] for case in cases}) == len(cases)
    assert len({case["query"] for case in cases}) == len(cases)
    category_counts = {
        category: sum(case["category"] == category for case in cases)
        for category in categories
    }
    assert category_counts == {
        "single_stock": 20,
        "focused_analysis": 25,
        "multi_stock_comparison": 20,
        "financial_calculation": 20,
        "robustness": 15,
    }
