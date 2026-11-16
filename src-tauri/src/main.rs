#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

//! CREST 1.1 native Windows shell.
//!
//! Owns a hidden backend sidecar process, waits for its loopback runtime
//! descriptor, and hosts the web interface in a real WebView window. There is
//! no terminal and no browser launcher. All state stays under
//! `%LOCALAPPDATA%\CREST` unless `CREST_DATA_DIR` is set explicitly.

use std::env;
use std::fs;
use std::io::{Read, Write};
use std::net::TcpStream;
use std::path::PathBuf;
use std::process::{Child, Command, Stdio};
use std::sync::Mutex;
use std::thread;
use std::time::{Duration, Instant};

use serde::Deserialize;
use tauri::{Manager, WebviewUrl, WebviewWindowBuilder};

#[allow(dead_code)]
#[derive(Deserialize, Clone)]
struct RuntimeInfo {
    host: String,
    port: u16,
    url: String,
    shutdown_token: String,
    version: String,
    schema_version: u32,
    pid: u32,
}

struct BackendState {
    child: Option<Child>,
    runtime: Option<RuntimeInfo>,
    runtime_path: PathBuf,
    /// False when this process attached to a backend owned by another instance.
    owns: bool,
}

fn data_dir(app: &tauri::App) -> Result<PathBuf, Box<dyn std::error::Error>> {
    if let Ok(custom) = env::var("CREST_DATA_DIR") {
        return Ok(PathBuf::from(custom));
    }
    #[cfg(windows)]
    {
        if let Ok(local) = env::var("LOCALAPPDATA") {
            return Ok(PathBuf::from(local).join("CREST"));
        }
    }
    Ok(app.path().app_local_data_dir()?.join("CREST"))
}

fn sidecar_path(app: &tauri::App) -> Result<PathBuf, Box<dyn std::error::Error>> {
    let bundled = app.path().resource_dir()?.join("binaries").join("crest-backend.exe");
    if bundled.exists() {
        return Ok(bundled);
    }
    // Development fallback: the binary is copied next to the dev executable.
    let local = env::current_exe()?
        .parent()
        .ok_or("no executable parent")?
        .join("binaries")
        .join("crest-backend.exe");
    Ok(local)
}

fn diag(dir: &std::path::Path, message: &str) {
    use std::io::Write as _;
    if let Ok(mut file) = fs::OpenOptions::new()
        .create(true)
        .append(true)
        .open(dir.join("shell-diagnostic.log"))
    {
        let _ = writeln!(file, "{}", message);
    }
}

fn normalize_host(host: &str) -> String {
    if host == "::1" {
        "[::1]".to_string()
    } else {
        host.to_string()
    }
}

/// A stale descriptor is harmless, but a *live* one means another instance
/// already owns a backend. Reusing it prevents duplicate sidecars and lets the
/// single-instance plugin close this process without killing shared state.
fn live_runtime(runtime_path: &std::path::Path) -> Option<RuntimeInfo> {
    let text = fs::read_to_string(runtime_path).ok()?;
    let info: RuntimeInfo = serde_json::from_str(&text).ok()?;
    let addr = format!("{}:{}", normalize_host(&info.host), info.port);
    let socket: std::net::SocketAddr = addr.parse().ok()?;
    let mut stream = TcpStream::connect_timeout(&socket, Duration::from_millis(700)).ok()?;
    stream.set_read_timeout(Some(Duration::from_millis(700))).ok()?;
    stream
        .write_all(
            format!("GET /api/v1/health HTTP/1.1\r\nHost: {}\r\nConnection: close\r\n\r\n", addr)
                .as_bytes(),
        )
        .ok()?;
    let mut reply = [0u8; 256];
    let read = stream.read(&mut reply).ok()?;
    let response = String::from_utf8_lossy(&reply[..read]);
    if response.contains("200 OK") {
        Some(info)
    } else {
        None
    }
}

fn launch_backend(app: &tauri::App) -> Result<(Option<Child>, RuntimeInfo, PathBuf), Box<dyn std::error::Error>> {
    let dir = data_dir(app)?;
    fs::create_dir_all(&dir)?;
    let runtime_path = dir.join("runtime.json");

    diag(
        &dir,
        &format!(
            "launch_backend: runtime={} exists={} env={:?}",
            runtime_path.display(),
            runtime_path.exists(),
            env::var("CREST_DATA_DIR").ok()
        ),
    );
    if let Some(info) = live_runtime(&runtime_path) {
        diag(&dir, &format!("reusing live backend on port {}", info.port));
        return Ok((None, info, runtime_path));
    }
    diag(&dir, "spawning a new backend");
    // No live backend — clear any stale descriptor before starting ours.
    let _ = fs::remove_file(&runtime_path);

    let exe = sidecar_path(app)?;
    if !exe.exists() {
        return Err(format!("backend sidecar not found at {}", exe.display()).into());
    }

    let mut command = Command::new(exe);
    command
        .env("CREST_HOST", "127.0.0.1")
        .env("CREST_PORT", "0")
        .env("CREST_DATA_DIR", &dir)
        .env("CREST_RUNTIME_FILE", &runtime_path)
        .stdout(Stdio::null())
        .stderr(Stdio::null());

    #[cfg(windows)]
    {
        use std::os::windows::process::CommandExt;
        // CREATE_NO_WINDOW — never flash a console window.
        command.creation_flags(0x0800_0000);
    }

    let mut child = command.spawn()?;
    let deadline = Instant::now() + Duration::from_secs(60);
    let mut info: Option<RuntimeInfo> = None;
    while Instant::now() < deadline {
        if let Ok(text) = fs::read_to_string(&runtime_path) {
            if let Ok(parsed) = serde_json::from_str::<RuntimeInfo>(&text) {
                info = Some(parsed);
                break;
            }
        }
        if let Ok(Some(_)) = child.try_wait() {
            return Err("backend process exited before becoming ready".into());
        }
        thread::sleep(Duration::from_millis(120));
    }

    match info {
        Some(info) => Ok((Some(child), info, runtime_path)),
        None => {
            let _ = child.kill();
            Err("timed out waiting for the backend runtime descriptor".into())
        }
    }
}

