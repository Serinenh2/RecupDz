"""
AI Workflow Engine — complete workflow orchestration system.

Architecture:
  WorkflowEngine (orchestrator)
    └── WorkflowAgent (integrator)
          ├── DecisionTree (branching logic)
          ├── TaskQueue (scheduling)
          ├── ExecutionGraph (DAG resolution)
          ├── InputValidator / OutputValidator (validation)
          ├── RecoveryEngine (error recovery)
          └── WorkflowReasoner (intelligent decisions)

Usage:
    from apps.ai_assistant.workflows import WorkflowEngine, WorkflowBuilder

    engine = WorkflowEngine()
    engine.register_handler("search", my_handler)

    wf = (
        WorkflowBuilder("example", "Example Workflow")
        .step("fetch", "Fetch Data", tool_name="fetch")
        .step("process", "Process", tool_name="process")
        .depends("process", "fetch")
        .build()
    )
    engine.register_workflow(wf)
    result = engine.execute("example", {"input": "data"})
"""

from apps.ai_assistant.workflows.models import *
from apps.ai_assistant.workflows.engine import WorkflowEngine
from apps.ai_assistant.workflows.agent.agent import WorkflowAgent, AgentConfig
from apps.ai_assistant.workflows.decision_tree.engine import DecisionTree
from apps.ai_assistant.workflows.task_queue.queue import TaskQueue
from apps.ai_assistant.workflows.execution_graph.graph import ExecutionGraph
from apps.ai_assistant.workflows.validation.engine import InputValidator, OutputValidator, WorkflowValidator
from apps.ai_assistant.workflows.recovery.engine import RecoveryEngine
from apps.ai_assistant.workflows.reasoner.reasoner import WorkflowReasoner
from apps.ai_assistant.workflows.planner.planner import WorkflowPlanner, PlannerGoal, PlannerStep
from apps.ai_assistant.workflows.builders.builder import WorkflowBuilder, build_linear, build_parallel_join

__all__ = [
    "WorkflowEngine",
    "WorkflowAgent",
    "AgentConfig",
    "DecisionTree",
    "TaskQueue",
    "ExecutionGraph",
    "InputValidator",
    "OutputValidator",
    "WorkflowValidator",
    "RecoveryEngine",
    "WorkflowReasoner",
    "WorkflowPlanner",
    "PlannerGoal",
    "PlannerStep",
    "WorkflowBuilder",
    "build_linear",
    "build_parallel_join",
]
