import pytest

from app.agent_runtime import AgentPlan, AgentRuntime, AgentRuntimeError, StepStatus, step
from app.agent_tools import ToolContext, ToolDefinition, ToolEffect, ToolRegistry
from app.refinery_model import AccessGrant, DataDomain, RefineryScope, ScopeKind, UnitScope

@pytest.fixture
def context():
    refinery=RefineryScope(id="site",name="Site",standalone_units=(UnitScope("fcc","FCC"),))
    access=AccessGrant(domains=frozenset({DataDomain.PROCESS}),unit_ids=frozenset({"fcc"}))
    return ToolContext(actor_id="u1",refinery=refinery,access=access,scope_kind=ScopeKind.UNIT,scope_id="fcc")

@pytest.mark.asyncio
async def test_executes_dependency_order_and_collects_evidence(context):
    registry=ToolRegistry()
    async def first(tool_context,arguments): return {"value":1}
    async def second(tool_context,arguments): return {"value":2}
    registry.register(ToolDefinition(name="first",description="first",domain=DataDomain.PROCESS,effect=ToolEffect.READ_ONLY),first)
    registry.register(ToolDefinition(name="second",description="second",domain=DataDomain.PROCESS,effect=ToolEffect.READ_ONLY),second)
    plan=AgentPlan(goal="investigate",steps=(step("first",{},step_id="a"),step("second",{},step_id="b",depends_on=("a",))))
    run=await AgentRuntime(registry).execute(plan,context=context)
    assert run.completed is True and run.failed is False
    assert run.executions["a"].status==StepStatus.SUCCEEDED
    assert run.executions["b"].status==StepStatus.SUCCEEDED
    assert [item["tool"] for item in run.evidence]==["first","second"]
    assert run.evidence[0]["data"]=={"value":1}

def test_rejects_dependency_cycle():
    plan=AgentPlan(goal="cycle",steps=(step("x",{},step_id="a",depends_on=("b",)),step("x",{},step_id="b",depends_on=("a",))))
    with pytest.raises(AgentRuntimeError,match="cycle"): AgentRuntime.validate(plan)

@pytest.mark.asyncio
async def test_failed_dependency_blocks_following_steps(context):
    registry=ToolRegistry()
    async def fail(tool_context,arguments): raise RuntimeError("boom")
    async def should_not_run(tool_context,arguments): raise AssertionError("must not execute")
    registry.register(ToolDefinition(name="fail",description="fail",domain=DataDomain.PROCESS,effect=ToolEffect.READ_ONLY),fail)
    registry.register(ToolDefinition(name="later",description="later",domain=DataDomain.PROCESS,effect=ToolEffect.READ_ONLY),should_not_run)
    plan=AgentPlan(goal="failure",steps=(step("fail",{},step_id="a"),step("later",{},step_id="b",depends_on=("a",))))
    run=await AgentRuntime(registry).execute(plan,context=context,stop_on_error=False)
    assert run.failed is True
    assert run.executions["a"].status==StepStatus.FAILED
    assert run.executions["b"].status==StepStatus.SKIPPED
