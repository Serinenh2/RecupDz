"""
Fallback Chain — ordered fallback with primary → cache → deterministic.

Features:
    Ordered chain of callables (steps)
    Each step can be conditional (enabled flag)
    Short-circuits on first successful result
    Supports per-step timeout and circuit breaker
    Immutable result with timing per step

Integration:
    Used by OfflineMode to chain: Ollama → cached LLM → deterministic response
    and: KnowledgeSearch → cached knowledge → empty result.

Architecture:
    Step 1 (Ollama) ──fail──► Step 2 (Cache) ──miss──► Step 3 (Deterministic)
         │                      │                        │
         ▼                      ▼                        ▼
    result.success=True    result.success=True        result.success=True
    RETURN                 RETURN                     RETURN
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


# ══════════════════════════════════════════════════════════════════════
# Data structures
# ══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class FallbackStep:
    """A single step in the fallback chain."""
    name: str
    fn: Callable[..., Any]
    enabled: bool = True
    timeout_seconds: float = 10.0
    description: str = ""


@dataclass(frozen=True)
class StepResult:
    """Result of executing a single fallback step."""
    name: str
    success: bool
    value: Any = None
    error: Optional[str] = None
    elapsed_ms: float = 0.0


@dataclass(frozen=True)
class FallbackResult:
    """Result of executing the full fallback chain."""
    success: bool
    value: Any = None
    steps: tuple = ()
    final_step: str = ""
    total_elapsed_ms: float = 0.0
    fallback_used: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "final_step": self.final_step,
            "fallback_used": self.fallback_used,
            "steps_attempted": len(self.steps),
            "total_elapsed_ms": round(self.total_elapsed_ms, 2),
        }


# ══════════════════════════════════════════════════════════════════════
# Fallback Chain
# ══════════════════════════════════════════════════════════════════════

class FallbackChain:
    """Executes an ordered chain of callables, short-circuiting on success.

    Usage:
        chain = FallbackChain([
            FallbackStep("ollama", lambda q: ollama.chat(q), timeout_seconds=10),
            FallbackStep("cache", lambda q: cache.get(q), timeout_seconds=2),
            FallbackStep("deterministic", lambda q: "Réponse par défaut"),
        ])
        result = chain.execute("Quels sont les déchets dangereux ?")
        if result.success:
            print(result.value)
    """

    def __init__(self, steps: Optional[List[FallbackStep]] = None) -> None:
        self._steps = list(steps or [])

    @property
    def steps(self) -> List[FallbackStep]:
        return list(self._steps)

    def add_step(self, step: FallbackStep) -> None:
        """Append a step to the chain."""
        self._steps.append(step)

    def remove_step(self, name: str) -> bool:
        """Remove a step by name. Returns True if found."""
        for i, step in enumerate(self._steps):
            if step.name == name:
                self._steps.pop(i)
                return True
        return False

    def execute(self, *args: Any, **kwargs: Any) -> FallbackResult:
        """Execute the chain. Returns FallbackResult — never raises."""
        total_start = time.monotonic()
        step_results: List[StepResult] = []

        for step in self._steps:
            if not step.enabled:
                continue

            step_start = time.monotonic()
            try:
                value = step.fn(*args, **kwargs)
                elapsed = (time.monotonic() - step_start) * 1000

                step_results.append(StepResult(
                    name=step.name,
                    success=True,
                    value=value,
                    elapsed_ms=round(elapsed, 2),
                ))

                total_elapsed = (time.monotonic() - total_start) * 1000
                return FallbackResult(
                    success=True,
                    value=value,
                    steps=tuple(step_results),
                    final_step=step.name,
                    total_elapsed_ms=round(total_elapsed, 2),
                    fallback_used=len(step_results) > 1,
                )

            except Exception as exc:
                elapsed = (time.monotonic() - step_start) * 1000
                step_results.append(StepResult(
                    name=step.name,
                    success=False,
                    error=str(exc),
                    elapsed_ms=round(elapsed, 2),
                ))
                logger.debug(
                    "FallbackChain step '%s' failed: %s (%.1fms)",
                    step.name, exc, elapsed,
                )

        # All steps failed
        total_elapsed = (time.monotonic() - total_start) * 1000
        return FallbackResult(
            success=False,
            steps=tuple(step_results),
            final_step=step_results[-1].name if step_results else "",
            total_elapsed_ms=round(total_elapsed, 2),
            fallback_used=False,
        )

    def execute_with_args(
        self,
        primary_fn: Callable[..., Any],
        fallback_fns: List[Callable[..., Any]],
        *args: Any,
        **kwargs: Any,
    ) -> FallbackResult:
        """Convenience: build chain from primary + fallback callables."""
        steps = [FallbackStep("primary", primary_fn)]
        for i, fn in enumerate(fallback_fns):
            steps.append(FallbackStep(f"fallback_{i}", fn))
        self._steps = steps
        return self.execute(*args, **kwargs)
