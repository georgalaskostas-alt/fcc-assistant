"""Server-owned identity adapter for investigation APIs.

Phase 1 has one local workstation identity. Request payloads never choose the
actor or authorization grant. Enterprise deployment can replace this adapter
with OS/SSO identity and directory-backed role/scope grants.
"""
from __future__ import annotations
import os
from dataclasses import dataclass

@dataclass(frozen=True)
class ActiveIdentity:
    actor_id:str
    source:str
    authenticated:bool
    unit_ids:frozenset[str]

def _unit_ids()->frozenset[str]:
    raw=os.getenv("FCC_ASSISTANT_UNIT_IDS","fcc,hcu")
    return frozenset(x.strip().casefold() for x in raw.split(",") if x.strip())

def active_identity()->ActiveIdentity:
    actor=(os.getenv("FCC_ASSISTANT_ACTOR_ID") or "local-engineer").strip()
    return ActiveIdentity(actor_id=actor or "local-engineer",source="phase1-local-server",
                          authenticated=False,unit_ids=_unit_ids())
