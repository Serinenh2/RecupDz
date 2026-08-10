"""
Enterprise AI Agent Module — production-ready orchestrator.

Integrates:
    - DI Container (Factory + Strategy patterns)
    - Pipeline (Clean Architecture)
    - Infrastructure (caching, monitoring, audit, metrics, tracing)
"""

from apps.ai_assistant.enterprise.container import Container
from apps.ai_assistant.enterprise.pipeline import EnterprisePipeline

__all__ = ["Container", "EnterprisePipeline"]
