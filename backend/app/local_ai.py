from __future__ import annotations
import asyncio
from dataclasses import dataclass
import json
from typing import Any
from urllib.parse import urlparse
import httpx
from .settings import get_settings
class LocalAIError(RuntimeError):pass
SYSTEM_PROMPT="""You are FCC Assistant, a local read-only process analysis assistant.
Use only the process evidence supplied in the prompt. Never invent tag values, causes, alarms, limits, or operating events. Clearly separate observed facts from calculated results and possible engineering hypotheses. Do not recommend changing plant setpoints or controls. Current mode is analysis and reporting only."""
@dataclass(frozen=True)
class LocalAIResponse:model:str;text:str
def _is_local_url(url:str)->bool:
    try:parsed=urlparse(url)
    except ValueError:return False
    return parsed.scheme in {"http","https"} and parsed.hostname in {"localhost","127.0.0.1","::1"}
def _model_ids(payload:object)->list[str]:
    if not isinstance(payload,dict):return []
    data=payload.get("data")
    if not isinstance(data,list):return []
    return [str(x.get("id","")) for x in data if isinstance(x,dict) and x.get("id")]
def _model_matches(ids:list[str],configured:str)->bool:
    if not ids:return False
    needle=configured.casefold().replace(".gguf","").strip()
    return any(needle in x.casefold().replace(".gguf","") or "qwen3-4b" in x.casefold() for x in ids)
class LocalAIClient:
    _embedded_lock:asyncio.Lock|None=None
    def __init__(self)->None:
        s=get_settings();self.travis_url=s.travis_ai_url.rstrip("/");self.travis_timeout=s.travis_ai_timeout_seconds;self.prefer_travis=s.prefer_travis_ai;self.base_url=s.local_ai_url.rstrip("/");self.model=s.local_ai_model_name.strip() or "embedded-local-model";self.timeout=s.local_ai_timeout_seconds
        if self.travis_url and not _is_local_url(self.travis_url):raise LocalAIError("TRAVIS endpoint must be localhost only")
        if not _is_local_url(self.base_url):raise LocalAIError("External AI endpoints are blocked. Only localhost is allowed.")
    @classmethod
    def _lock(cls)->asyncio.Lock:
        # Construct lazily inside the active uvicorn event loop. Qwen/llama.cpp is
        # a single local reasoning resource; serializing dashboard requests avoids
        # slot/context collisions and makes command ordering deterministic.
        if cls._embedded_lock is None:cls._embedded_lock=asyncio.Lock()
        return cls._embedded_lock
    async def status(self)->dict[str,Any]:
        if self.prefer_travis:
            try:
                async with httpx.AsyncClient(timeout=min(self.travis_timeout,5.0)) as c:r=await c.get(f"{self.travis_url}/v1/fcc/status");r.raise_for_status();p=r.json()
                if isinstance(p,dict):return {"configured":True,"connected":True,"runtime":"TRAVIS","provider":"TRAVIS","model":p.get("model"),"local_only_link":True,"travis":p}
            except Exception:pass
        try:
            async with httpx.AsyncClient(timeout=5.0) as c:r=await c.get(f"{self.base_url}/v1/models");r.raise_for_status();p=r.json()
            ids=_model_ids(p)
            if not _model_matches(ids,self.model):return {"configured":True,"connected":False,"runtime":"llama.cpp","provider":"embedded-local","model":self.model,"local_only":True,"detail":"Local endpoint responded but model identity did not match FCC Assistant","models":ids}
            return {"configured":True,"connected":True,"runtime":"llama.cpp","provider":"embedded-local","model":self.model,"local_only":True,"models":ids}
        except Exception as exc:return {"configured":True,"connected":False,"runtime":"llama.cpp","provider":"embedded-local","model":self.model,"local_only":True,"detail":f"{type(exc).__name__}: {exc}"}
    async def generate(self,user_prompt:str,context:dict[str,Any]|None=None,*,system_prompt:str|None=None,temperature:float=0.1)->LocalAIResponse:
        prompt=user_prompt.strip()
        if not prompt:raise LocalAIError("Prompt cannot be empty")
        if self.prefer_travis and system_prompt is None:
            try:return await self._generate_with_travis(prompt,context)
            except LocalAIError:pass
        async with self._lock():return await self._generate_with_embedded(prompt,context,system_prompt=system_prompt,temperature=temperature)
    async def _generate_with_travis(self,prompt,context):
        if not self.travis_url or not _is_local_url(self.travis_url):raise LocalAIError("TRAVIS local bridge is not configured")
        body={"source":"fcc-assistant","mode":"read_only_process_analysis","question":prompt,"system_prompt":SYSTEM_PROMPT,"evidence":context or {},"data_policy":"local_only_no_external_process_data"}
        try:
            async with httpx.AsyncClient(timeout=self.travis_timeout) as c:r=await c.post(f"{self.travis_url}/v1/fcc/analyze",json=body);r.raise_for_status();p=r.json()
        except Exception as exc:raise LocalAIError(f"TRAVIS is not reachable: {exc}") from exc
        text=p.get("answer") if isinstance(p,dict) else None
        if not isinstance(text,str) or not text.strip():raise LocalAIError("TRAVIS returned an empty or invalid response")
        return LocalAIResponse(model=str(p.get("provider") or "TRAVIS"),text=text.strip())
    async def _generate_with_embedded(self,prompt,context,*,system_prompt=None,temperature=0.1):
        evidence="\n\nLOCAL STRUCTURED CONTEXT:\n"+json.dumps(context,ensure_ascii=False,separators=(",",":")) if context else ""
        body={"model":self.model,"stream":False,"temperature":max(0.0,min(float(temperature),1.0)),"messages":[{"role":"system","content":system_prompt or SYSTEM_PROMPT},{"role":"user","content":f"{prompt}{evidence}"}]}
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as c:
                r=await c.post(f"{self.base_url}/v1/chat/completions",json=body)
                if r.is_error:
                    detail=r.text.strip().replace("\n"," ")[:800]
                    raise LocalAIError(f"Embedded local AI HTTP {r.status_code}: {detail or 'no response body'}")
                p=r.json()
        except LocalAIError:raise
        except Exception as exc:raise LocalAIError(f"Embedded local AI request failed: {type(exc).__name__}: {exc}") from exc
        try:text=p["choices"][0]["message"]["content"]
        except (KeyError,IndexError,TypeError) as exc:raise LocalAIError("Embedded local AI returned an invalid response") from exc
        if not isinstance(text,str) or not text.strip():raise LocalAIError("Embedded local AI returned an empty response")
        return LocalAIResponse(model=self.model,text=text.strip())
