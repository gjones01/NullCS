use serde::{Deserialize, Serialize};
use std::{
  env,
  fs::{self, OpenOptions},
  io::{Read, Write},
  net::{TcpListener, TcpStream, ToSocketAddrs},
  path::{Path, PathBuf},
  process::{Child, Command, Stdio},
  sync::{Mutex, OnceLock},
  thread,
  time::Duration,
};
use tauri::Manager;
use uuid::Uuid;
use sha2::{Digest, Sha256};
use tauri_plugin_updater::UpdaterExt;
use rfd::FileDialog;

#[cfg(target_os = "windows")]
use std::os::windows::process::CommandExt;

const LOCAL_API_HOST: &str = "127.0.0.1";
const LOCAL_API_PORT_BASE: u16 = 8011;
#[cfg(target_os = "windows")]
const CREATE_NO_WINDOW: u32 = 0x0800_0000;

static INSTANCE_LOCK: OnceLock<fs::File> = OnceLock::new();
static LOCAL_API_START: Mutex<()> = Mutex::new(());
static LOCAL_API_CHILD: OnceLock<Mutex<Option<Child>>> = OnceLock::new();
static DESKTOP_API_KEY: OnceLock<String> = OnceLock::new();
static LOCAL_API_PORT: OnceLock<u16> = OnceLock::new();
static PACKAGED_BACKEND_ROOT: OnceLock<Option<PathBuf>> = OnceLock::new();
static PACKAGED_BACKEND_VERIFIED: OnceLock<bool> = OnceLock::new();
static APP_DATA_DIR: OnceLock<Option<PathBuf>> = OnceLock::new();

#[derive(Deserialize)]
struct BackendManifest {
  files: Vec<BackendManifestFile>,
}

#[derive(Deserialize)]
struct BackendManifestFile {
  path: String,
  sha256: String,
}

#[derive(Clone, Serialize)]
struct DesktopServiceStatus {
  is_desktop: bool,
  api_base_url: String,
  api_key: String,
  running: bool,
  healthy: bool,
  can_start: bool,
  launched_by_app: bool,
  error: Option<String>,
}

fn local_api_child() -> &'static Mutex<Option<Child>> {
  LOCAL_API_CHILD.get_or_init(|| Mutex::new(None))
}

fn choose_local_api_port() -> u16 {
  for port in LOCAL_API_PORT_BASE..(LOCAL_API_PORT_BASE + 32) {
    if TcpListener::bind((LOCAL_API_HOST, port)).is_ok() {
      return port;
    }
  }
  LOCAL_API_PORT_BASE
}

fn local_api_port() -> u16 {
  *LOCAL_API_PORT.get_or_init(choose_local_api_port)
}

fn api_base_url() -> String {
  format!("http://{LOCAL_API_HOST}:{}{}", local_api_port(), "/api")
}

fn load_or_create_desktop_api_key() -> String {
  Uuid::new_v4().to_string()
}

fn desktop_api_key() -> &'static str {
  DESKTOP_API_KEY.get_or_init(load_or_create_desktop_api_key).as_str()
}

fn packaged_backend_root() -> Option<PathBuf> {
  let root = PACKAGED_BACKEND_ROOT.get().and_then(|value| value.clone())?;
  let verified = *PACKAGED_BACKEND_VERIFIED.get_or_init(|| verify_packaged_backend(&root));
  if verified {
    Some(root)
  } else {
    None
  }
}

fn app_data_dir() -> Option<PathBuf> {
  APP_DATA_DIR.get().and_then(|value| value.clone())
}