fn shutdown_backend(app: &tauri::AppHandle) {
    let (owns, info) = app
        .try_state::<Mutex<BackendState>>()
        .and_then(|state| {
            state
                .lock()
                .ok()
                .map(|guard| (guard.owns, guard.runtime.clone()))
        })
        .unwrap_or((false, None));

    // A secondary instance must never shut down a backend it does not own.
    if !owns {
        return;
    }

    if let Some(info) = info {
        let addr = format!("{}:{}", normalize_host(&info.host), info.port);
        if let Ok(mut stream) = TcpStream::connect(&addr) {
            let request = format!(
                "POST /api/v1/control/shutdown HTTP/1.1\r\nHost: {}\r\nConnection: close\r\nx-crest-shutdown-token: {}\r\nContent-Length: 0\r\n\r\n",
                addr, info.shutdown_token
            );
            if stream.write_all(request.as_bytes()).is_ok() {
                let mut reply = [0u8; 128];
                let _ = stream.read(&mut reply);
            }
        }
    }

    thread::sleep(Duration::from_millis(350));
    if let Some(state) = app.try_state::<Mutex<BackendState>>() {
        if let Ok(mut guard) = state.lock() {
            if let Some(mut child) = guard.child.take() {
                let _ = child.kill();
                let _ = child.wait();
            }
            // Removing the descriptor here avoids a stale port among the next
            // launch, even if the Python child was killed before its cleanup.
            let _ = fs::remove_file(&guard.runtime_path);
        }
    }
}

fn build_error_window(app: &tauri::AppHandle, message: &str) {
    let escaped = message
        .replace('&', "&amp;")
        .replace('<', "&lt;")
        .replace('>', "&gt;")
        .replace('"', "&quot;");
    let html = format!(
        "<!doctype html><html><head><meta charset='utf-8'><title>CREST — startup error</title>\
         <style>body{{font-family:Segoe UI,Arial,sans-serif;background:#0b1414;color:#e7f1f0;margin:0;\
         display:grid;place-items:center;height:100vh}}main{{max-width:560px;padding:32px;border:1px solid #264b48;\
         border-radius:16px;background:#10201f}}h1{{color:#5eead4;font-size:20px}}code{{color:#fbbf24}}</style></head>\
         <body><main><h1>CREST could not start</h1><p><code>{}</code></p>\
         <p>Your data was not changed. Close this window and try again. If the problem persists, see the troubleshooting guide.</p>\
         </main></body></html>",
        escaped
    );
    let url = format!("data:text/html,{}", urlencoding(&html));
    if let Ok(parsed) = url.parse::<tauri::Url>() {
        let _ = WebviewWindowBuilder::new(app, "main", WebviewUrl::External(parsed))
            .title("CREST — startup error")
            .build();
    }
}

fn urlencoding(value: &str) -> String {
    let mut out = String::new();
    for byte in value.bytes() {
        match byte {
            b'A'..=b'Z' | b'a'..=b'z' | b'0'..=b'9' | b'-' | b'_' | b'.' | b'~' | b'/' | b':' => {
                out.push(byte as char)
            }
            _ => out.push_str(&format!("%{:02X}", byte)),
        }
    }
    out
}

fn setup(app: &mut tauri::App) -> Result<(), Box<dyn std::error::Error>> {
    match launch_backend(app) {
        Ok((child, info, runtime_path)) => {
            let owns = child.is_some();
            app.manage(Mutex::new(BackendState {
                child,
                runtime: Some(info.clone()),
                runtime_path,
                owns,
            }));

            let url = format!("{}/app", info.url).parse::<tauri::Url>()?;
            let window = WebviewWindowBuilder::new(app, "main", WebviewUrl::External(url))
                .title("CREST")
                .inner_size(1320.0, 860.0)
                .min_inner_size(980.0, 640.0)
                .resizable(true)
                .center()
                .build()?;

            let handle = app.handle().clone();
            window.on_window_event(move |event| {
                if let tauri::WindowEvent::CloseRequested { api, .. } = event {
                    api.prevent_close();
                    let h = handle.clone();
                    thread::spawn(move || {
                        shutdown_backend(&h);
                        h.exit(0);
                    });
                }
            });
        }
        Err(error) => {
            let message = error.to_string();
            build_error_window(app.handle(), &message);
        }
    }

    Ok(())
}

fn main() {
    let app = tauri::Builder::default()
        .plugin(tauri_plugin_single_instance::init(|app, _args, _cwd| {
            if let Some(window) = app.get_webview_window("main") {
                let _ = window.show();
                let _ = window.set_focus();
            }
        }))
        .setup(setup)
        .build(tauri::generate_context!())
        .expect("failed to build the CREST application");

    app.run(|handle, event| {
        if let tauri::RunEvent::ExitRequested { .. } = event {
            shutdown_backend(handle);
        }
    });
}
