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


def allocate_branch_tool_budget(*, branches:list[dict[str,Any]], remaining_calls:int, max_actions:int=3)->dict[str,int]:
    """Allocate the next bounded tool-call slice across active hypothesis branches."""
    active=[b for b in branches if isinstance(b,dict) and b.get("state")!="prune" and b.get("branch_id")]
    if not active or remaining_calls<=0 or max_actions<=0:return {}
    ranked=sorted(active,key=lambda b:(int(b.get("priority") or 999),-float(b.get("score") or 0.0),str(b.get("branch_id"))))
    slots=min(remaining_calls,max_actions)
    allocation={str(b["branch_id"]):0 for b in ranked}
    # First preserve competing explanations when budget allows.
    for branch in ranked[:slots]:
        allocation[str(branch["branch_id"])]+=1
    slots-=min(slots,len(ranked))
    # Then give remaining capacity to promoted/high-priority branches.
    weighted=sorted(ranked,key=lambda b:(0 if b.get("state")=="promote" else 1,int(b.get("priority") or 999),-float(b.get("score") or 0.0)))
    i=0
    while slots>0 and weighted:
        allocation[str(weighted[i%len(weighted)]["branch_id"])]+=1;i+=1;slots-=1
    return {k:v for k,v in allocation.items() if v>0}


def adaptive_branch_tool_budget(*, branches:list[dict[str,Any]], remaining_calls:int, path_gain_history:list[dict[str,Any]], max_actions:int=3)->dict[str,int]:
    """Reallocate the next bounded slice using branch-specific realized information gain."""
    active=[b for b in branches if isinstance(b,dict) and b.get("state")!="prune" and b.get("branch_id")]
    if not active or remaining_calls<=0 or max_actions<=0:return {}
    gain:dict[str,dict[str,float]]={}
    for item in path_gain_history:
        if not isinstance(item,dict):continue
        branch_id=str(item.get("hypothesis_branch_id") or "")
        if not branch_id:continue
        slot=gain.setdefault(branch_id,{"attempts":0.0,"useful":0.0,"no_gain":0.0,"score":0.0})
        slot["attempts"]+=1;slot["score"]+=float(item.get("score") or 0.0)
        if item.get("classification")=="useful_path":slot["useful"]+=1
        elif item.get("classification")=="no_information_gain":slot["no_gain"]+=1
    def adaptive_score(branch:dict[str,Any])->float:
        branch_id=str(branch.get("branch_id"));history=gain.get(branch_id,{})
        mean=float(history.get("score") or 0.0)/max(1.0,float(history.get("attempts") or 0.0))
        state_bonus=1.5 if branch.get("state")=="promote" else -1.0 if branch.get("state")=="weaken" else 0.0
        return float(branch.get("score") or 0.0)+state_bonus+min(3.0,mean*.5)+float(history.get("useful") or 0.0)-float(history.get("no_gain") or 0.0)*1.5
    ranked=sorted(active,key=lambda b:(-adaptive_score(b),int(b.get("priority") or 999),str(b.get("branch_id"))))
    slots=min(remaining_calls,max_actions)
    allocation:dict[str,int]={}
    # Keep one exploration slot for the best branch without realized feedback when possible.
    unexplored=[b for b in ranked if str(b.get("branch_id")) not in gain]
    exploration_branch_id=""
    if unexplored and slots>1:
        exploratory=unexplored[0];exploration_branch_id=str(exploratory["branch_id"]);allocation[exploration_branch_id]=1;slots-=1
    exploitation_ranked=[b for b in ranked if str(b.get("branch_id"))!=exploration_branch_id] or ranked
    i=0
    while slots>0 and exploitation_ranked:
        branch=exploitation_ranked[i%len(exploitation_ranked)];branch_id=str(branch["branch_id"])
        # A branch with only no-gain history gets no repeated slot while alternatives exist.
        history=gain.get(branch_id,{})
        if float(history.get("no_gain") or 0)>0 and float(history.get("useful") or 0)==0 and len(exploitation_ranked)>1:
            i+=1
            if i>len(exploitation_ranked)*2:break
            continue
        allocation[branch_id]=allocation.get(branch_id,0)+1;slots-=1;i+=1
    return allocation