fn candidate_roots() -> Vec<PathBuf> {
  let mut out = Vec::new();
  let mut push = |path: PathBuf| {
    if !out.iter().any(|existing| existing == &path) {
      out.push(path);
    }
  };

  if let Some(root) = packaged_backend_root() {
    push(root);
  }

  #[cfg(debug_assertions)]
  {
    for env_name in ["NULLCS_PROJECT_ROOT", "CLARITY_PROJECT_ROOT"] {
      if let Ok(value) = env::var(env_name) {
        let trimmed = value.trim();
        if !trimmed.is_empty() {
          push(PathBuf::from(trimmed));
        }
      }
    }

    if let Ok(cwd) = env::current_dir() {
      push(cwd.clone());
      for ancestor in cwd.ancestors() {
        push(ancestor.to_path_buf());
      }
    }

    if let Ok(exe) = env::current_exe() {
      if let Some(parent) = exe.parent() {
        push(parent.to_path_buf());
        for ancestor in parent.ancestors() {
          push(ancestor.to_path_buf());
        }
      }
    }
  }

  #[cfg(debug_assertions)]
  for hardcoded in [r"C:\NullCS", r"C:\ClarityCS"] {
    push(PathBuf::from(hardcoded));
  }

  out
}

fn is_repo_root(path: &Path) -> bool {
  path.join("main").is_dir()
    && path.join("main").join("ui").join("api").join("main.py").is_file()
    && path.join("main").join("scripts").join("run_infer_pipeline.py").is_file()
    && path.join("main").join("src").join("utils").join("model_registry.py").is_file()
    && path.join("main").join("data").join("processed").join("models").is_dir()
}

fn find_repo_root() -> Option<PathBuf> {
  candidate_roots().into_iter().find(|candidate| is_repo_root(candidate))
}

fn preferred_python(repo_root: &Path) -> PathBuf {
  if let Ok(value) = env::var("CLARITY_PYTHON_EXE") {
    let trimmed = value.trim();
    if !trimmed.is_empty() {
      return PathBuf::from(trimmed);
    }
  }
  let venv = repo_root.join("NewAnubisTri").join(".venv").join("Scripts").join("python.exe");
  if venv.is_file() {
    return venv;
  }
  for fallback in [
    r"C:\NullCS\NewAnubisTri\.venv\Scripts\python.exe",
    r"C:\ClarityCS\NewAnubisTri\.venv\Scripts\python.exe",
  ] {
    let path = PathBuf::from(fallback);
    if path.is_file() {
      return path;
    }
  }
  PathBuf::from("python")
}

fn preferred_uvicorn(repo_root: &Path) -> Option<PathBuf> {
  let exe = repo_root.join("NewAnubisTri").join(".venv").join("Scripts").join("uvicorn.exe");
  if exe.is_file() {
    return Some(exe);
  }
  for fallback in [
    r"C:\NullCS\NewAnubisTri\.venv\Scripts\uvicorn.exe",
    r"C:\ClarityCS\NewAnubisTri\.venv\Scripts\uvicorn.exe",
  ] {
    let path = PathBuf::from(fallback);
    if path.is_file() {
      return Some(path);
    }
  }
  None
}

fn packaged_sidecar_exe(repo_root: &Path) -> Option<PathBuf> {
  let exe = repo_root.join("nullcs-backend.exe");
  if exe.is_file() {
    Some(exe)
  } else {
    None
  }
}

fn certutil_sha256(path: &Path) -> Option<String> {
  let mut file = fs::File::open(path).ok()?;
  let mut hash = Sha256::new();
  let mut buffer = [0u8; 65536];
  loop {
    let count = file.read(&mut buffer).ok()?;
    if count == 0 { break; }
    hash.update(&buffer[..count]);
  }
  Some(format!("{:x}", hash.finalize()))
}

