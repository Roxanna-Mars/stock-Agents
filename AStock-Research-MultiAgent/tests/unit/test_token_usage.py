from types import SimpleNamespace

from src.utils.token_usage import collect_token_usage


def test_collects_langchain_usage_metadata():
    messages = [
        SimpleNamespace(
            usage_metadata={
                "input_tokens": 100,
                "output_tokens": 20,
                "total_tokens": 120,
            },
            response_metadata={},
        ),
        SimpleNamespace(
            usage_metadata={
                "input_tokens": 40,
                "output_tokens": 10,
            },
            response_metadata={},
        ),
    ]

    assert collect_token_usage(messages) == {
        "input_tokens": 140,
        "output_tokens": 30,
        "total_tokens": 170,
    }


def test_collects_openai_style_response_metadata():
    message = SimpleNamespace(
        usage_metadata=None,
        response_metadata={
            "token_usage": {
                "prompt_tokens": 12,
                "completion_tokens": 8,
                "total_tokens": 20,
            }
        },
    )

    assert collect_token_usage([message])["total_tokens"] == 20
