#!/usr/bin/env python3
"""Qualify the production release key through the packaged native verifier."""

from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from scholion.interfaces.local_file_manager import LocalFileManager
from scholion.supply_chain.native_update_verifier import NativeUpdateVerifier
from scholion.supply_chain.release_tools import assemble_signed_update_envelope
from scholion.supply_chain.update_manifest import (
    UpdateManifestPayload,
    UpdateTrustError,
    verify_signed_update_manifest,
)
from scholion.update_channel.service import (
    UpdateChannelError,
    UpdateChannelService,
    UpdateStateStore,
    current_platform_id,
)

_KEY_ID = "release-2026-a"
_FIXED_NOW = datetime(2026, 10, 4, 12, 0, tzinfo=UTC)
_EXPECTED_PAYLOAD_SHA256 = (
    "a2fe67af89973f5d2b3978c3da4731ea4ce3b026585a43772699668244a49306"
)


class _FixtureTransport:
    def __init__(
        self,
        manifest: dict[str, Any],
        artifacts: dict[str, bytes],
    ) -> None:
        self.manifest = manifest
        self.artifacts = artifacts

    def fetch_manifest(self, url: str) -> dict[str, Any]:
        del url
        return self.manifest

    def stage_verified_artifact(
        self,
        url: str,
        *,
        destination: Path,
        expected_size: int,
        expected_sha256: str,
    ) -> None:
        content = self.artifacts.get(url)
        if content is None:
            raise UpdateChannelError("qualification artifact URL was not recognized")
        if len(content) != expected_size:
            raise UpdateChannelError(
                "qualification artifact size did not match metadata"
            )
        if hashlib.sha256(content).hexdigest() != expected_sha256:
            raise UpdateChannelError(
                "qualification artifact hash did not match metadata"
            )
        destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        destination.write_bytes(content)


def _load_fixture(
    fixture_dir: Path,
) -> tuple[bytes, bytes, dict[str, bytes], UpdateManifestPayload]:
    payload = (fixture_dir / "payload.json").read_bytes()
    signature = (fixture_dir / "signature.bin").read_bytes()
    if len(signature) != 64:
        raise RuntimeError(
            "production qualification signature must be exactly 64 bytes"
        )
    if hashlib.sha256(payload).hexdigest() != _EXPECTED_PAYLOAD_SHA256:
        raise RuntimeError("production qualification payload identity changed")

    parsed = UpdateManifestPayload.from_bytes(payload)
    artifacts: dict[str, bytes] = {}
    for artifact in parsed.artifacts:
        filename = Path(artifact.url).name
        content = (fixture_dir / filename).read_bytes()
        if len(content) != artifact.size_bytes:
            raise RuntimeError("qualification artifact size changed")
        if hashlib.sha256(content).hexdigest() != artifact.sha256_hex:
            raise RuntimeError("qualification artifact hash changed")
        artifacts[artifact.url] = content
    return payload, signature, artifacts, parsed


def _require_native_signature_behavior(
    verifier: NativeUpdateVerifier,
    *,
    payload: bytes,
    signature: bytes,
) -> None:
    if not verifier.verify(
        key_id=_KEY_ID,
        algorithm="ed25519",
        payload=payload,
        signature=signature,
    ):
        raise RuntimeError("packaged native verifier rejected the production signature")

    tampered_payload = bytearray(payload)
    tampered_payload[-1] ^= 1
    if verifier.verify(
        key_id=_KEY_ID,
        algorithm="ed25519",
        payload=bytes(tampered_payload),
        signature=signature,
    ):
        raise RuntimeError("packaged native verifier accepted payload mutation")

    tampered_signature = bytearray(signature)
    tampered_signature[0] ^= 1
    if verifier.verify(
        key_id=_KEY_ID,
        algorithm="ed25519",
        payload=payload,
        signature=bytes(tampered_signature),
    ):
        raise RuntimeError("packaged native verifier accepted signature mutation")

    if verifier.verify(
        key_id="unknown-release-key",
        algorithm="ed25519",
        payload=payload,
        signature=signature,
    ):
        raise RuntimeError("packaged native verifier accepted an unknown key ID")