fn verify_packaged_backend(root: &Path) -> bool {
  let manifest_path = root.join("backend_manifest.json");
  let expected_manifest_hash = option_env!("NULLCS_BACKEND_MANIFEST_SHA256").unwrap_or("");
  if expected_manifest_hash.len() != 64 {
    return false;
  }
  let Some(actual_manifest_hash) = certutil_sha256(&manifest_path) else {
    return false;
  };
  if actual_manifest_hash != expected_manifest_hash {
    return false;
  }
  let manifest_text = match fs::read_to_string(&manifest_path) {
    Ok(text) => text,
    Err(_) => return false,
  };
  let manifest: BackendManifest = match serde_json::from_str(manifest_text.trim_start_matches('\u{feff}')) {
    Ok(value) => value,
    Err(_) => return false,
  };
  let root_resolved = match root.canonicalize() {
    Ok(path) => path,
    Err(_) => return false,
  };
  if manifest.files.is_empty() || !manifest.files.iter().any(|f| f.path == "nullcs-backend.exe") { return false; }
  for file in manifest.files {
    if file.path.contains("..") || file.path.starts_with('/') || file.path.starts_with('\\') {
      return false;
    }
    let target = root.join(file.path.replace('/', "\\"));
    let target_resolved = match target.canonicalize() {
      Ok(path) => path,
      Err(_) => return false,
    };
    if target_resolved != root_resolved && !target_resolved.starts_with(&root_resolved) {
      return false;
    }
    let Some(actual) = certutil_sha256(&target_resolved) else {
      return false;
    };
    if actual != file.sha256.to_ascii_lowercase() {
      return false;
    }
  }
  true
}

fn copy_dir_missing(src: &Path, dst: &Path) -> std::io::Result<()> {
  if !src.exists() {
    return Ok(());
  }
  fs::create_dir_all(dst)?;
  for entry in fs::read_dir(src)? {
    let entry = entry?;
    let src_path = entry.path();
    let dst_path = dst.join(entry.file_name());
    let file_type = entry.file_type()?;
    if file_type.is_dir() {
      copy_dir_missing(&src_path, &dst_path)?;
    } else if file_type.is_file() && (!dst_path.exists() || certutil_sha256(&src_path) != certutil_sha256(&dst_path)) {
      fs::copy(&src_path, &dst_path)?;
    }
  }
  Ok(())
}

fn prepare_desktop_data(repo_root: &Path) -> Result<Option<PathBuf>, String> {
  let Some(data_dir) = app_data_dir() else {
    return Ok(None);
  };
  let processed_dir = data_dir.join("processed");
  let models_src = repo_root.join("main").join("data").join("processed").join("models");
  let models_dst = processed_dir.join("models");
  copy_dir_missing(&models_src, &models_dst).map_err(|err| format!("Failed to prepare desktop model cache: {err}"))?;
  fs::create_dir_all(data_dir.join("raw_uploads")).map_err(|err| format!("Failed to prepare desktop uploads dir: {err}"))?;
  fs::create_dir_all(data_dir.join("state")).map_err(|err| format!("Failed to prepare desktop state dir: {err}"))?;
  fs::create_dir_all(processed_dir.join("reports")).map_err(|err| format!("Failed to prepare desktop reports dir: {err}"))?;
  Ok(Some(data_dir))
}

fn local_api_healthy() -> bool {
  let socket = format!("{LOCAL_API_HOST}:{}", local_api_port());
  let addr = match socket.to_socket_addrs().ok().and_then(|mut iter| iter.next()) {
    Some(addr) => addr,
    None => return false,
  };
  let mut stream = match TcpStream::connect_timeout(&addr, Duration::from_millis(700)) {
    Ok(stream) => stream,
    Err(_) => return false,
  };
  let _ = stream.set_read_timeout(Some(Duration::from_millis(1200)));
  let _ = stream.set_write_timeout(Some(Duration::from_millis(1200)));
  let request = format!(
    "GET /api/health HTTP/1.1\r\nHost: {LOCAL_API_HOST}:{}\r\nX-NULLCS-KEY: {}\r\nConnection: close\r\n\r\n",
    local_api_port(),
    desktop_api_key(),
  );
  if stream.write_all(request.as_bytes()).is_err() {
    return false;
  }
  let mut response = String::new();
  if stream.read_to_string(&mut response).is_err() {
    return false;
  }
  response.starts_with("HTTP/1.1 200") || response.starts_with("HTTP/1.0 200")
}

