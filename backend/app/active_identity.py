"""Server-owned identity adapter for investigation APIs.

Phase 1 has one local workstation identity. Request payloads must not choose the
actor. Enterprise deployment can replace this adapter with OS/SSO identity.
"""
from __future__ import annotations
import os
from dataclasses import dataclass

@dataclass(frozen=True)
class ActiveIdentity:
    actor_id:str
    source:str
    authenticated:bool

def active_identity()->ActiveIdentity:
    actor=(os.getenv("FCC_ASSISTANT_ACTOR_ID") or "local-engineer").strip()
    return ActiveIdentity(actor_id=actor or "local-engineer",source="phase1-local-server",authenticated=False)
