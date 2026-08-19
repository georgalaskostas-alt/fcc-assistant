#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use tauri_plugin_shell::ShellExt;

fn main() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .setup(|app| {
            let command = app.shell().sidecar("fcc-backend")?;
            let (_rx, _child) = command.spawn()?;
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running FCC Assistant");
}