fn local_api_port_open() -> bool {
  let socket = format!("{LOCAL_API_HOST}:{}", local_api_port());
  let addr = match socket.to_socket_addrs().ok().and_then(|mut iter| iter.next()) {
    Some(addr) => addr,
    None => return false,
  };
  TcpStream::connect_timeout(&addr, Duration::from_millis(500)).is_ok()
}

fn child_running() -> bool {
  let mutex = local_api_child();
  let mut guard = match mutex.lock() {
    Ok(guard) => guard,
    Err(_) => return false,
  };
  if let Some(child) = guard.as_mut() {
    match child.try_wait() {
      Ok(None) => true,
      Ok(Some(_)) | Err(_) => {
        *guard = None;
        false
      }
    }
  } else {
    false
  }
}

fn desktop_status(error: Option<String>) -> DesktopServiceStatus {
  let repo_root = find_repo_root();
  let running = child_running();
  let healthy = local_api_healthy();
  DesktopServiceStatus {
    is_desktop: true,
    api_base_url: api_base_url(),
    api_key: desktop_api_key().to_string(),
    running: running || healthy,
    healthy,
    can_start: repo_root.is_some(),
    launched_by_app: running,
    error,
  }
}

fn spawn_local_api() -> Result<DesktopServiceStatus, String> {
  let _startup = LOCAL_API_START.lock().map_err(|_| "Engine startup state unavailable".to_string())?;
  if local_api_healthy() {
    return Ok(desktop_status(None));
  }
  if child_running() {
    return Ok(desktop_status(None));
  }

  let repo_root = find_repo_root().ok_or_else(|| "NullCS repo root was not found on this machine.".to_string())?;
  let desktop_data = prepare_desktop_data(&repo_root)?;
  let sidecar = packaged_sidecar_exe(&repo_root);
  let python = preferred_python(&repo_root);
  let uvicorn = preferred_uvicorn(&repo_root);
  let state_dir = desktop_data
    .as_ref()
    .map(|path| path.join("state"))
    .unwrap_or_else(|| repo_root.join("main").join("ui").join("api").join("state"));
  fs::create_dir_all(&state_dir).map_err(|err| format!("Failed to create state dir: {err}"))?;
  let stdout_log = OpenOptions::new()
    .create(true)
    .append(true)
    .open(state_dir.join("desktop_api.log"))
    .map_err(|err| format!("Failed to open desktop_api.log: {err}"))?;
  let stderr_log = OpenOptions::new()
    .create(true)
    .append(true)
    .open(state_dir.join("desktop_api.err.log"))
    .map_err(|err| format!("Failed to open desktop_api.err.log: {err}"))?;

  let mut cmd = if let Some(ref sidecar_exe) = sidecar {
    let mut command = Command::new(sidecar_exe);
    command
      .arg("api")
      .arg("--host")
      .arg(LOCAL_API_HOST)
      .arg("--port")
      .arg(local_api_port().to_string());
    command
  } else if let Some(ref uvicorn_exe) = uvicorn {
    let mut command = Command::new(&uvicorn_exe);
    command
      .arg("main.ui.api.main:app")
      .arg("--host")
      .arg(LOCAL_API_HOST)
      .arg("--port")
      .arg(local_api_port().to_string());
    command
  } else {
    let mut command = Command::new(&python);
    command
      .arg("-m")
      .arg("uvicorn")
      .arg("main.ui.api.main:app")
      .arg("--host")
      .arg(LOCAL_API_HOST)
      .arg("--port")
      .arg(local_api_port().to_string());
    command
  };

  cmd
    .current_dir(&repo_root)
    .env("NULLCS_PROJECT_ROOT", &repo_root)
    .env("CLARITY_PROJECT_ROOT", &repo_root)
    .env_remove("NULLCS_API_KEY")
    .env_remove("NULLCS_MODEL_ARTIFACT")
    .env_remove("CLARITY_MODEL_ARTIFACT")
    .env("NULLCS_WEB_ANALYSIS", "0")
    .env("NULLCS_ENV", "desktop")
    .env("NULLCS_DESKTOP_MODE", "1")
    .env("NULLCS_DESKTOP_PARENT_WATCHDOG", "1")
    .env("NULLCS_DESKTOP_KEY", desktop_api_key())
    .env("NULLCS_ENABLE_DIAGNOSTICS", "0")
    .env("NULLCS_DEMO_MODE", "0")
    .env("NULLCS_MAX_UPLOAD_BYTES", "1073741824");
  if let Some(data_dir) = desktop_data.as_ref() {
    cmd
      .env("NULLCS_DESKTOP_DATA_DIR", data_dir)
      .env("NULLCS_STATE_DIR", data_dir.join("state"))
      .env("NULLCS_UPLOAD_DIR", data_dir.join("raw_uploads"))
      .env("CLARITY_RAW_UPLOADS_DIR", data_dir.join("raw_uploads"))
      .env("CLARITY_PROCESSED_DIR", data_dir.join("processed"));
  }
  if let Some(sidecar_exe) = sidecar.as_ref() {
    cmd.env("NULLCS_PIPELINE_EXE", sidecar_exe);
  }
  cmd
    .stdin(Stdio::piped())
    .stdout(Stdio::from(stdout_log))
    .stderr(Stdio::from(stderr_log));
  #[cfg(target_os = "windows")]
  cmd.creation_flags(CREATE_NO_WINDOW);

  let launcher_label = sidecar
    .as_ref()
    .map(|path| path.display().to_string())
    .or_else(|| uvicorn.as_ref().map(|path| path.display().to_string()))
    .unwrap_or_else(|| python.display().to_string());
  let child = cmd.spawn().map_err(|err| format!("Failed to launch local API with {launcher_label}: {err}"))?;
  {
    let mutex = local_api_child();
    let mut guard = mutex.lock().map_err(|_| "Failed to acquire local API state.".to_string())?;
    *guard = Some(child);
  }

  for _ in 0..120 {
    if local_api_healthy() {
      return Ok(desktop_status(None));
    }
    thread::sleep(Duration::from_millis(350));
    if !child_running() {
      break;
    }
  }

  if local_api_port_open() && !local_api_healthy() {
    return Err(format!(
      "Another local service is already bound to port {}, but it does not accept this desktop session. Close the stale service and start the local engine again.",
      local_api_port()
    ));
  }

  Err("The local review engine did not become healthy after launch.".to_string())
}