def _require_update_service_behavior(
    verifier: NativeUpdateVerifier,
    *,
    payload: bytes,
    signature: bytes,
    artifacts: dict[str, bytes],
    parsed: UpdateManifestPayload,
) -> dict[str, object]:
    envelope = json.loads(
        assemble_signed_update_envelope(
            payload,
            key_id=_KEY_ID,
            signature=signature,
        )
    )
    if not isinstance(envelope, dict):
        raise RuntimeError("production qualification envelope is invalid")

    platform_id = current_platform_id()
    selected = parsed.artifact_for(platform_id)
    transport = _FixtureTransport(envelope, artifacts)

    with tempfile.TemporaryDirectory(
        prefix="scholion-update-qualification-"
    ) as temporary:
        root = Path(temporary).resolve()
        store = LocalFileManager()
        service = UpdateChannelService(
            current_version="0.1.0",
            cache_dir=root / "cache",
            state_store=UpdateStateStore(root / "state", store),
            verifier=verifier,
            transport=transport,
            platform_id=platform_id,
        )
        checked = service.check(now=_FIXED_NOW)
        if checked.get("state") != "trusted_update_available":
            raise RuntimeError("production-signed fixture was not trusted as an update")

        staged = service.stage(now=_FIXED_NOW)
        if staged.get("state") != "staged":
            raise RuntimeError("production-signed fixture was not staged")

        staged_path = (
            root
            / "cache"
            / "updates"
            / "staged"
            / f"release-{parsed.sequence}-{platform_id}.bin"
        )
        if staged_path.read_bytes() != artifacts[selected.url]:
            raise RuntimeError("staged qualification artifact bytes changed")

        prepared = service.prepare_activation(now=_FIXED_NOW)
        if prepared.get("activation_state") != "ready_to_install":
            raise RuntimeError(
                "production-signed fixture was not re-verified for native handoff"
            )

    return {
        "platform": platform_id,
        "sequence": parsed.sequence,
        "version": parsed.version,
        "artifact_size_bytes": selected.size_bytes,
        "artifact_sha256": selected.sha256_hex,
        "check_state": "trusted_update_available",
        "stage_state": "staged",
        "activation_state": "ready_to_install",
    }


def verify(native_verifier: Path, fixture_dir: Path) -> dict[str, object]:
    executable = native_verifier.expanduser().resolve(strict=True)
    directory = fixture_dir.expanduser().resolve(strict=True)
    payload, signature, artifacts, parsed = _load_fixture(directory)
    verifier = NativeUpdateVerifier(executable)

    _require_native_signature_behavior(
        verifier,
        payload=payload,
        signature=signature,
    )

    try:
        verified = verify_signed_update_manifest(
            json.loads(
                assemble_signed_update_envelope(
                    payload,
                    key_id=_KEY_ID,
                    signature=signature,
                )
            ),
            verifier=verifier,
            now=_FIXED_NOW,
        )
    except UpdateTrustError as exc:
        raise RuntimeError("production-signed envelope failed update trust") from exc
    if verified != parsed:
        raise RuntimeError("verified production fixture payload changed")

    service = _require_update_service_behavior(
        verifier,
        payload=payload,
        signature=signature,
        artifacts=artifacts,
        parsed=parsed,
    )
    return {
        "schema_version": 1,
        "key_id": _KEY_ID,
        "payload_sha256": hashlib.sha256(payload).hexdigest(),
        "native_signature_verified": True,
        "tamper_rejected": True,
        "unknown_key_rejected": True,
        "update_service": service,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Qualify a production-key-signed update fixture through packaged trust."
    )
    parser.add_argument("--native-verifier", type=Path, required=True)
    parser.add_argument("--fixture-dir", type=Path, required=True)
    arguments = parser.parse_args()
    print(
        json.dumps(
            verify(arguments.native_verifier, arguments.fixture_dir),
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
