"""Hard budgets for autonomous refinery investigations.

Budgets limit autonomous work independently of planner/model behavior. They do
not grant permissions and cannot expand the read-only tool boundary.
"""
from __future__ import annotations
from dataclasses import dataclass,field
from typing import Any

@dataclass
class InvestigationBudget:
    max_rounds:int=3
    max_actions_per_round:int=3
    max_total_tool_calls:int=7
    tool_calls_used:int=0
    denied_actions:int=0
    history:list[dict[str,Any]]=field(default_factory=list)

    @property
    def remaining_tool_calls(self)->int:
        return max(0,self.max_total_tool_calls-self.tool_calls_used)

    def allowance(self,requested:int)->int:
        return max(0,min(requested,self.max_actions_per_round,self.remaining_tool_calls))

    def record(self,*,round_number:int,requested:int,executed:int)->None:
        self.tool_calls_used+=max(0,executed)
        self.denied_actions+=max(0,requested-executed)
        self.history.append({"round":round_number,"requested":requested,"executed":executed,
                             "remaining_tool_calls":self.remaining_tool_calls})

    def to_dict(self)->dict[str,Any]:
        return {"max_rounds":self.max_rounds,"max_actions_per_round":self.max_actions_per_round,
                "max_total_tool_calls":self.max_total_tool_calls,"tool_calls_used":self.tool_calls_used,
                "remaining_tool_calls":self.remaining_tool_calls,"denied_actions":self.denied_actions,
                "history":list(self.history)}
