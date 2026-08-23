#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use serde::Serialize;
use std::{
    net::{SocketAddr, TcpStream},
    process::Command,
    str::FromStr,
    sync::{Arc, Mutex},
    time::Duration,
};
use tauri::Manager;
use tauri_plugin_shell::{
    process::{CommandChild, CommandEvent},
    ShellExt,
};

#[derive(Default)]
struct BackendDiagnostics {
    last_error: Option<String>,
    recent_output: Vec<String>,
    terminated: bool,
}

struct BackendProcess {
    child: Mutex<Option<CommandChild>>,
    diagnostics: Arc<Mutex<BackendDiagnostics>>,
}

#[derive(Serialize)]
struct BackendRuntimeStatus {
    listening: bool,
    terminated: bool,
    last_error: Option<String>,
    recent_output: Vec<String>,
    port: u16,
}

fn append_output(diagnostics: &Arc<Mutex<BackendDiagnostics>>, line: String) {
    if let Ok(mut state) = diagnostics.lock() {
        state.recent_output.push(line);
        if state.recent_output.len() > 20 {
            let excess = state.recent_output.len() - 20;
            state.recent_output.drain(0..excess);
        }
    }
}

fn backend_is_listening() -> bool {
    let Ok(address) = SocketAddr::from_str("127.0.0.1:8765") else {
        return false;
    };
    TcpStream::connect_timeout(&address, Duration::from_millis(250)).is_ok()
}

#[tauri::command]
fn backend_runtime_status(state: tauri::State<'_, BackendProcess>) -> BackendRuntimeStatus {
    let diagnostics = state.diagnostics.lock().ok();
    BackendRuntimeStatus {
        listening: backend_is_listening(),
        terminated: diagnostics.as_ref().map(|value| value.terminated).unwrap_or(false),
        last_error: diagnostics.as_ref().and_then(|value| value.last_error.clone()),
        recent_output: diagnostics
            .as_ref()
            .map(|value| value.recent_output.clone())
            .unwrap_or_default(),
        port: 8765,
    }
}

#[tauri::command]
fn speak_text(text: String) -> Result<(), String> {
    let trimmed = text.trim();
    if trimmed.is_empty() {
        return Ok(());
    }
    if trimmed.chars().count() > 3000 {
        return Err("Speech text is too long".into());
    }

    #[cfg(target_os = "macos")]
    let status = Command::new("/usr/bin/say")
        .arg(trimmed)
        .status()
        .map_err(|error| format!("Local speech failed: {error}"))?;

    #[cfg(target_os = "windows")]
    let status = Command::new("powershell")
        .args([
            "-NoProfile",
            "-Command",
            &format!(
                "Add-Type -AssemblyName System.Speech; $s=New-Object System.Speech.Synthesis.SpeechSynthesizer; $s.Speak('{}')",
                trimmed.replace('’', "'").replace('\'', "''")
            ),
        ])
        .status()
        .map_err(|error| format!("Local speech failed: {error}"))?;

    #[cfg(target_os = "linux")]
    let status = Command::new("spd-say")
        .arg(trimmed)
        .status()
        .map_err(|error| format!("Local speech failed: {error}"))?;

    if status.success() {
        Ok(())
    } else {
        Err(format!("Local speech exited with status {status}"))
    }
}

fn main() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .invoke_handler(tauri::generate_handler![backend_runtime_status, speak_text])
        .setup(|app| {
            let command = app.shell().sidecar("fcc-backend")?;
            let (mut rx, child) = command.spawn()?;
            let diagnostics = Arc::new(Mutex::new(BackendDiagnostics::default()));
            let event_diagnostics = Arc::clone(&diagnostics);

            tauri::async_runtime::spawn(async move {
                while let Some(event) = rx.recv().await {
                    match event {
                        CommandEvent::Stdout(bytes) => {
                            let text = String::from_utf8_lossy(&bytes).trim().to_string();
                            if !text.is_empty() {
                                append_output(&event_diagnostics, format!("stdout: {text}"));
                            }
                        }
                        CommandEvent::Stderr(bytes) => {
                            let text = String::from_utf8_lossy(&bytes).trim().to_string();
                            if !text.is_empty() {
                                if let Ok(mut state) = event_diagnostics.lock() {
                                    state.last_error = Some(text.clone());
                                }
                                append_output(&event_diagnostics, format!("stderr: {text}"));
                            }
                        }
                        CommandEvent::Error(message) => {
                            if let Ok(mut state) = event_diagnostics.lock() {
                                state.last_error = Some(message.clone());
                            }
                            append_output(&event_diagnostics, format!("error: {message}"));
                        }
                        CommandEvent::Terminated(payload) => {
                            if let Ok(mut state) = event_diagnostics.lock() {
                                state.terminated = true;
                                if state.last_error.is_none() {
                                    state.last_error = Some(format!(
                                        "Backend exited before becoming ready (code: {:?}, signal: {:?})",
                                        payload.code, payload.signal
                                    ));
                                }
                            }
                            break;
                        }
                        _ => {}
                    }
                }
            });

            app.manage(BackendProcess {
                child: Mutex::new(Some(child)),
                diagnostics,
            });
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running FCC Assistant");
}
