"""Autonomous multi-step execution runtime for the refinery assistant.

The runtime executes validated tool plans against the governed ToolRegistry.
It deliberately keeps planning and execution separate: an LLM or deterministic
planner may propose steps, but only registered tools are allowed to execute.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Any, Callable, Iterable
from uuid import uuid4

from .agent_tools import ToolContext, ToolRegistry, ToolResult


class StepStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass(frozen=True)
class AgentStep:
    id: str
    tool_name: str
    arguments: dict[str, Any]
    depends_on: tuple[str, ...] = ()
    description: str = ""


@dataclass
class StepExecution:
    step: AgentStep
    status: StepStatus = StepStatus.PENDING
    result: ToolResult | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "step": asdict(self.step),
            "status": self.status.value,
            "result": self.result.to_dict() if self.result is not None else None,
            "error": self.error,
        }


@dataclass(frozen=True)
class AgentPlan:
    goal: str
    steps: tuple[AgentStep, ...]
    plan_id: str = field(default_factory=lambda: f"plan-{uuid4().hex}")


@dataclass
class AgentRun:
    plan: AgentPlan
    executions: dict[str, StepExecution]
    completed: bool = False
    failed: bool = False

    @property
    def evidence(self) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for execution in self.executions.values():
            if execution.result is None:
                continue
            items.append(
                {
                    "step_id": execution.step.id,
                    "tool": execution.step.tool_name,
                    "provenance": execution.result.provenance,
                    "data": execution.result.data,
                }
            )
        return items

    def to_dict(self) -> dict[str, Any]:
        return {
            "plan_id": self.plan.plan_id,
            "goal": self.plan.goal,
            "completed": self.completed,
            "failed": self.failed,
            "executions": [item.to_dict() for item in self.executions.values()],
            "evidence": self.evidence,
        }


class AgentRuntimeError(RuntimeError):
    pass


ArgumentResolver = Callable[[dict[str, Any], AgentRun], dict[str, Any]]


class AgentRuntime:
    """Execute dependency-aware, governed refinery tool plans."""

    def __init__(self, registry: ToolRegistry) -> None:
        self.registry = registry

    @staticmethod
    def validate(plan: AgentPlan) -> None:
        if not plan.goal.strip():
            raise AgentRuntimeError("Agent plan goal is required")
        if not plan.steps:
            raise AgentRuntimeError("Agent plan requires at least one step")

        ids = [step.id for step in plan.steps]
        if any(not value.strip() for value in ids):
            raise AgentRuntimeError("Every agent step requires an id")
        if len(set(ids)) != len(ids):
            raise AgentRuntimeError("Agent step ids must be unique")

        known = set(ids)
        for step in plan.steps:
            unknown = [dependency for dependency in step.depends_on if dependency not in known]
            if unknown:
                raise AgentRuntimeError(
                    f"Step {step.id} references unknown dependencies: {', '.join(unknown)}"
                )
            if step.id in step.depends_on:
                raise AgentRuntimeError(f"Step {step.id} cannot depend on itself")

        # Detect dependency cycles before any tool runs.
        visiting: set[str] = set()
        visited: set[str] = set()
        by_id = {step.id: step for step in plan.steps}

        def visit(step_id: str) -> None:
            if step_id in visited:
                return
            if step_id in visiting:
                raise AgentRuntimeError("Agent plan contains a dependency cycle")
            visiting.add(step_id)
            for dependency in by_id[step_id].depends_on:
                visit(dependency)
            visiting.remove(step_id)
            visited.add(step_id)

        for step_id in ids:
            visit(step_id)

    async def execute(
        self,
        plan: AgentPlan,
        *,
        context: ToolContext,
        argument_resolver: ArgumentResolver | None = None,
        stop_on_error: bool = True,
    ) -> AgentRun:
        self.validate(plan)
        executions = {step.id: StepExecution(step=step) for step in plan.steps}
        run = AgentRun(plan=plan, executions=executions)

        pending = set(executions)
        while pending:
            progressed = False
            for step in plan.steps:
                if step.id not in pending:
                    continue
                execution = executions[step.id]
                dependencies = [executions[item] for item in step.depends_on]

                if any(item.status == StepStatus.FAILED for item in dependencies):
                    execution.status = StepStatus.SKIPPED
                    execution.error = "Dependency failed"
                    pending.remove(step.id)
                    progressed = True
                    continue
                if any(item.status != StepStatus.SUCCEEDED for item in dependencies):
                    continue

                execution.status = StepStatus.RUNNING
                try:
                    arguments = dict(step.arguments)
                    if argument_resolver is not None:
                        arguments = argument_resolver(arguments, run)
                    execution.result = await self.registry.execute(
                        step.tool_name,
                        arguments=arguments,
                        context=context,
                    )
                    execution.status = StepStatus.SUCCEEDED
                except Exception as exc:  # registry normalizes policy and tool failures
                    execution.status = StepStatus.FAILED
                    execution.error = str(exc)
                    run.failed = True
                    if stop_on_error:
                        pending.remove(step.id)
                        for remaining_id in list(pending):
                            remaining = executions[remaining_id]
                            remaining.status = StepStatus.SKIPPED
                            remaining.error = "Run stopped after previous tool failure"
                            pending.remove(remaining_id)
                        run.completed = True
                        return run
                pending.remove(step.id)
                progressed = True

            if not progressed:
                raise AgentRuntimeError("Agent plan could not make progress")

        run.completed = True
        return run


def step(
    tool_name: str,
    arguments: dict[str, Any],
    *,
    step_id: str | None = None,
    depends_on: Iterable[str] = (),
    description: str = "",
) -> AgentStep:
    return AgentStep(
        id=step_id or f"step-{uuid4().hex}",
        tool_name=tool_name,
        arguments=dict(arguments),
        depends_on=tuple(depends_on),
        description=description,
    )
