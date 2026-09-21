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


def explain_branch_budget(*, branches:list[dict[str,Any]], allocation:dict[str,int], path_gain_history:list[dict[str,Any]], mode:str)->list[dict[str,Any]]:
    """Create deterministic human-readable reasons for the current branch allocation."""
    by_id={str(b.get("branch_id")):b for b in branches if isinstance(b,dict) and b.get("branch_id")}
    history:dict[str,dict[str,float]]={}
    for item in path_gain_history:
        if not isinstance(item,dict):continue
        branch_id=str(item.get("hypothesis_branch_id") or "")
        if not branch_id:continue
        slot=history.setdefault(branch_id,{"attempts":0.0,"useful":0.0,"limited":0.0,"no_gain":0.0,"score_total":0.0})
        slot["attempts"]+=1;slot["score_total"]+=float(item.get("score") or 0.0)
        classification=str(item.get("classification") or "")
        if classification=="useful_path":slot["useful"]+=1
        elif classification=="limited_path":slot["limited"]+=1
        elif classification=="no_information_gain":slot["no_gain"]+=1
    rows=[]
    for branch_id,branch in by_id.items():
        calls=int(allocation.get(branch_id,0));stats=history.get(branch_id,{})
        attempts=int(stats.get("attempts") or 0);useful=int(stats.get("useful") or 0);no_gain=int(stats.get("no_gain") or 0)
        mean=round(float(stats.get("score_total") or 0.0)/max(1,attempts),3)
        if mode=="balanced_initial":reason="Initial balanced exploration across active hypotheses."
        elif calls==0 and no_gain>0 and useful==0:reason="No repeated budget: prior process-path exploration produced no information gain."
        elif attempts==0 and calls>0:reason="Exploration slot reserved because this hypothesis has not yet been tested."
        elif useful>0 and calls>0:reason="Budget retained or increased because prior process-path exploration produced useful evidence."
        elif calls>0:reason="Budget retained for an active hypothesis within the hard investigation limit."
        else:reason="No tool call allocated in this bounded round."
        rows.append({"hypothesis_branch_id":branch_id,"allocated_calls":calls,"state":branch.get("state"),"priority":branch.get("priority"),"branch_score":branch.get("score"),"prior_attempts":attempts,"prior_useful_paths":useful,"prior_no_gain_paths":no_gain,"prior_mean_path_gain":mean,"reason":reason})
    return rows
