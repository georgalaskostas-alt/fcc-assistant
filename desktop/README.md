# FCC Assistant Desktop

Cross-platform desktop client for Windows and macOS.

## Architecture

The desktop UI is Tauri + React. It talks only to the local FCC Assistant backend at `127.0.0.1:8000`. The AI runtime is separately restricted by the backend to localhost only.

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

## Security boundary

- Plant write access is disabled.
- No cloud AI endpoint is supported.
- Local AI URLs are restricted to loopback hosts.
- Real PI URLs, credentials, and tag mappings must stay in local configuration files and must not be committed.
