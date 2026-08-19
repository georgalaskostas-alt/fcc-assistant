# FCC Assistant Desktop

Cross-platform desktop client for Windows and macOS.

## Architecture

The desktop UI is Tauri + React. It talks only to the local FCC Assistant backend at `127.0.0.1:8000`.

The final desktop build uses a bundled `llama.cpp` runtime (`llama-server`) and a local GGUF model. The backend owns that child process and exposes it only on loopback (`127.0.0.1:8081`). Ollama is not required and external AI endpoints are blocked.

## Development flow

Run the backend first from the repository root:

### macOS

```bash
bash scripts/dev-backend.sh
```

### Windows PowerShell

```powershell
.\scripts\dev-backend.ps1
```

Then start the desktop app in another terminal:

### macOS

```bash
bash scripts/dev-desktop.sh
```

### Windows PowerShell

```powershell
.\scripts\dev-desktop.ps1
```

The first development screen uses the built-in FCC simulator, so PI Web API is not required yet.

## Embedded AI packaging layout

```text
runtime/bin/llama-server       # .exe on Windows
models/default.gguf            # selected local model
```

These large/native assets are staged for builds and are not committed to the repository.

## Security boundary

- Plant write access is disabled.
- No cloud AI endpoint is supported.
- Embedded AI is loopback-only.
- Real PI URLs, credentials, and tag mappings must stay in local configuration files and must not be committed.
- The application remains functional for deterministic analytics and reports even when the local LLM is unavailable.
