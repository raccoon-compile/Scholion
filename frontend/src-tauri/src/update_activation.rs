use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::path::{Path, PathBuf};
#[cfg(target_os = "macos")]
use std::process::{Command, Stdio};
use tauri::State;

use crate::backend::{self, DesktopRuntime};

const ACTIVATION_REQUEST_ID: &str = "native-update-activation";

#[derive(Debug, Deserialize)]
struct ActivationBridgeError {
    message: String,
}

#[derive(Debug, Deserialize)]
struct ActivationTicket {
    schema_version: u8,
    platform: String,
    version: String,
    sequence: u64,
    size_bytes: u64,
    sha256: String,
    staged_path: String,
}

#[derive(Debug, Deserialize)]
struct ActivationBridgeResponse {
    protocol_version: u8,
    request_id: String,
    ok: bool,
    result: Option<ActivationTicket>,
    error: Option<ActivationBridgeError>,
}

#[derive(Debug, Serialize)]
pub struct ActivationOutcome {
    activation_state: &'static str,
    version: String,
    message: String,
}

fn expected_platform_id() -> Option<String> {
    let os = if cfg!(target_os = "windows") {
        "windows"
    } else if cfg!(target_os = "macos") {
        "macos"
    } else {
        return None;
    };
    let architecture = match std::env::consts::ARCH {
        "x86_64" => "x86_64",
        "aarch64" => "aarch64",
        _ => return None,
    };
    Some(format!("{os}-{architecture}"))
}

fn parse_ticket(value: Value) -> Result<ActivationTicket, String> {
    let response: ActivationBridgeResponse = serde_json::from_value(value)
        .map_err(|_| "Scholion's native update authorization was invalid".to_string())?;
    if response.protocol_version != 1 || response.request_id != ACTIVATION_REQUEST_ID {
        return Err("Scholion's native update authorization was incompatible".to_string());
    }
    if !response.ok {
        return Err(response
            .error
            .map(|error| error.message)
            .unwrap_or_else(|| {
                "Scholion could not authorize the staged update for installation".to_string()
            }));
    }
    if response.error.is_some() {
        return Err("Scholion's native update authorization was invalid".to_string());
    }
    let ticket = response
        .result
        .ok_or_else(|| "Scholion's native update authorization was incomplete".to_string())?;
    if ticket.schema_version != 1
        || ticket.sequence == 0
        || ticket.size_bytes == 0
        || ticket.version.trim().is_empty()
        || ticket.sha256.len() != 64
        || !ticket
            .sha256
            .bytes()
            .all(|byte| byte.is_ascii_digit() || (b'a'..=b'f').contains(&byte))
    {
        return Err("Scholion's native update ticket was invalid".to_string());
    }
    let expected = expected_platform_id()
        .ok_or_else(|| "Native update activation is not supported on this platform".to_string())?;
    if ticket.platform != expected {
        return Err("The staged update does not match this platform".to_string());
    }
    let path = Path::new(&ticket.staged_path);
    if !path.is_absolute() || !path.is_file() {
        return Err("The staged update package is unavailable".to_string());
    }
    Ok(ticket)
}

#[cfg(target_os = "windows")]
fn activate_platform(ticket: ActivationTicket) -> Result<ActivationOutcome, String> {
    let path = PathBuf::from(&ticket.staged_path);
    if path.extension().and_then(|value| value.to_str()) != Some("exe") {
        return Err("The staged Windows update is not an executable installer".to_string());
    }

    // #173 owns the publisher identity/certificate custody choice. Until that exact
    // publisher trust can be verified here, launching the installer would turn
    // project-level hash/signature verification into a substitute for Authenticode.
    Err(
        "Windows publisher verification is required before Scholion can activate this update"
            .to_string(),
    )
}

#[cfg(target_os = "macos")]
fn activate_platform(ticket: ActivationTicket) -> Result<ActivationOutcome, String> {
    let path = PathBuf::from(&ticket.staged_path);
    if path.extension().and_then(|value| value.to_str()) != Some("dmg") {
        return Err("The staged macOS update is not a disk image".to_string());
    }

    Command::new("/usr/bin/open")
        .arg(&path)
        .stdin(Stdio::null())
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .spawn()
        .map_err(|_| "macOS could not open the verified Scholion disk image".to_string())?;

    Ok(ActivationOutcome {
        activation_state: "handoff_started",
        version: ticket.version,
        message: (
            "macOS opened the exact verified Scholion disk image. Complete the replacement "
                .to_string()
                + "through the operating system; Gatekeeper and any per-app approval remain in effect."
        ),
    })
}

#[cfg(not(any(target_os = "windows", target_os = "macos")))]
fn activate_platform(_ticket: ActivationTicket) -> Result<ActivationOutcome, String> {
    Err("Native update activation is not supported on this platform".to_string())
}

#[tauri::command]
pub async fn update_activate(
    runtime: State<'_, DesktopRuntime>,
) -> Result<ActivationOutcome, String> {
    let response = backend::native_update_activation_ticket(runtime.inner().clone()).await?;
    let ticket = parse_ticket(response)?;
    activate_platform(ticket)
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    fn ticket_value(platform: &str, staged_path: &Path) -> Value {
        json!({
            "protocol_version": 1,
            "request_id": ACTIVATION_REQUEST_ID,
            "ok": true,
            "result": {
                "schema_version": 1,
                "platform": platform,
                "version": "0.2.0",
                "sequence": 2,
                "size_bytes": 42,
                "sha256": "a".repeat(64),
                "staged_path": staged_path,
            },
            "error": null,
        })
    }

    #[test]
    fn ticket_parser_rejects_path_or_platform_substitution() {
        let temporary = tempfile::tempdir().expect("temporary directory");
        let package = temporary.path().join("candidate.bin");
        std::fs::write(&package, b"candidate").expect("write candidate");

        let wrong_platform = if expected_platform_id().as_deref() == Some("windows-x86_64") {
            "macos-x86_64"
        } else {
            "windows-x86_64"
        };
        assert!(parse_ticket(ticket_value(wrong_platform, &package)).is_err());

        let relative = json!({
            "protocol_version": 1,
            "request_id": ACTIVATION_REQUEST_ID,
            "ok": true,
            "result": {
                "schema_version": 1,
                "platform": expected_platform_id().unwrap_or_else(|| "linux-x86_64".to_string()),
                "version": "0.2.0",
                "sequence": 2,
                "size_bytes": 42,
                "sha256": "a".repeat(64),
                "staged_path": "relative/candidate.bin",
            },
            "error": null,
        });
        assert!(parse_ticket(relative).is_err());
    }

    #[test]
    fn failed_bridge_response_does_not_yield_ticket() {
        let value = json!({
            "protocol_version": 1,
            "request_id": ACTIVATION_REQUEST_ID,
            "ok": false,
            "result": null,
            "error": {
                "code": "update_activation_not_authorized",
                "message": "Scholion could not authorize the staged update for installation",
            },
        });
        assert!(parse_ticket(value).is_err());
    }
}
