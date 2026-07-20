"""
Recovery Engine — handles failures with retries, fallbacks, and compensation.

Implements multiple recovery strategies and manages the compensation graph
for rollback when needed.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from apps.ai_assistant.workflows.models import (
    RecoveryStrategy, StepConfig, StepStatus, WorkflowState,
)

logger = logging.getLogger(__name__)


@dataclass
class RetryPolicy:
    """Configuration for step retry behavior."""
    max_retries: int = 3
    base_delay_seconds: float = 1.0
    backoff_multiplier: float = 2.0
    max_delay_seconds: float = 30.0
    jitter: bool = True

    def delay_for_attempt(self, attempt: int) -> float:
        import random
        delay = self.base_delay_seconds * (self.backoff_multiplier ** (attempt - 1))
        delay = min(delay, self.max_delay_seconds)
        if self.jitter:
            delay *= (0.5 + random.random() * 0.5)
        return delay


@dataclass
class RecoveryAction:
    """Describes what to do when a step fails."""
    strategy: RecoveryStrategy
    retry_policy: Optional[RetryPolicy] = None
    fallback_value: Any = None
    fallback_step_id: Optional[str] = None
    compensation_step_id: Optional[str] = None
    human_review: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RecoveryRecord:
    """Tracks recovery attempts for a step."""
    step_id: str
    strategy: RecoveryStrategy
    attempts: int = 0
    last_error: Optional[str] = None
    last_attempt_time: Optional[float] = None
    recovered: bool = False
    compensation_triggered: bool = False
    history: List[Dict[str, Any]] = field(default_factory=list)


class RecoveryEngine:
    """
    Manages failure recovery for workflow steps.

    Responsibilities:
      1. Determine recovery strategy for failed steps
      2. Execute retry logic with backoff
      3. Apply fallback values
      4. Trigger compensation (rollback) steps
      5. Track recovery history for auditing
    """

    def __init__(self) -> None:
        self._strategies: Dict[str, RecoveryAction] = {}
        self._records: Dict[str, RecoveryRecord] = {}
        self._compensation_handlers: Dict[str, Callable[[Dict[str, Any]], bool]] = {}

    def register_strategy(self, step_id: str, action: RecoveryAction) -> None:
        self._strategies[step_id] = action

    def register_compensation_handler(
        self, step_id: str, handler: Callable[[Dict[str, Any]], bool]
    ) -> None:
        self._compensation_handlers[step_id] = handler

    def handle_failure(
        self,
        step_id: str,
        error: str,
        state: WorkflowState,
        step_config: Optional[StepConfig] = None,
    ) -> RecoveryAction:
        """
        Determine and record the recovery action for a failed step.
        Returns the RecoveryAction to execute.
        """
        record = self._get_record(step_id)
        record.attempts += 1
        record.last_error = error
        record.last_attempt_time = time.monotonic()

        record.history.append({
            "attempt": record.attempts,
            "error": error,
            "time": record.last_attempt_time,
        })

        action = self._strategies.get(step_id)
        if action is None and step_config:
            action = RecoveryAction(
                strategy=step_config.recovery_strategy,
                retry_policy=RetryPolicy(
                    max_retries=step_config.max_retries,
                    base_delay_seconds=step_config.retry_delay_seconds,
                    backoff_multiplier=step_config.retry_backoff,
                ),
                fallback_value=step_config.fallback_value,
                compensation_step_id=step_config.compensation_step,
            )

        if action is None:
            action = RecoveryAction(strategy=RecoveryStrategy.ABORT)

        if action.strategy == RecoveryStrategy.RETRY:
            policy = action.retry_policy or RetryPolicy()
            if record.attempts >= policy.max_retries:
                logger.info(
                    f"Step {step_id}: max retries ({policy.max_retries}) reached, "
                    f"falling back to ABORT"
                )
                action = RecoveryAction(strategy=RecoveryStrategy.ABORT)

        logger.info(
            f"Step {step_id}: recovery strategy={action.strategy.value}, "
            f"attempt={record.attempts}"
        )
        return action

    def should_retry(self, step_id: str) -> bool:
        record = self._records.get(step_id)
        if not record:
            return False

        action = self._strategies.get(step_id)
        if not action or action.strategy != RecoveryStrategy.RETRY:
            return False

        policy = action.retry_policy or RetryPolicy()
        return record.attempts < policy.max_retries

    def get_retry_delay(self, step_id: str) -> float:
        record = self._records.get(step_id)
        if not record:
            return 0.0

        action = self._strategies.get(step_id)
        if not action:
            return 0.0

        policy = action.retry_policy or RetryPolicy()
        return policy.delay_for_attempt(record.attempts)

    def execute_compensation(
        self, step_id: str, state: WorkflowState, output_data: Dict[str, Any]
    ) -> bool:
        """Execute compensation (rollback) for a failed step."""
        record = self._get_record(step_id)
        action = self._strategies.get(step_id)

        if not action or not action.compensation_step_id:
            return False

        handler = self._compensation_handlers.get(action.compensation_step_id)
        if handler:
            try:
                success = handler(output_data)
                record.compensation_triggered = True
                logger.info("Compensation for %s: %s", step_id, "success" if success else "failed")
                return success
            except Exception as e:
                logger.error("Compensation error for %s: %s", step_id, e)
                return False

        comp_state = state.get_step_state(action.compensation_step_id)
        comp_state.status = StepStatus.PENDING
        state.compensation_stack.append(step_id)
        record.compensation_triggered = True
        return True

    def get_record(self, step_id: str) -> Optional[RecoveryRecord]:
        return self._records.get(step_id)

    def get_all_records(self) -> Dict[str, RecoveryRecord]:
        return dict(self._records)

    def reset(self, step_id: str) -> None:
        self._records.pop(step_id, None)

    def clear(self) -> None:
        self._records.clear()

    def _get_record(self, step_id: str) -> RecoveryRecord:
        if step_id not in self._records:
            self._records[step_id] = RecoveryRecord(step_id=step_id, strategy=RecoveryStrategy.ABORT)
        return self._records[step_id]
