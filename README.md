# FCC Assistant

Local-first desktop assistant for FCC process monitoring, analysis, and reporting.

## Goals

- Windows and macOS desktop application
- Read-only PI System integration through PI Web API
- Local AI: no cloud AI API required
- Shift and daily reports
- Engineering calculations and trend analysis
- Chat interface grounded in actual process data
- No plant credentials, secrets, or real PI tags committed to Git

## Initial architecture

- Desktop UI: Tauri + React + TypeScript
- Process backend: Python + FastAPI
- Local storage: SQLite
- PI connector: PI Web API (read-only)
- Local model runtime: pluggable local LLM provider

## Safety boundary

The first versions are read-only. FCC Assistant will not write values, commands, or setpoints back to the PI System or plant control systems.

## Status

Project bootstrap in progress.