#[tauri::command]
fn desktop_service_status() -> DesktopServiceStatus {
  desktop_status(None)
}

#[tauri::command]
async fn desktop_service_start() -> DesktopServiceStatus {
  match tauri::async_runtime::spawn_blocking(spawn_local_api).await.unwrap_or_else(|_| Err("Engine startup failed".into())) {
    Ok(status) => status,
    Err(error) => desktop_status(Some(error)),
  }
}

#[tauri::command]
fn desktop_pick_demo_file() -> Option<String> {
  FileDialog::new()
    .add_filter("Counter-Strike Demo", &["dem"])
    .pick_file()
    .map(|path| path.display().to_string())
}

#[tauri::command]
async fn desktop_save_report(report: String) -> Result<bool, String> {
  if report.len() > 1024 * 1024 { return Err("Report is too large".into()); }
  tauri::async_runtime::spawn_blocking(move || {
    let Some(path) = FileDialog::new().add_filter("Plain text report", &["txt"]).set_file_name("NullCS-report.txt").save_file() else { return Ok(false); };
    if path.extension().and_then(|s| s.to_str()).map(|s| s.to_ascii_lowercase()) != Some("txt".into()) { return Err("Save the report as a .txt file".into()); }
    fs::write(path, report).map_err(|_| "The report could not be saved. Choose another location.".to_string())?;
    Ok(true)
  }).await.map_err(|_| "Report save failed".to_string())?
}

