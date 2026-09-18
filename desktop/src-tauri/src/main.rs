#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use serde::Serialize;
use std::{net::{SocketAddr,TcpStream},process::Command,str::FromStr,sync::{Arc,Mutex},time::Duration};
use tauri::Manager;
use tauri_plugin_shell::{process::{CommandChild,CommandEvent},ShellExt};

#[derive(Default)] struct BackendDiagnostics{last_error:Option<String>,recent_output:Vec<String>,terminated:bool}
struct BackendProcess{child:Mutex<Option<CommandChild>>,diagnostics:Arc<Mutex<BackendDiagnostics>>}
impl Drop for BackendProcess{
    fn drop(&mut self){
        if let Ok(mut guard)=self.child.lock(){
            if let Some(child)=guard.take(){let _=child.kill();}
        }
    }
}
#[derive(Serialize)] struct BackendRuntimeStatus{listening:bool,terminated:bool,last_error:Option<String>,recent_output:Vec<String>,port:u16}
fn append_output(d:&Arc<Mutex<BackendDiagnostics>>,line:String){if let Ok(mut s)=d.lock(){s.recent_output.push(line);if s.recent_output.len()>20{let n=s.recent_output.len()-20;s.recent_output.drain(0..n);}}}
fn backend_is_listening()->bool{let Ok(a)=SocketAddr::from_str("127.0.0.1:18765") else{return false};TcpStream::connect_timeout(&a,Duration::from_millis(250)).is_ok()}
fn expected_backend_is_healthy()->bool{
    // Do not treat an arbitrary process on 18765 as FCC Assistant. This exact
    // HTTP probe verifies the service identity before a dev relaunch reuses it.
    let Ok(mut stream)=TcpStream::connect_timeout(&SocketAddr::from_str("127.0.0.1:18765").unwrap(),Duration::from_millis(300)) else{return false};
    let _=stream.set_read_timeout(Some(Duration::from_millis(500)));
    let _=stream.set_write_timeout(Some(Duration::from_millis(500)));
    use std::io::{Read,Write};
    if stream.write_all(b"GET /health HTTP/1.1\r\nHost: 127.0.0.1:18765\r\nConnection: close\r\n\r\n").is_err(){return false}
    let mut response=String::new();
    if stream.read_to_string(&mut response).is_err(){return false}
    let Some((headers,body))=response.split_once("\r\n\r\n") else{return false};
    headers.starts_with("HTTP/1.1 200") && body.contains("\"status\":\"ok\"")
}
#[tauri::command] fn backend_runtime_status(state:tauri::State<'_,BackendProcess>)->BackendRuntimeStatus{let d=state.diagnostics.lock().ok();BackendRuntimeStatus{listening:backend_is_listening(),terminated:d.as_ref().map(|v|v.terminated).unwrap_or(false),last_error:d.as_ref().and_then(|v|v.last_error.clone()),recent_output:d.as_ref().map(|v|v.recent_output.clone()).unwrap_or_default(),port:18765}}
#[cfg(target_os="macos")]
fn preferred_greek_voice()->Option<String>{let o=Command::new("/usr/bin/say").args(["-v","?"]).output().ok()?;if !o.status.success(){return None}let listing=String::from_utf8_lossy(&o.stdout);let mut voices:Vec<String>=listing.lines().filter_map(|line|{let p:Vec<&str>=line.split_whitespace().collect();let i=p.iter().position(|x|x.eq_ignore_ascii_case("el_GR")||x.starts_with("el_"))?;if i==0{return None}Some(p[..i].join(" "))}).filter(|n|!n.trim().is_empty()).collect();voices.sort_by_key(|n|{let l=n.to_lowercase();if l.contains("melina"){0}else if l.contains("nikos"){1}else{2}});voices.into_iter().next()}
#[tauri::command]
fn speak_text(text:String)->Result<(),String>{let t=text.trim();if t.is_empty(){return Ok(())}if t.chars().count()>3000{return Err("Speech text is too long".into())}
#[cfg(target_os="macos")] let status={let mut c=Command::new("/usr/bin/say");if let Some(v)=preferred_greek_voice(){c.args(["-v",&v]);}c.args(["-r","195"]).arg(t).status().map_err(|e|format!("Local speech failed: {e}"))?};
#[cfg(target_os="windows")] let status=Command::new("powershell").args(["-NoProfile","-Command",&format!("Add-Type -AssemblyName System.Speech; $s=New-Object System.Speech.Synthesis.SpeechSynthesizer; $s.Rate=1; $s.Speak('{}')",t.replace('’',"'").replace('\'',"''"))]).status().map_err(|e|format!("Local speech failed: {e}"))?;
#[cfg(target_os="linux")] let status=Command::new("spd-say").args(["-r","8"]).arg(t).status().map_err(|e|format!("Local speech failed: {e}"))?;
if status.success(){Ok(())}else{Err(format!("Local speech exited with status {status}"))}}
fn main(){tauri::Builder::default().plugin(tauri_plugin_shell::init()).invoke_handler(tauri::generate_handler![backend_runtime_status,speak_text]).setup(|app|{
    let diagnostics=Arc::new(Mutex::new(BackendDiagnostics::default()));
    // A previous desktop instance can briefly leave the backend sidecar on 18765.
    // Never return Err from setup for that condition: on macOS tao invokes setup
    // from NSApplicationDelegate::didFinishLaunching, where unwinding across the
    // Objective-C callback aborts the whole process. Keep the UI alive and expose
    // the condition through backend_runtime_status instead.
    if backend_is_listening(){
        if expected_backend_is_healthy(){
            if let Ok(mut s)=diagnostics.lock(){
                s.last_error=None;
                s.recent_output.push("startup: verified FCC backend already listening on 18765; reusing existing local backend".into());
            }
        }else if let Ok(mut s)=diagnostics.lock(){
            s.last_error=Some("Port 18765 is occupied by a different local service. FCC backend was not spawned.".into());
            s.recent_output.push("startup: foreign service detected on 18765; FCC backend identity check failed".into());
        }
        app.manage(BackendProcess{child:Mutex::new(None),diagnostics});
        return Ok(());
    }
    let command=app.shell().sidecar("fcc-backend")?;let(mut rx,child)=command.spawn()?;let event_diagnostics=Arc::clone(&diagnostics);
    tauri::async_runtime::spawn(async move{while let Some(event)=rx.recv().await{match event{CommandEvent::Stdout(bytes)=>{let text=String::from_utf8_lossy(&bytes).trim().to_string();if !text.is_empty(){append_output(&event_diagnostics,format!("stdout: {text}"));}},CommandEvent::Stderr(bytes)=>{let text=String::from_utf8_lossy(&bytes).trim().to_string();if !text.is_empty(){if let Ok(mut s)=event_diagnostics.lock(){s.last_error=Some(text.clone());}append_output(&event_diagnostics,format!("stderr: {text}"));}},CommandEvent::Error(message)=>{if let Ok(mut s)=event_diagnostics.lock(){s.last_error=Some(message.clone());}append_output(&event_diagnostics,format!("error: {message}"));},CommandEvent::Terminated(payload)=>{if let Ok(mut s)=event_diagnostics.lock(){s.terminated=true;if s.last_error.is_none(){s.last_error=Some(format!("Backend exited before becoming ready (code: {:?}, signal: {:?})",payload.code,payload.signal));}}break;},_=>{}}}});
    app.manage(BackendProcess{child:Mutex::new(Some(child)),diagnostics});Ok(())}).run(tauri::generate_context!()).expect("error while running FCC Assistant");}
