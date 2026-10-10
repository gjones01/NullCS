use std::{path::Path, process::{Command, Stdio}};

fn certutil_sha256(path: &Path) -> Option<String> {
  let output = Command::new("certutil")
    .arg("-hashfile")
    .arg(path)
    .arg("SHA256")
    .stdout(Stdio::piped())
    .stderr(Stdio::null())
    .output()
    .ok()?;
  if !output.status.success() {
    return None;
  }
  let stdout = String::from_utf8_lossy(&output.stdout);
  stdout
    .lines()
    .map(|line| line.trim().replace(' ', "").to_ascii_lowercase())
    .find(|line| line.len() == 64 && line.chars().all(|ch| ch.is_ascii_hexdigit()))
}

fn main() {
  println!("cargo:rerun-if-env-changed=NULLCS_UPDATE_ENDPOINT");
  println!("cargo:rerun-if-env-changed=NULLCS_UPDATE_PUBLIC_KEY");
  let manifest = Path::new("resources").join("nullcs-backend").join("backend_manifest.json");
  println!("cargo:rerun-if-changed={}", manifest.display());
  let hash = certutil_sha256(&manifest).unwrap_or_default();
  if std::env::var("PROFILE").as_deref() == Ok("release") && hash.len() != 64 {
    panic!("Prepare the backend resources before building a release");
  }
  println!("cargo:rustc-env=NULLCS_BACKEND_MANIFEST_SHA256={hash}");
  tauri_build::build()
}
