from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import tempfile
from contextlib import AbstractContextManager, nullcontext
from pathlib import Path
from typing import Any

from verify_cross_platform_media_acceptance import _fetch_public_fixture

_EXPECTED_WORDS = frozenset({"fellow", "americans", "country", "ask", "you"})
_MIN_EXPECTED_WORDS = 3


def _run_runtime(
    runtime: Path,
    mode: str,
    *,
    env: dict[str, str],
    payload: object | None = None,
) -> dict[str, Any]:
    completed = subprocess.run(  # noqa: S603
        [str(runtime), mode],
        input=None if payload is None else json.dumps(payload),
        capture_output=True,
        check=False,
        text=True,
        env=env,
        timeout=300,
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip()
        raise RuntimeError(
            f"packaged runtime mode {mode!r} failed" + (f": {detail}" if detail else "")
        )
    try:
        value = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"packaged runtime mode {mode!r} did not return JSON"
        ) from exc
    if not isinstance(value, dict):
        raise RuntimeError(f"packaged runtime mode {mode!r} returned a non-object")
    return value


def _runtime_environment(root: Path) -> dict[str, str]:
    output_dir = root / "output"
    env = os.environ.copy()
    env.update(
        {
            "SCHOLION_STATE_DIR": str(root / "state"),
            "SCHOLION_CACHE_DIR": str(root / "cache"),
            "SCHOLION_MODEL_DIR": str(root / "cache" / "models"),
            "SCHOLION_OUTPUT_DIR": str(output_dir),
            "SCHOLION_MAX_CPU_THREADS": "2",
            "SCHOLION_MIN_FREE_DISK_BYTES": "0",
            "SCHOLION_WARN_FREE_DISK_BYTES": "0",
        }
    )
    return env


def _require_worker_success(payload: dict[str, Any], *, operation: str) -> None:
    if payload.get("protocol_version") != 1 or payload.get("ok") is not True:
        raise RuntimeError(f"packaged {operation} worker did not report success")
    if payload.get("error") is not None:
        raise RuntimeError(
            f"packaged {operation} worker returned contradictory error state"
        )


