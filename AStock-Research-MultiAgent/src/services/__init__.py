"""Application services shared by CLI and Web entry points."""

from src.services.research_service import ResearchRunResult, ResearchService

__all__ = ["ResearchRunResult", "ResearchService"]
