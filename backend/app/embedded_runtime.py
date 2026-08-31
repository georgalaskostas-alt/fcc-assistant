from __future__ import annotations
import json,os,platform,socket,subprocess,time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse,urlopen
from .settings import get_settings
class EmbeddedRuntimeError(RuntimeError):pass
@dataclass
class RuntimeState:
    running:bool;pid:int|None;binary_path:str;model_path:str;endpoint:str;runtime:str="llama.cpp";local_only:bool=True;ready:bool=False;detail:str|None=None
class EmbeddedAIRuntime:
    _process:subprocess.Popen[Any]|None=None
    def __init__(self)->None:
        self.settings=get_settings();self.root=Path(__file__).resolve().parents[2];self.binary_path=self._resolve_binary_path(self.settings.local_ai_binary_path);self.model_path=self._resolve_path(self.settings.local_ai_model_path);self.cache_dir=Path.home()/".fcc-assistant"/"cache"/"llama.cpp";self.log_dir=Path.home()/".fcc-assistant"/"logs";self.endpoint=self.settings.local_ai_url.rstrip("/");parsed=urlparse(self.endpoint)
        if parsed.hostname not in {"localhost","127.0.0.1","::1"}:raise EmbeddedRuntimeError("Embedded AI endpoint must be localhost")
        self.host="127.0.0.1";self.port=parsed.port or 18081
    def _resolve_path(self,configured):
        path=Path(configured).expanduser();return path if path.is_absolute() else self.root/path
    def _resolve_binary_path(self,configured):
        path=self._resolve_path(configured)
        return path.with_suffix(".exe") if platform.system()=="Windows" and path.suffix.lower()!=".exe" else path
    def _port_ready(self,timeout=.2):
        try:
            with socket.create_connection((self.host,self.port),timeout=timeout):return True
        except OSError:return False
    def _identity_ready(self,timeout=.5):
        if not self._port_ready(timeout):return False
        try:
            with urlopen(f"{self.endpoint}/v1/models",timeout=timeout) as response:payload=json.loads(response.read().decode("utf-8"))
            data=payload.get("data") if isinstance(payload,dict) else None
            ids=[str(x.get("id","")) for x in data if isinstance(x,dict)] if isinstance(data,list) else []
            expected=self.settings.local_ai_model_name.casefold().replace(".gguf","").strip()
            return bool(ids) and any(expected in x.casefold().replace(".gguf","") or "qwen3-4b" in x.casefold() for x in ids)
        except Exception:return False
    def readiness(self)->dict[str,Any]:
        port=self._port_ready();identity=self._identity_ready() if port else False
        return {"runtime":"llama.cpp","local_only":True,"binary_present":self.binary_path.exists(),"model_present":self.model_path.exists(),"endpoint_ready":identity,"port_open":port,"identity_verified":identity,"binary_path":str(self.binary_path),"model_path":str(self.model_path),"endpoint":self.endpoint,"platform":platform.system(),"architecture":platform.machine()}
    def state(self)->RuntimeState:
        process=type(self)._process;owned=process is not None and process.poll() is None;port=self._port_ready();ready=self._identity_ready() if port else False
        detail=None
        if port and not ready:detail="port-conflict-or-unverified-runtime"
        elif ready and not owned:detail="external-or-existing-verified-llama-runtime"
        return RuntimeState(owned or ready,process.pid if owned and process is not None else None,str(self.binary_path),str(self.model_path),self.endpoint,ready=ready,detail=detail)
    def start(self,wait_seconds=20.0)->RuntimeState:
        current=self.state()
        if current.ready:return current
        if self._port_ready() and not current.ready:raise EmbeddedRuntimeError(f"Port {self.port} is occupied by a service that is not the configured llama.cpp model")
        if not self.binary_path.exists():raise EmbeddedRuntimeError(f"Local llama.cpp binary not found: {self.binary_path}")
        if not self.model_path.exists():raise EmbeddedRuntimeError(f"Local GGUF model not found: {self.model_path}")
        self.cache_dir.mkdir(parents=True,exist_ok=True);self.log_dir.mkdir(parents=True,exist_ok=True);command=[str(self.binary_path),"-m",str(self.model_path),"--host",self.host,"--port",str(self.port),"-c",str(self.settings.local_ai_context_size)]
        if self.settings.local_ai_threads>0:command.extend(["-t",str(self.settings.local_ai_threads)])
        flags=getattr(subprocess,"CREATE_NO_WINDOW",0) if platform.system()=="Windows" else 0;log_path=self.log_dir/"llama-server.log";log_handle=log_path.open("ab")
        type(self)._process=subprocess.Popen(command,cwd=str(self.binary_path.parent),stdin=subprocess.DEVNULL,stdout=log_handle,stderr=subprocess.STDOUT,env={**os.environ,"LLAMA_CACHE":str(self.cache_dir)},creationflags=flags)
        deadline=time.monotonic()+max(.5,wait_seconds)
        while time.monotonic()<deadline:
            process=type(self)._process
            if process is not None and process.poll() is not None:raise EmbeddedRuntimeError(f"llama.cpp exited during startup; see {log_path}")
            if self._identity_ready(timeout=.3):return self.state()
            time.sleep(.2)
        raise EmbeddedRuntimeError(f"llama.cpp did not become identity-verified within {wait_seconds:.0f}s; see {log_path}")
    def stop(self)->RuntimeState:
        process=type(self)._process
        if process is not None and process.poll() is None:
            process.terminate()
            try:process.wait(timeout=5)
            except subprocess.TimeoutExpired:process.kill()
        type(self)._process=None;return self.state()