def _load_expected_model(catalog_path: Path, model_id: str) -> dict[str, Any]:
    try:
        document = json.loads(catalog_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError("expected model trust catalog is unavailable") from exc
    if not isinstance(document, dict):
        raise RuntimeError("expected model trust catalog is invalid")
    raw_models = document.get("models")
    if not isinstance(raw_models, list):
        raise RuntimeError("expected model trust catalog omitted models")
    match = next(
        (
            item
            for item in raw_models
            if isinstance(item, dict) and item.get("model_id") == model_id
        ),
        None,
    )
    if match is None:
        raise RuntimeError("expected model trust catalog omitted qualified model")
    return match


def _validate_policy_receipt(
    model_dir: Path,
    *,
    expected_model: dict[str, Any],
) -> tuple[Path, dict[str, Any]]:
    manifest_path = model_dir / "registry" / "faster-whisper" / "tiny.json"
    try:
        document = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError("packaged trusted model manifest is unavailable") from exc
    if not isinstance(document, dict):
        raise RuntimeError("packaged trusted model manifest is invalid")
    revision = expected_model.get("revision")
    files = expected_model.get("files")
    if not isinstance(revision, str) or not isinstance(files, list) or not files:
        raise RuntimeError("expected model trust entry is invalid")
    policy = document.get("policy_trust")
    if not isinstance(policy, dict):
        raise RuntimeError("packaged model install omitted policy trust receipt")
    expected_total = sum(
        item.get("size_bytes", 0)
        for item in files
        if isinstance(item, dict) and isinstance(item.get("size_bytes"), int)
    )
    if (
        document.get("resolved_revision") != revision
        or policy.get("model_id") != "tiny"
        or policy.get("revision") != revision
        or policy.get("verification") != "scholion_curated_sha256_v1"
        or policy.get("verified_files") != len(files)
        or policy.get("total_bytes") != expected_total
    ):
        raise RuntimeError("packaged model policy receipt does not match reviewed policy")
    return manifest_path, document


def _bridge_request(
    runtime: Path,
    *,
    env: dict[str, str],
    request_id: str,
    method: str,
    params: dict[str, object],
) -> dict[str, Any]:
    return _run_runtime(
        runtime,
        "bridge",
        env=env,
        payload={
            "protocol_version": 1,
            "request_id": request_id,
            "method": method,
            "params": params,
        },
    )


def _qualify_legacy_policy_migration(
    runtime: Path,
    *,
    env: dict[str, str],
    input_path: Path,
    manifest_path: Path,
    manifest: dict[str, Any],
) -> None:
    revision = manifest.get("resolved_revision")
    if not isinstance(revision, str) or not revision:
        raise RuntimeError("packaged model manifest omitted resolved revision")
    legacy = dict(manifest)
    legacy["policy_trust"] = None
    manifest_path.write_text(json.dumps(legacy, sort_keys=True), encoding="utf-8")

    readiness = _bridge_request(
        runtime,
        env=env,
        request_id="package-legacy-readiness",
        method="processing.readiness",
        params={"profile": "screening"},
    )
    result = readiness.get("result")
    if (
        readiness.get("ok") is not True
        or not isinstance(result, dict)
        or result.get("model_policy_enforced") is not True
        or not isinstance(result.get("model_policy_trust"), dict)
        or result["model_policy_trust"].get("tiny") is not False
    ):
        raise RuntimeError("packaged legacy model was not reported as untrusted")
    models = result.get("models")
    tiny = next(
        (
            item
            for item in models
            if isinstance(models, list)
            and isinstance(item, dict)
            and item.get("model_id") == "tiny"
        ),
        None,
    )
    if tiny is None or tiny.get("installed") is not True:
        raise RuntimeError("packaged legacy model disappeared from inventory")

    preflight = _bridge_request(
        runtime,
        env=env,
        request_id="package-legacy-preflight",
        method="processing.preflight",
        params={
            "input_path": str(input_path),
            "profile": "screening",
            "strategy_id": "tiny-cpu-int8",
        },
    )
    if preflight.get("ok") is not False or preflight.get("result") is not None:
        raise RuntimeError("packaged legacy model authorized new execution admission")

    removal = _run_runtime(
        runtime,
        "processing-worker",
        env=env,
        payload={
            "task_id": "package-remove-legacy-tiny",
            "kind": "model_remove",
            "model_id": "tiny",
            "expected_revision": revision,
        },
    )
    _require_worker_success(removal, operation="legacy model removal")

def _words(text: str) -> set[str]:
    return set(re.findall(r"[^\W\d_]+", text.lower(), flags=re.UNICODE))


def _one_canonical(output_dir: Path) -> tuple[dict[str, Any], str]:
    candidates = tuple(output_dir.glob("*.json"))
    if len(candidates) != 1:
        raise RuntimeError(
            f"expected one packaged canonical transcript, found {len(candidates)}"
        )
    raw = candidates[0].read_text(encoding="utf-8")
    document = json.loads(raw)
    if not isinstance(document, dict):
        raise RuntimeError("packaged canonical transcript is not a JSON object")
    return document, raw


def _validate_source(document: dict[str, Any], input_path: Path) -> None:
    source = document.get("source")
    if not isinstance(source, dict):
        raise RuntimeError("packaged canonical transcript omitted source provenance")
    expected_hash = hashlib.sha256(input_path.read_bytes()).hexdigest()
    if source.get("sha256") != expected_hash:
        raise RuntimeError("packaged canonical transcript recorded wrong source hash")
    if source.get("size_bytes") != input_path.stat().st_size:
        raise RuntimeError(
            "packaged canonical transcript recorded wrong source byte size"
        )


def _validate_engine(document: dict[str, Any]) -> None:
    engine = document.get("engine")
    if not isinstance(engine, dict):
        raise RuntimeError("packaged canonical transcript omitted engine provenance")
    if engine.get("name") != "faster-whisper" or engine.get("model") != "tiny":
        raise RuntimeError("packaged canonical transcript recorded wrong engine/model")
    if engine.get("device") != "cpu" or engine.get("compute_type") != "int8":
        raise RuntimeError(
            "packaged canonical transcript recorded wrong execution target"
        )
    if not str(engine.get("model_revision", "")).strip():
        raise RuntimeError(
            "packaged canonical transcript omitted immutable model revision"
        )


def _validate_recognized_speech(document: dict[str, Any]) -> None:
    segments = document.get("segments")
    if not isinstance(segments, list) or not segments:
        raise RuntimeError(
            "packaged canonical transcript contains no recognized segments"
        )
    recognized = " ".join(
        str(segment.get("text", ""))
        for segment in segments
        if isinstance(segment, dict)
    )
    if len(_words(recognized) & _EXPECTED_WORDS) < _MIN_EXPECTED_WORDS:
        raise RuntimeError(
            "packaged transcription did not recover enough known JFK speech"
        )


def _validate_privacy(raw: str, private_paths: tuple[Path, ...]) -> None:
    lowered = raw.lower()
    for private_path in private_paths:
        normalized = str(private_path).strip().lower()
        if normalized and normalized in lowered:
            raise RuntimeError(
                "packaged canonical evidence leaked a private local path"
            )


def _validate_canonical(
    document: dict[str, Any],
    raw: str,
    *,
    input_path: Path,
    state_dir: Path,
    model_dir: Path,
) -> None:
    _validate_source(document, input_path)
    _validate_engine(document)
    _validate_recognized_speech(document)
    _validate_privacy(raw, (input_path.parent, state_dir, model_dir))


def _workspace_context(
    workspace_root: Path | None,
) -> AbstractContextManager[str | Path]:
    if workspace_root is None:
        return tempfile.TemporaryDirectory(prefix="scholion-packaged-acceptance-")
    resolved = workspace_root.expanduser().resolve(strict=False)
    if resolved.exists() and any(resolved.iterdir()):
        raise RuntimeError("retained packaged acceptance workspace must start empty")
    resolved.mkdir(parents=True, exist_ok=True)
    return nullcontext(resolved)


def verify(
    runtime: Path,
    *,
    workspace_root: Path | None = None,
    model_trust_catalog: Path | None = None,
) -> None:
    runtime = runtime.expanduser().resolve(strict=True)
    expected_model = (
        None
        if model_trust_catalog is None
        else _load_expected_model(model_trust_catalog.resolve(strict=True), "tiny")
    )
    if not runtime.is_file():
        raise RuntimeError("packaged runtime executable is missing")

    with _workspace_context(workspace_root) as temporary:
        root = Path(temporary)
        env = _runtime_environment(root)

        info = _run_runtime(runtime, "runtime-info", env=env)
        if (
            info.get("protocol_version") != 1
            or info.get("runtime") != "scholion-desktop"
        ):
            raise RuntimeError("packaged runtime identity contract is invalid")
        for field in (
            "scholion_version",
            "python_version",
            "faster_whisper_version",
            "ctranslate2_version",
            "duckdb_version",
            "lingua_version",
        ):
            if not str(info.get(field, "")).strip():
                raise RuntimeError(f"packaged runtime omitted {field}")

        input_path = _fetch_public_fixture(root)
        install = _run_runtime(
            runtime,
            "processing-worker",
            env=env,
            payload={
                "task_id": "package-install-tiny",
                "kind": "model_install",
                "model_id": "tiny",
            },
        )
        _require_worker_success(install, operation="model install")
        policy_manifest: tuple[Path, dict[str, Any]] | None = None
        if expected_model is not None:
            policy_manifest = _validate_policy_receipt(
                Path(env["SCHOLION_MODEL_DIR"]),
                expected_model=expected_model,
            )

        offline_env = dict(env)
        offline_env.update(
            {
                "HF_HUB_OFFLINE": "1",
                "TRANSFORMERS_OFFLINE": "1",
            }
        )
        transcribe = _run_runtime(
            runtime,
            "processing-worker",
            env=offline_env,
            payload={
                "task_id": "package-transcribe-jfk",
                "kind": "transcription_start",
                "job_id": "package-jfk",
                "input_path": str(input_path),
                "profile": "screening",
                "strategy_id": "tiny-cpu-int8",
                "export_formats": ["txt", "srt", "vtt"],
            },
        )
        _require_worker_success(transcribe, operation="transcription")

        output_dir = Path(env["SCHOLION_OUTPUT_DIR"])
        document, raw = _one_canonical(output_dir)
        _validate_canonical(
            document,
            raw,
            input_path=input_path,
            state_dir=Path(env["SCHOLION_STATE_DIR"]),
            model_dir=Path(env["SCHOLION_MODEL_DIR"]),
        )
        for suffix in (".txt", ".srt", ".vtt"):
            if len(tuple(output_dir.glob(f"*{suffix}"))) != 1:
                raise RuntimeError(
                    f"packaged transcription omitted {suffix} publication"
                )

        if policy_manifest is not None:
            manifest_path, manifest = policy_manifest
            _qualify_legacy_policy_migration(
                runtime,
                env=env,
                input_path=input_path,
                manifest_path=manifest_path,
                manifest=manifest,
            )

        print(
            "accepted packaged Scholion runtime: real JFK transcription, offline inference, "
            "canonical provenance, and deterministic publications"
        )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Qualify an installed/final bundled Scholion runtime with real media."
    )
    parser.add_argument("runtime", type=Path)
    parser.add_argument(
        "--workspace-root",
        type=Path,
        help="Retain acceptance state under this empty directory for lifecycle checks.",
    )
    parser.add_argument(
        "--model-trust-catalog",
        type=Path,
        help="Reviewed model policy expected to be enforced by this packaged runtime.",
    )
    arguments = parser.parse_args()
    verify(
        arguments.runtime,
        workspace_root=arguments.workspace_root,
        model_trust_catalog=arguments.model_trust_catalog,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