fn allowed_external_url(url: &str) -> bool {
  let trimmed = url.trim();
  let steam_prefix = "https://steamcommunity.com/profiles/";
  let csstats_prefix = "https://csstats.gg/player/";
  let suffix = if let Some(value) = trimmed.strip_prefix(steam_prefix) {
    value
  } else if let Some(value) = trimmed.strip_prefix(csstats_prefix) {
    value
  } else {
    return false;
  };
  suffix.len() == 17 && suffix.chars().all(|ch| ch.is_ascii_digit())
}

#[tauri::command]
fn desktop_open_external_url(url: String) -> Result<bool, String> {
  let trimmed = url.trim().to_string();
  if !allowed_external_url(&trimmed) {
    return Err("Only Steam and CSStats player profile URLs are allowed.".to_string());
  }

  #[cfg(target_os = "windows")]
  {
    Command::new("rundll32.exe")
      .arg("url.dll,FileProtocolHandler")
      .arg(trimmed)
      .spawn()
      .map(|_| true)
      .map_err(|err| format!("Failed to open the default browser: {err}"))
  }

  #[cfg(target_os = "macos")]
  {
    Command::new("open")
      .arg(trimmed)
      .spawn()
      .map(|_| true)
      .map_err(|err| format!("Failed to open the default browser: {err}"))
  }

  #[cfg(all(not(target_os = "windows"), not(target_os = "macos")))]
  {
    Command::new("xdg-open")
      .arg(trimmed)
      .spawn()
      .map(|_| true)
      .map_err(|err| format!("Failed to open the default browser: {err}"))
  }
}


#[derive(Default)]
struct PendingUpdate(Mutex<Option<tauri_plugin_updater::Update>>);

#[derive(Serialize)]
struct UpdateStatus { configured: bool, version: Option<String>, notes: Option<String> }

#[tauri::command]
async fn desktop_check_update(app: tauri::AppHandle, pending: tauri::State<'_, PendingUpdate>) -> Result<UpdateStatus, String> {
  let endpoint = option_env!("NULLCS_UPDATE_ENDPOINT").unwrap_or("");
  let public_key = option_env!("NULLCS_UPDATE_PUBLIC_KEY").unwrap_or("");
  if endpoint.is_empty() || public_key.is_empty() {
    return Ok(UpdateStatus { configured: false, version: None, notes: None });
  }
  let url: tauri::Url = endpoint.parse().map_err(|_| "Invalid update endpoint")?;
  if url.scheme() != "https" || url.host_str().is_none() || !url.username().is_empty() || url.password().is_some() {
    return Err("Update checks require a trusted HTTPS endpoint".into());
  }
  let update = app.updater_builder().pubkey(public_key).endpoints(vec![url])
    .map_err(|_| "Update configuration is invalid")?
    .timeout(Duration::from_secs(20)).build().map_err(|_| "Update configuration is invalid")?
    .check().await.map_err(|_| "Could not check for updates. You can retry when online.")?;
  let status = UpdateStatus { configured: true, version: update.as_ref().map(|u| u.version.clone()), notes: update.as_ref().and_then(|u| u.body.clone()) };
  *pending.0.lock().map_err(|_| "Update state unavailable")? = update;
  Ok(status)
}

fn stop_local_api() {
  if let Ok(mut guard) = local_api_child().lock() {
    if let Some(mut child) = guard.take() {
      #[cfg(target_os = "windows")]
      {
        let _ = Command::new("taskkill.exe").args(["/PID", &child.id().to_string(), "/T", "/F"])
          .creation_flags(CREATE_NO_WINDOW).stdout(Stdio::null()).stderr(Stdio::null()).status();
      }
      let _ = child.kill();
      let _ = child.wait();
    }
  }
}

