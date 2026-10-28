"""Environment-backed Web settings without exposing model secrets."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]


def _csv(value: str) -> tuple[str, ...]:
    return tuple(item.strip() for item in value.split(",") if item.strip())


@dataclass(frozen=True)
class Settings:
    project_root: Path = PROJECT_ROOT
    database_path: Path = Path(
        os.getenv(
            "WEB_DATABASE_PATH",
            str(PROJECT_ROOT / "web" / "backend" / "data" / "research_web.db"),
        )
    )
    log_dir: Path = Path(os.getenv("WEB_LOG_DIR", str(PROJECT_ROOT / "logs")))
    cors_origins: tuple[str, ...] = _csv(
        os.getenv(
            "WEB_CORS_ORIGINS",
            "http://localhost:5173,http://127.0.0.1:5173",
        )
    )
    timezone_name: str = os.getenv("WEB_TIMEZONE", "Asia/Shanghai")
    intent_router_use_llm: bool = os.getenv(
        "INTENT_ROUTER_USE_LLM", "1"
    ).strip().casefold() not in {"0", "false", "no", "off"}
    direct_tool_routing_enabled: bool = os.getenv(
        "DIRECT_TOOL_ROUTING_ENABLED", "1"
    ).strip().casefold() not in {"0", "false", "no", "off"}


settings = Settings()
