"""Local vision-language P&ID interpretation: hypotheses only, never verified topology."""
from __future__ import annotations
import base64
import json
import os
import re
from urllib.parse import urlparse

import httpx
from fastapi import APIRouter, File, Form, HTTPException, UploadFile

router = APIRouter(prefix="/api/v1/pid", tags=["pid-vision"])
MAX_IMAGE = 12 * 1024 * 1024
MAX_OUTPUT = 12000
PROMPT = """You are an experienced process instrumentation engineer examining ONE P&ID image.
Identify visible instrument bubbles, valves, equipment, pipe labels, and likely connections.
Return JSON ONLY with keys: symbols (array), connections (array), uncertainties (array), summary (string).
Each symbol: {tag:string, kind:string, bbox:[x1,y1,x2,y2] or null, evidence:string, confidence:number}.
Each connection: {from:string,to:string,evidence:string,confidence:number}.
Bounding boxes normalized 0..1. Do not invent unseen tags or connectivity.
Distinguish line crossings without junctions from actual connected branches.
When uncertain, leave the connection out and explain uncertainty.
Do not confuse notes, material classes, line sizes, or drawing references with instruments.
Never infer a plant action or claim a verified circuit. Image may be partial/oblique."""
def validate_output(raw: object) -> dict:
    if not isinstance(raw, dict):
        raise ValueError("Vision response is not a JSON object")
    symbols, connections = [], []
    for item in raw.get("symbols", [])[:250] if isinstance(raw.get("symbols"),list) else []:
        if not isinstance(item,dict): continue
        tag=str(item.get("tag",""))[:80].strip()
        kind=str(item.get("kind","unknown"))[:80]
        box=item.get("bbox")
        if not isinstance(box,list) or len(box)!=4 or not all(isinstance(n,(int,float)) and 0<=n<=1 for n in box) or box[2]<=box[0] or box[3]<=box[1]:
            box=None
        symbols.append({"tag":tag,"kind":kind,"bbox":box,"evidence":str(item.get("evidence",""))[:350],"confidence":max(0.,min(1.,float(item.get("confidence",0)))) if isinstance(item.get("confidence"),(int,float)) else 0.})
    for item in raw.get("connections",[])[:250] if isinstance(raw.get("connections"),list) else []:
        if not isinstance(item,dict): continue
        a,b=str(item.get("from",""))[:80],str(item.get("to",""))[:80]
        if not a or not b or a==b: continue
        connections.append({"from":a,"to":b,"evidence":str(item.get("evidence",""))[:350],"confidence":max(0.,min(1.,float(item.get("confidence",0)))) if isinstance(item.get("confidence"),(int,float)) else 0.})
    uncertainties=raw.get("uncertainties",[])
    return {"symbols":symbols,"connections":connections,"uncertainties":[str(x)[:300] for x in uncertainties[:100]] if isinstance(uncertainties,list) else [],"summary":str(raw.get("summary",""))[:3000],"verified":False}
@router.post("/vision/analyze")
async def analyze_pid_vision(file: UploadFile=File(...), model: str=Form("qwen2.5vl:7b")):
    content=await file.read(MAX_IMAGE+1)
    if len(content)>MAX_IMAGE: raise HTTPException(413,"Image exceeds 12 MB")
    if not (content.startswith(b"\x89PNG\r\n\x1a\n") or content.startswith(b"\xff\xd8\xff")):
        raise HTTPException(415,"Only PNG/JPEG P&ID images supported")
    if not re.fullmatch(r"[A-Za-z0-9_.:-]{1,90}",model):
        raise HTTPException(400,"Invalid local vision model name")
    endpoint=os.getenv("FCC_PID_VISION_URL","http://127.0.0.1:11434").rstrip("/")
    parsed=urlparse(endpoint)
    if parsed.scheme!="http" or parsed.hostname not in ("127.0.0.1","localhost","::1") or parsed.username or parsed.password:
        raise HTTPException(400,"Vision endpoint must be local Ollama")
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(240.0,connect=5.0),trust_env=False) as client:
            response=await client.post(endpoint+"/api/chat",json={"model":model,"stream":False,"format":"json","options":{"temperature":0},"messages":[{"role":"user","content":PROMPT,"images":[base64.b64encode(content).decode("ascii")]}]})
            response.raise_for_status()
        answer=response.json().get("message",{}).get("content","")
        if not isinstance(answer,str) or len(answer)>MAX_OUTPUT*5: raise ValueError("Invalid model output")
        result=validate_output(json.loads(answer))
    except (httpx.HTTPError,ValueError,KeyError,json.JSONDecodeError) as exc:
        raise HTTPException(502,detail=f"Local vision inference failed: {str(exc)[:400]}") from exc
    return {"engine":"local-ollama-vlm","model":model,"status":"unverified_proposals","read_only":True,**result}