#[tauri::command]
async fn desktop_install_update(app: tauri::AppHandle, pending: tauri::State<'_, PendingUpdate>) -> Result<(), String> {
  let update = pending.0.lock().map_err(|_| "Update state unavailable")?.take().ok_or("Check for updates first")?;
  // Download verifies the signature before the engine is stopped or an installer runs.
  let bytes = update.download(|_, _| {}, || {}).await.map_err(|_| "Update download or signature verification failed. Nothing was installed.")?;
  stop_local_api();
  update.install(bytes).map_err(|_| "Update installation failed. Restart NullCS and retry.")?;
  app.restart();
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
  let app = tauri::Builder::default()
    .plugin(tauri_plugin_updater::Builder::new().build())
    .manage(PendingUpdate::default())
    .invoke_handler(tauri::generate_handler![desktop_service_status, desktop_service_start, desktop_pick_demo_file, desktop_open_external_url, desktop_save_report, desktop_check_update, desktop_install_update])
    .setup(|app| {
      let resource_root = app.path().resource_dir().ok().and_then(|path| {
        let direct = path.join("nullcs-backend");
        if direct.is_dir() {
          return Some(direct);
        }
        let nested = path.join("resources").join("nullcs-backend");
        if nested.is_dir() {
          return Some(nested);
        }
        None
      });
      let _ = PACKAGED_BACKEND_ROOT.set(resource_root);
      let data_root = app.path().app_data_dir().ok().map(|path| path.join("backend-data"));
      if let Some(path) = data_root.as_ref() {
        fs::create_dir_all(path)?;
        let lock = OpenOptions::new().create(true).truncate(false).read(true).write(true).open(path.join("desktop.lock"))?;
        lock.try_lock().map_err(|_| "NullCS is already running. Use the existing window.")?;
        let _ = INSTANCE_LOCK.set(lock);
      }
      let _ = APP_DATA_DIR.set(data_root);
      if cfg!(debug_assertions) {
        app.handle().plugin(
          tauri_plugin_log::Builder::default()
            .level(log::LevelFilter::Info)
            .build(),
        )?;
      }
      Ok(())
    })
    .build(tauri::generate_context!())
    .expect("error while building tauri application");
  app.run(|_, event| {
    if matches!(event, tauri::RunEvent::Exit) { stop_local_api(); }
  });
}

#[cfg(test)]
mod tests {
  use super::*;
  #[test]
  fn hash_matches_known_sha256() {
    let root = env::temp_dir().join(format!("nullcs-hash-{}", Uuid::new_v4()));
    fs::create_dir(&root).unwrap();
    let file = root.join("data"); fs::write(&file, b"abc").unwrap();
    assert_eq!(certutil_sha256(&file).unwrap(), "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad");
    fs::remove_dir_all(root).unwrap();
  }
  #[test]
  fn model_cache_replaces_changed_artifacts() {
    let root = env::temp_dir().join(format!("nullcs-cache-{}", Uuid::new_v4()));
    let source = root.join("source"); let destination = root.join("destination");
    fs::create_dir_all(&source).unwrap(); fs::create_dir_all(&destination).unwrap();
    fs::write(source.join("model"), b"new").unwrap(); fs::write(destination.join("model"), b"old").unwrap();
    copy_dir_missing(&source, &destination).unwrap();
    assert_eq!(fs::read(destination.join("model")).unwrap(), b"new");
    fs::remove_dir_all(root).unwrap();
  }
  #[test]
  fn external_links_reject_untrusted_urls() {
    assert!(allowed_external_url("https://steamcommunity.com/profiles/76561198000000000"));
    assert!(!allowed_external_url("https://steamcommunity.com.evil.test/profiles/76561198000000000"));
    assert!(!allowed_external_url("file:///C:/Windows/system32/cmd.exe"));
  }
}
