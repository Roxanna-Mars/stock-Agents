from src.utils.react_config import get_react_invoke_config


def test_default_recursion_limit(monkeypatch):
    monkeypatch.delenv("REACT_RECURSION_LIMIT", raising=False)

    assert get_react_invoke_config() == {"recursion_limit": 40}


def test_recursion_limit_is_bounded(monkeypatch):
    monkeypatch.setenv("REACT_RECURSION_LIMIT", "999")
    assert get_react_invoke_config() == {"recursion_limit": 64}

    monkeypatch.setenv("REACT_RECURSION_LIMIT", "1")
    assert get_react_invoke_config() == {"recursion_limit": 10}


def test_invalid_recursion_limit_uses_default(monkeypatch):
    monkeypatch.setenv("REACT_RECURSION_LIMIT", "invalid")

    assert get_react_invoke_config() == {"recursion_limit": 40}
