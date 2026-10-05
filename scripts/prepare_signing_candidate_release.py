from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class PlatformCandidate:
    label: str
    runner_os: str
    package_subdir: str
    package_suffix: str
    notarized: bool | None


_PLATFORMS = (
    PlatformCandidate(
        label="windows",
        runner_os="Windows",
        package_subdir="nsis",
        package_suffix=".exe",
        notarized=None,
    ),
    PlatformCandidate(
        label="macos",
        runner_os="macOS",
        package_subdir="dmg",
        package_suffix=".dmg",
        notarized=False,
    ),
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_json(path: Path, description: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"{description} is not readable JSON: {path}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{description} must be a JSON object")
    return value


def _require(value: bool, message: str) -> None:
    if not value:
        raise ValueError(message)


def _qualification_artifact(
    qualification: dict[str, Any],
    *,
    relative_path: str,
) -> dict[str, Any]:
    artifacts = qualification.get("artifacts")
    _require(isinstance(artifacts, list), "qualification artifacts must be a list")
    matches = [
        item
        for item in artifacts
        if isinstance(item, dict) and item.get("path") == relative_path
    ]
    _require(
        len(matches) == 1,
        f"qualification must contain exactly one record for {relative_path}",
    )
    return matches[0]


def _provenance_artifact(
    provenance: dict[str, Any],
    *,
    relative_path: str,
) -> dict[str, Any]:
    artifacts = provenance.get("artifacts")
    _require(isinstance(artifacts, list), "provenance artifacts must be a list")
    matches = [
        item
        for item in artifacts
        if isinstance(item, dict) and item.get("path") == relative_path
    ]
    _require(
        len(matches) == 1,
        f"provenance must contain exactly one record for {relative_path}",
    )
    return matches[0]


def _load_checksums(path: Path) -> dict[str, str]:
    records: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        parts = line.split("  ", 1)
        _require(len(parts) == 2, f"invalid SHA256SUMS line: {line!r}")
        digest, relative = parts
        _require(
            len(digest) == 64
            and all(character in "0123456789abcdef" for character in digest),
            "SHA256SUMS digest must be lowercase SHA-256",
        )
        _require(relative not in records, f"duplicate SHA256SUMS path: {relative}")
        records[relative] = digest
    _require(bool(records), "SHA256SUMS must not be empty")
    return records


def _stage_platform(
    artifact_root: Path,
    output_dir: Path,
    *,
    platform: PlatformCandidate,
    expected_commit: str,
) -> None:
    artifact_root = artifact_root.resolve(strict=True)
    bundle_root = (
        artifact_root / "frontend" / "src-tauri" / "target" / "release" / "bundle"
    )
    package_root = bundle_root / platform.package_subdir
    packages = sorted(package_root.glob(f"*{platform.package_suffix}"))
    _require(
        len(packages) == 1,
        f"{platform.label} candidate must contain exactly one "
        f"{platform.package_suffix} package in {platform.package_subdir}",
    )
    package = packages[0]
    relative_package = package.relative_to(bundle_root).as_posix()

    evidence_root = artifact_root / "release-preview"
    qualification_path = evidence_root / "qualification.json"
    provenance_path = evidence_root / "provenance.json"
    checksums_path = evidence_root / "SHA256SUMS"
    qualification = _load_json(qualification_path, "qualification")
    provenance = _load_json(provenance_path, "provenance")
    checksums = _load_checksums(checksums_path)

    _require(
        qualification.get("schema_version") == 1, "unsupported qualification schema"
    )
    _require(
        qualification.get("qualification") == "unsigned-preview",
        "signing candidate must originate from unsigned-preview qualification",
    )
    _require(
        qualification.get("commit") == expected_commit,
        "qualification commit does not match publication commit",
    )
    _require(
        qualification.get("runner_os") == platform.runner_os,
        f"qualification runner must be {platform.runner_os}",
    )
    _require(
        qualification.get("release_ready") is False,
        "signing candidate must remain explicitly non-production",
    )

    trust = qualification.get("platform_trust")
    _require(isinstance(trust, dict), "qualification platform_trust is missing")
    _require(
        trust.get("scholion_release_verified") is False,
        "prerelease candidate must not claim final Scholion release verification",
    )
    _require(
        trust.get("os_publisher_verified") is False,
        "prerelease candidate must not claim OS publisher verification",
    )
    _require(
        trust.get("os_notarized") is platform.notarized,
        f"unexpected {platform.label} notarization state",
    )

    qualified = qualification.get("qualified")
    _require(isinstance(qualified, dict), "qualification checks are missing")
    for key in (
        "tauri_package_build",
        "exact_package_install_or_mount",
        "package_identity_metadata",
        "artifact_sha256",
    ):
        _require(qualified.get(key) is True, f"required qualification failed: {key}")

    package_digest = _sha256(package)
    package_size = package.stat().st_size
    qualification_record = _qualification_artifact(
        qualification,
        relative_path=relative_package,
    )
    _require(
        qualification_record.get("sha256") == package_digest,
        "package digest does not match qualification",
    )
    _require(
        qualification_record.get("size_bytes") == package_size,
        "package size does not match qualification",
    )
    _require(
        checksums.get(relative_package) == package_digest,
        "package digest does not match qualification SHA256SUMS",
    )

    _require(provenance.get("schema_version") == 1, "unsupported provenance schema")
    _require(
        provenance.get("qualification") == "unsigned-preview",
        "provenance qualification is not unsigned-preview",
    )
    _require(
        provenance.get("commit") == expected_commit,
        "provenance commit does not match publication commit",
    )
    runner = provenance.get("runner")
    _require(
        isinstance(runner, dict) and runner.get("os") == platform.runner_os,
        "provenance runner OS does not match platform",
    )
    _require(
        provenance.get("qualification_sha256") == _sha256(qualification_path),
        "provenance qualification hash does not match evidence",
    )
    _require(
        provenance.get("sha256sums_sha256") == _sha256(checksums_path),
        "provenance SHA256SUMS hash does not match evidence",
    )
    provenance_record = _provenance_artifact(
        provenance,
        relative_path=relative_package,
    )
    _require(
        provenance_record.get("sha256") == package_digest
        and provenance_record.get("size_bytes") == package_size,
        "package identity does not match provenance",
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    destination = output_dir / package.name
    _require(not destination.exists(), f"duplicate release asset name: {package.name}")
    shutil.copy2(package, destination)
    shutil.copy2(
        qualification_path,
        output_dir / f"{platform.label}-qualification.json",
    )
    shutil.copy2(
        provenance_path,
        output_dir / f"{platform.label}-provenance.json",
    )


def _write_release_checksums(output_dir: Path) -> None:
    assets = sorted(
        path
        for path in output_dir.iterdir()
        if path.is_file() and path.name != "SHA256SUMS"
    )
    _require(bool(assets), "no prerelease assets were staged")
    lines = [f"{_sha256(path)}  {path.name}" for path in assets]
    (output_dir / "SHA256SUMS").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate and stage exact qualified Scholion signing candidates."
    )
    parser.add_argument("--windows-artifact-root", type=Path, required=True)
    parser.add_argument("--macos-artifact-root", type=Path, required=True)
    parser.add_argument("--expected-commit", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    arguments = parser.parse_args()

    _require(
        len(arguments.expected_commit) == 40
        and all(
            character in "0123456789abcdef" for character in arguments.expected_commit
        ),
        "expected commit must be a lowercase 40-hex Git SHA",
    )

    output_dir = arguments.output_dir.resolve()
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True)

    roots = {
        "windows": arguments.windows_artifact_root,
        "macos": arguments.macos_artifact_root,
    }
    for platform in _PLATFORMS:
        _stage_platform(
            roots[platform.label],
            output_dir,
            platform=platform,
            expected_commit=arguments.expected_commit,
        )
    _write_release_checksums(output_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
