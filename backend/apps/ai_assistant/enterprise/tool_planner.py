"""
Tool Planner — execution plan generation from DecisionProposal.

Zero tool execution.  Zero repository access.  Zero Django coupling.

Responsibilities:
    1. Receive DecisionProposal           — structured input from reasoning layer
    2. Determine execution order           — sequential, parallel, or fallback
    3. Detect tool dependencies            — data-flow and ordering constraints
    4. Detect conflicting tools            — mutually exclusive operations
    5. Estimate execution cost             — time + resource estimates
    6. Require confirmation                — destructive / low-confidence ops
    7. Generate fallback plan              — alternative on failure
    8. Return immutable ExecutionPlan      — frozen dataclass with to_dict()

Execution Modes:
    SEQUENTIAL  — tools run one after another (default for dependencies)
    PARALLEL    — tools run concurrently (independent reads)
    FALLBACK    — primary fails → try alternative
    MIXED       — combination of sequential + parallel phases

Architecture:
    ToolPlanner.plan(proposal) → ExecutionPlan
        → ordered_tools: List[ToolStep]
        → execution_mode: str
        → dependencies: Dict[str, List[str]]
        → estimated_cost: CostEstimate
        → requires_confirmation: bool
        → fallback_plan: Optional[ExecutionPlan]

Design Rules:
    - Never guess — if conflict detected → requires_confirmation
    - Never execute — planning only
    - Does NOT modify any existing module — pure additive
    - Immutable dataclasses with full to_dict() serialization
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple


# ══════════════════════════════════════════════════════════════════════
# Constants
# ══════════════════════════════════════════════════════════════════════


class ExecutionMode:
    SEQUENTIAL = "sequential"
    PARALLEL = "parallel"
    FALLBACK = "fallback"
    MIXED = "mixed"


# ── Tool metadata: (estimated_ms, is_write, category) ────────────────

_TOOL_META: Dict[str, Tuple[float, bool, str]] = {
    "waste_tool":           (150, False, "nomenclature"),
    "declaration_tool":     (200, False, "declaration"),
    "producteur_tool":      (150, False, "actor"),
    "transporteur_tool":    (150, False, "actor"),
    "partner_tool":         (150, False, "actor"),
    "entreprise_tool":      (180, False, "actor"),
    "statistiques_tool":    (300, False, "analytics"),
    "rapport_tool":         (400, False, "analytics"),
    "reglementation_tool":  (120, False, "knowledge"),
    "authentification_tool": (100, False, "auth"),
    "bsd_tool":             (180, False, "document"),
    "bc_tool":              (180, False, "document"),
    "bl_tool":              (180, False, "document"),
    "inspection_tool":      (150, False, "compliance"),
    "archive_tool":         (120, False, "document"),
    "traceability_tool":    (200, False, "traceability"),
    "glossaire_tool":       (80,  False, "knowledge"),
    "nomenclature_tool":    (100, False, "nomenclature"),
    "notification_tool":    (80,  False, "notification"),
    "dashboard_tool":       (250, False, "analytics"),
    "administration_tool":  (120, False, "actor"),
    "permissions_tool":     (100, False, "auth"),
    "rag_knowledge_tool":   (200, False, "knowledge"),
}

# ── Tool categories that produce data consumed by others ──────────────
# Maps tool category → categories that depend on its output
_DEPENDENCY_GRAPH: Dict[str, List[str]] = {
    "nomenclature":  ["document", "analytics"],
    "actor":         ["document", "traceability", "analytics"],
    "document":      ["analytics", "notification"],
    "knowledge":     ["analytics"],
    "compliance":    ["analytics", "notification"],
    "traceability":  ["analytics", "notification"],
    "auth":          ["notification"],
}

# ── Conflicting tool pairs (same entity, different mutations) ─────────
# Maps (tool, action) → set of (tool, action) that conflict
_CONFLICT_RULES: Dict[Tuple[str, str], List[Tuple[str, str]]] = {
    ("declaration_tool", "create"): [
        ("declaration_tool", "update"),
    ],
    ("bsd_tool", "create"): [
        ("bsd_tool", "update"),
    ],
    ("notification_tool", "list"): [
        ("notification_tool", "by_type"),
        ("notification_tool", "by_priority"),
    ],
}

# ── Actions that modify state (require confirmation) ──────────────────
_WRITE_ACTIONS: Set[str] = {
    "create", "update", "delete", "archive",
    "index",  # RAG reindex
}


# ══════════════════════════════════════════════════════════════════════
# Data Contracts
# ══════════════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class DecisionProposal:
    """
    Input to the ToolPlanner — output of the reasoning layer.

    Attributes:
        message:     Original user message.
        tool:        Selected tool name (or "none").
        action:      Tool action to execute.
        parameters:  Parameters to pass to the tool.
        confidence:  Reasoning confidence (0.0 – 1.0).
        reasoning:   Human-readable reasoning trace.
        missing:     Parameters missing (if validation failed).
    """

    message: str = ""
    tool: str = "none"
    action: str = ""
    parameters: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0
    reasoning: str = ""
    missing: List[Dict[str, str]] = field(default_factory=list)

    @property
    def has_tool(self) -> bool:
        return self.tool not in ("none", "greeting", "")

    @property
    def is_write(self) -> bool:
        return self.action in _WRITE_ACTIONS

    @property
    def is_valid(self) -> bool:
        return self.has_tool and not self.missing

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "message": self.message,
            "tool": self.tool,
            "action": self.action,
            "parameters": dict(self.parameters),
            "confidence": round(self.confidence, 3),
        }
        if self.reasoning:
            d["reasoning"] = self.reasoning
        if self.missing:
            d["missing"] = self.missing
        return d


@dataclass(frozen=True)
class CostEstimate:
    """Estimated execution cost for an ExecutionPlan."""

    total_ms: float = 0.0
    tool_count: int = 0
    read_count: int = 0
    write_count: int = 0
    parallel_savings_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_ms": round(self.total_ms, 1),
            "tool_count": self.tool_count,
            "read_count": self.read_count,
            "write_count": self.write_count,
            "parallel_savings_ms": round(self.parallel_savings_ms, 1),
        }


@dataclass(frozen=True)
class ToolStep:
    """
    A single tool execution step in the plan.

    Attributes:
        step_id:        Unique identifier (e.g., "step_1").
        tool:           Tool name.
        action:         Tool action.
        parameters:     Parameters to pass.
        depends_on:     Steps that must complete before this one.
        estimated_ms:   Estimated execution time.
        is_write:       Whether this step modifies state.
        timeout_ms:     Maximum execution time before timeout.
        retry_count:    Number of retries on failure.
    """

    step_id: str
    tool: str
    action: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    depends_on: List[str] = field(default_factory=list)
    estimated_ms: float = 0.0
    is_write: bool = False
    timeout_ms: float = 30000.0
    retry_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "step_id": self.step_id,
            "tool": self.tool,
            "action": self.action,
            "parameters": dict(self.parameters),
        }
        if self.depends_on:
            d["depends_on"] = list(self.depends_on)
        if self.estimated_ms:
            d["estimated_ms"] = round(self.estimated_ms, 1)
        if self.is_write:
            d["is_write"] = True
        if self.timeout_ms != 30000.0:
            d["timeout_ms"] = round(self.timeout_ms, 1)
        if self.retry_count:
            d["retry_count"] = self.retry_count
        return d


@dataclass(frozen=True)
class ConflictInfo:
    """Details of a detected conflict between tools."""

    tool_a: str
    action_a: str
    tool_b: str
    action_b: str
    reason: str = ""

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "tool_a": self.tool_a,
            "action_a": self.action_a,
            "tool_b": self.tool_b,
            "action_b": self.action_b,
        }
        if self.reason:
            d["reason"] = self.reason
        return d


@dataclass(frozen=True)
class ExecutionPlan:
    """
    Immutable execution plan — output of the ToolPlanner.

    Attributes:
        ordered_tools:           Tool steps in execution order.
        execution_mode:          "sequential" | "parallel" | "fallback" | "mixed".
        dependencies:            Mapping of step_id → list of dependency step_ids.
        estimated_cost:          Cost estimate for the entire plan.
        requires_confirmation:   True if destructive or low-confidence ops.
        confirmation_reason:     Human-readable reason for confirmation.
        fallback_plan:           Optional alternative plan on failure.
        conflicts:               Detected conflicts (informational).
        tool_count:              Number of tool steps.
        is_empty:                True when no tool is needed.
    """

    ordered_tools: List[ToolStep] = field(default_factory=list)
    execution_mode: str = ExecutionMode.SEQUENTIAL
    dependencies: Dict[str, List[str]] = field(default_factory=dict)
    estimated_cost: CostEstimate = field(default_factory=CostEstimate)
    requires_confirmation: bool = False
    confirmation_reason: str = ""
    fallback_plan: Optional["ExecutionPlan"] = None
    conflicts: List[ConflictInfo] = field(default_factory=list)
    tool_count: int = 0
    is_empty: bool = True

    @property
    def has_fallback(self) -> bool:
        return self.fallback_plan is not None

    @property
    def has_conflicts(self) -> bool:
        return len(self.conflicts) > 0

    @property
    def first_tool(self) -> Optional[ToolStep]:
        return self.ordered_tools[0] if self.ordered_tools else None

    @property
    def last_tool(self) -> Optional[ToolStep]:
        return self.ordered_tools[-1] if self.ordered_tools else None

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "ordered_tools": [s.to_dict() for s in self.ordered_tools],
            "execution_mode": self.execution_mode,
            "dependencies": dict(self.dependencies),
            "estimated_cost": self.estimated_cost.to_dict(),
            "requires_confirmation": self.requires_confirmation,
            "tool_count": self.tool_count,
            "is_empty": self.is_empty,
        }
        if self.confirmation_reason:
            d["confirmation_reason"] = self.confirmation_reason
        if self.fallback_plan is not None:
            d["fallback_plan"] = self.fallback_plan.to_dict()
        if self.conflicts:
            d["conflicts"] = [c.to_dict() for c in self.conflicts]
        return d


# ══════════════════════════════════════════════════════════════════════
# Tool Planner
# ══════════════════════════════════════════════════════════════════════


class ToolPlanner:
    """
    Framework-independent execution plan generator.

    Consumes a DecisionProposal and produces an immutable ExecutionPlan.
    Never executes tools.  Never accesses repositories.

    Usage:
        planner = ToolPlanner()
        plan = planner.plan(proposal)
        if plan.requires_confirmation:
            # ask user
        for step in plan.ordered_tools:
            # orchestrator executes step
    """

    def plan(self, proposal: DecisionProposal) -> ExecutionPlan:
        """
        Generate an ExecutionPlan from a DecisionProposal.

        Steps:
            1. Validate proposal
            2. Build tool steps
            3. Detect dependencies
            4. Detect conflicts
            5. Determine execution mode
            6. Estimate cost
            7. Check confirmation requirements
            8. Generate fallback plan
        """
        # ── 1. Empty / invalid proposal ─────────────────────────────
        if not proposal.has_tool:
            return self._empty_plan(proposal)

        if not proposal.is_valid:
            return self._invalid_plan(proposal)

        # ── 2. Build tool step ──────────────────────────────────────
        step = self._build_step(proposal)
        steps = [step]

        # ── 3. Dependencies (single tool → none) ───────────────────
        deps: Dict[str, List[str]] = {}

        # ── 4. Conflicts ───────────────────────────────────────────
        conflicts = self._detect_conflicts(proposal)

        # ── 5. Execution mode ───────────────────────────────────────
        mode = ExecutionMode.SEQUENTIAL

        # ── 6. Cost ─────────────────────────────────────────────────
        cost = self._estimate_cost(steps, mode)

        # ── 7. Confirmation ─────────────────────────────────────────
        needs_confirm, reason = self._check_confirmation(
            proposal, conflicts,
        )

        # ── 8. Fallback ─────────────────────────────────────────────
        fallback = self._build_fallback(proposal)

        return ExecutionPlan(
            ordered_tools=steps,
            execution_mode=mode,
            dependencies=deps,
            estimated_cost=cost,
            requires_confirmation=needs_confirm,
            confirmation_reason=reason,
            fallback_plan=fallback,
            conflicts=conflicts,
            tool_count=1,
            is_empty=False,
        )

    def plan_batch(
        self, proposals: List[DecisionProposal],
    ) -> ExecutionPlan:
        """
        Generate an ExecutionPlan from multiple DecisionProposals.

        Supports sequential, parallel, and fallback modes based on
        dependency analysis.
        """
        if not proposals:
            return self._empty_plan(DecisionProposal())

        valid = [p for p in proposals if p.has_tool and p.is_valid]
        if not valid:
            return self._empty_plan(DecisionProposal())

        # ── Build steps ─────────────────────────────────────────────
        steps = [
            self._build_step(p, index=i + 1)
            for i, p in enumerate(valid)
        ]

        # ── Detect cross-step dependencies ──────────────────────────
        deps = self._detect_batch_dependencies(steps)

        # ── Detect conflicts ────────────────────────────────────────
        all_conflicts: List[ConflictInfo] = []
        for p in valid:
            all_conflicts.extend(self._detect_conflicts(p))
        # Cross-step conflicts
        all_conflicts.extend(self._detect_cross_step_conflicts(steps))

        # ── Determine mode ──────────────────────────────────────────
        has_deps = any(dep_list for dep_list in deps.values())
        mode = (
            ExecutionMode.SEQUENTIAL if has_deps
            else ExecutionMode.PARALLEL
        )

        # ── Cost ────────────────────────────────────────────────────
        cost = self._estimate_cost(steps, mode)

        # ── Confirmation ────────────────────────────────────────────
        needs_confirm = any(p.is_write for p in valid)
        if all_conflicts:
            needs_confirm = True
        reason = ""
        if needs_confirm:
            reasons: List[str] = []
            if any(p.is_write for p in valid):
                reasons.append("opérations d'écriture détectées")
            if all_conflicts:
                reasons.append(
                    f"{len(all_conflicts)} conflit(s) détecté(s)"
                )
            reason = "; ".join(reasons)

        # ── Fallback ────────────────────────────────────────────────
        fallback = self._build_batch_fallback(valid)

        return ExecutionPlan(
            ordered_tools=steps,
            execution_mode=mode,
            dependencies=deps,
            estimated_cost=cost,
            requires_confirmation=needs_confirm,
            confirmation_reason=reason,
            fallback_plan=fallback,
            conflicts=all_conflicts,
            tool_count=len(steps),
            is_empty=False,
        )

    # ════════════════════════════════════════════════════════════════
    # Internal helpers
    # ════════════════════════════════════════════════════════════════

    def _empty_plan(self, proposal: DecisionProposal) -> ExecutionPlan:
        """Return an empty plan for no-tool proposals."""
        return ExecutionPlan(
            ordered_tools=[],
            execution_mode=ExecutionMode.SEQUENTIAL,
            dependencies={},
            estimated_cost=CostEstimate(),
            requires_confirmation=False,
            fallback_plan=None,
            conflicts=[],
            tool_count=0,
            is_empty=True,
        )

    def _invalid_plan(self, proposal: DecisionProposal) -> ExecutionPlan:
        """Return a plan that requires confirmation for invalid proposals."""
        step = ToolStep(
            step_id="step_1",
            tool=proposal.tool,
            action=proposal.action,
            parameters=dict(proposal.parameters),
            depends_on=[],
            estimated_ms=_get_tool_ms(proposal.tool),
            is_write=proposal.is_write,
            timeout_ms=30000.0,
            retry_count=0,
        )
        missing_desc = ", ".join(
            m.get("name", "?") for m in proposal.missing
        )
        return ExecutionPlan(
            ordered_tools=[step],
            execution_mode=ExecutionMode.SEQUENTIAL,
            dependencies={},
            estimated_cost=CostEstimate(
                total_ms=step.estimated_ms,
                tool_count=1,
                read_count=0 if proposal.is_write else 1,
                write_count=1 if proposal.is_write else 0,
            ),
            requires_confirmation=True,
            confirmation_reason=(
                f"Paramètres manquants : {missing_desc}"
            ),
            fallback_plan=None,
            conflicts=[],
            tool_count=1,
            is_empty=False,
        )

    def _build_step(
        self, proposal: DecisionProposal, index: int = 1,
    ) -> ToolStep:
        """Build a single ToolStep from a proposal."""
        meta = _TOOL_META.get(proposal.tool, (200.0, False, "unknown"))
        est_ms = meta[0]
        is_write = proposal.action in _WRITE_ACTIONS
        timeout = 60000.0 if is_write else 30000.0
        retries = 0 if is_write else 1

        return ToolStep(
            step_id=f"step_{index}",
            tool=proposal.tool,
            action=proposal.action,
            parameters=dict(proposal.parameters),
            depends_on=[],
            estimated_ms=est_ms,
            is_write=is_write,
            timeout_ms=timeout,
            retry_count=retries,
        )

    def _detect_conflicts(
        self, proposal: DecisionProposal,
    ) -> List[ConflictInfo]:
        """Detect conflicts for a single proposal."""
        conflicts: List[ConflictInfo] = []
        key = (proposal.tool, proposal.action)
        rules = _CONFLICT_RULES.get(key, [])
        for other_tool, other_action in rules:
            conflicts.append(ConflictInfo(
                tool_a=proposal.tool,
                action_a=proposal.action,
                tool_b=other_tool,
                action_b=other_action,
                reason=(
                    f"{proposal.tool}.{proposal.action} peut "
                    f"entrer en conflit avec "
                    f"{other_tool}.{other_action}"
                ),
            ))
        return conflicts

    def _detect_cross_step_conflicts(
        self, steps: List[ToolStep],
    ) -> List[ConflictInfo]:
        """Detect conflicts between different steps in a batch."""
        conflicts: List[ConflictInfo] = []
        for i, a in enumerate(steps):
            for b in steps[i + 1:]:
                if a.tool == b.tool and a.action != b.action:
                    # Same tool, different actions — potential conflict
                    a_is_write = a.action in _WRITE_ACTIONS
                    b_is_write = b.action in _WRITE_ACTIONS
                    if a_is_write or b_is_write:
                        conflicts.append(ConflictInfo(
                            tool_a=a.tool,
                            action_a=a.action,
                            tool_b=b.tool,
                            action_b=b.action,
                            reason=(
                                f"Même outil '{a.tool}' avec "
                                f"actions différentes et opération "
                                f"d'écriture"
                            ),
                        ))
        return conflicts

    def _detect_batch_dependencies(
        self, steps: List[ToolStep],
    ) -> Dict[str, List[str]]:
        """Detect dependencies between steps in a batch."""
        deps: Dict[str, List[str]] = {s.step_id: [] for s in steps}

        for i, consumer in enumerate(steps):
            consumer_cat = _get_category(consumer.tool)
            for j, provider in enumerate(steps):
                if i == j:
                    continue
                provider_cat = _get_category(provider.tool)
                # Check if consumer's category depends on provider's
                depends_on_cats = _DEPENDENCY_GRAPH.get(provider_cat, [])
                if consumer_cat in depends_on_cats:
                    deps[consumer.step_id].append(provider.step_id)

        return deps

    def _estimate_cost(
        self,
        steps: List[ToolStep],
        mode: str,
    ) -> CostEstimate:
        """Estimate total execution cost."""
        total_ms = sum(s.estimated_ms for s in steps)
        read_count = sum(1 for s in steps if not s.is_write)
        write_count = sum(1 for s in steps if s.is_write)

        # Parallel savings: if parallel, total is max而非 sum
        parallel_savings = 0.0
        if mode == ExecutionMode.PARALLEL and len(steps) > 1:
            sequential_ms = total_ms
            parallel_ms = max(s.estimated_ms for s in steps)
            parallel_savings = sequential_ms - parallel_ms
            total_ms = parallel_ms

        return CostEstimate(
            total_ms=total_ms,
            tool_count=len(steps),
            read_count=read_count,
            write_count=write_count,
            parallel_savings_ms=parallel_savings,
        )

    def _check_confirmation(
        self,
        proposal: DecisionProposal,
        conflicts: List[ConflictInfo],
    ) -> Tuple[bool, str]:
        """Determine if user confirmation is required."""
        reasons: List[str] = []

        if proposal.is_write:
            reasons.append(
                f"Opération d'écriture : {proposal.tool}.{proposal.action}"
            )

        if proposal.confidence < 0.5:
            reasons.append(
                f"Confiance faible : {proposal.confidence:.2f}"
            )

        if conflicts:
            reasons.append(
                f"{len(conflicts)} conflit(s) potentiel(s)"
            )

        if reasons:
            return True, "; ".join(reasons)
        return False, ""

    def _build_fallback(
        self, proposal: DecisionProposal,
    ) -> Optional[ExecutionPlan]:
        """
        Build a fallback plan for when the primary tool fails.

        Rules:
            - Read tools: fallback to RAG knowledge search
            - Write tools: no automatic fallback (requires manual retry)
            - Greeting / none: no fallback
        """
        if proposal.is_write:
            return None

        if not proposal.has_tool:
            return None

        # Fallback: RAG knowledge search
        fallback_proposal = DecisionProposal(
            message=proposal.message,
            tool="rag_knowledge_tool",
            action="search",
            parameters={"query": proposal.message},
            confidence=0.5,
            reasoning="Fallback vers RAG en cas d'échec",
        )
        step = self._build_step(fallback_proposal)
        cost = self._estimate_cost([step], ExecutionMode.SEQUENTIAL)

        return ExecutionPlan(
            ordered_tools=[step],
            execution_mode=ExecutionMode.SEQUENTIAL,
            dependencies={},
            estimated_cost=cost,
            requires_confirmation=False,
            fallback_plan=None,
            conflicts=[],
            tool_count=1,
            is_empty=False,
        )

    def _build_batch_fallback(
        self, proposals: List[DecisionProposal],
    ) -> Optional[ExecutionPlan]:
        """Build a fallback plan for a batch of proposals."""
        read_proposals = [p for p in proposals if not p.is_write]
        if not read_proposals:
            return None

        # Fallback: RAG search for all read operations
        fallback_proposal = DecisionProposal(
            message=read_proposals[0].message,
            tool="rag_knowledge_tool",
            action="search",
            parameters={"query": read_proposals[0].message},
            confidence=0.5,
            reasoning="Fallback batch vers RAG",
        )
        step = self._build_step(fallback_proposal)
        cost = self._estimate_cost([step], ExecutionMode.SEQUENTIAL)

        return ExecutionPlan(
            ordered_tools=[step],
            execution_mode=ExecutionMode.SEQUENTIAL,
            dependencies={},
            estimated_cost=cost,
            requires_confirmation=False,
            fallback_plan=None,
            conflicts=[],
            tool_count=1,
            is_empty=False,
        )


# ══════════════════════════════════════════════════════════════════════
# Module-level helpers
# ══════════════════════════════════════════════════════════════════════


def _get_tool_ms(tool: str) -> float:
    """Get estimated execution time for a tool."""
    meta = _TOOL_META.get(tool)
    return meta[0] if meta else 200.0


def _get_category(tool: str) -> str:
    """Get the category of a tool."""
    meta = _TOOL_META.get(tool)
    return meta[2] if meta else "unknown"
