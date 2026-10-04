from __future__ import annotations

import hashlib
import json
import os
import tempfile
from contextlib import contextmanager
from pathlib import Path
from urllib.request import Request, urlopen

from scholion.interfaces.local_file_manager import LocalFileManager
from scholion.model_management.catalog import faster_whisper_model_catalog
from scholion.model_management.errors import ModelManagementError
from scholion.model_management.provider import HuggingFaceModelProvider
from scholion.model_management.service import ModelManager
from scholion.supply_chain import load_model_trust_catalog
from scholion.transcription.backend import FasterWhisperTranscriber
from scholion.transcription.models import CpuEngineConfiguration
from scholion.transcription.strategy import faster_whisper_catalog

_JFK_FIXTURE_URL = (
    "https://raw.githubusercontent.com/openai/whisper/"
    "86098128c0b4f24f0e2aa2994de830614b474227/tests/jfk.flac"
)
_JFK_FIXTURE_GIT_BLOB = "e44b7c13897eae7f78beb220c61fe77429a3961d"
_JFK_FIXTURE_SIZE = 1_152_693
_MAX_FIXTURE_BYTES = 2 * 1024 * 1024
_EXPECTED_WORDS = frozenset({"fellow", "americans", "country", "ask", "you"})
_MIN_EXPECTED_WORDS = 3


def _repository_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _git_blob_sha1(payload: bytes) -> str:
    header = f"blob {len(payload)}\0".encode("ascii")
    return hashlib.sha1(header + payload, usedforsecurity=False).hexdigest()


def _fetch_fixture(root: Path) -> Path:
    request = Request(
        _JFK_FIXTURE_URL,
        headers={"User-Agent": "Scholion-model-policy-qualification/1"},
    )
    with urlopen(request, timeout=60) as response:  # noqa: S310
        payload = response.read(_MAX_FIXTURE_BYTES + 1)
    if len(payload) != _JFK_FIXTURE_SIZE:
        raise RuntimeError("public acceptance fixture size changed unexpectedly")
    if _git_blob_sha1(payload) != _JFK_FIXTURE_GIT_BLOB:
        raise RuntimeError("public acceptance fixture identity changed unexpectedly")
    fixture = root / "jfk.flac"
    fixture.write_bytes(payload)
    return fixture


@contextmanager
def _offline_hub_environment():
    values = {
        "HF_HUB_OFFLINE": "1",
        "HF_HUB_DISABLE_TELEMETRY": "1",
        "TRANSFORMERS_OFFLINE": "1",
    }
    previous = {key: os.environ.get(key) for key in values}
    os.environ.update(values)
    try:
        yield
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def _words(text: str) -> set[str]:
    return {
        "".join(character for character in token.lower() if character.isalpha())
        for token in text.split()
        if token.strip()
    }


def _rewrite_as_legacy_install(
    manager: ModelManager,
    store: LocalFileManager,
    model_id: str,
) -> None:
    manifest_path = manager.registry_root / f"{model_id}.json"
    document = json.loads(store.read_file(manifest_path).decode("utf-8"))
    if not isinstance(document, dict) or document.get("policy_trust") is None:
        raise RuntimeError("trusted install did not record policy evidence")
    document["policy_trust"] = None
    store.save_file(
        json.dumps(document, sort_keys=True).encode("utf-8"),
        manifest_path,
        private=True,
    )


def verify_production_model_policy() -> dict[str, object]:
    repository_root = _repository_root()
    catalog_path = repository_root / "packaging" / "release-trust" / "model-trust.json"
    catalog_payload = catalog_path.read_bytes()
    trust_catalog = load_model_trust_catalog(catalog_path)
    trusted_spec = trust_catalog.require("tiny")

    with tempfile.TemporaryDirectory(
        prefix="scholion-model-policy-qualification-"
    ) as temporary:
        root = Path(temporary).resolve()
        fixture = _fetch_fixture(root)
        store = LocalFileManager()
        manager = ModelManager(
            catalog=faster_whisper_model_catalog(faster_whisper_catalog()),
            provider=HuggingFaceModelProvider(),
            file_store=store,
            model_root=root / "models",
            trust_catalog=trust_catalog,
            enforce_policy_trust=True,
        )

        manifest = manager.install("tiny")
        if manifest.resolved_revision != trusted_spec.revision:
            raise RuntimeError("managed install did not resolve the trusted revision")
        if manifest.policy_trust is None:
            raise RuntimeError("managed install omitted policy trust evidence")
        if manifest.policy_trust.verified_files != len(trusted_spec.files):
            raise RuntimeError("managed install verified the wrong model file count")
        if not manager.is_policy_trusted("tiny"):
            raise RuntimeError("installed model did not revalidate as policy trusted")
        if manager.resolved_revision("tiny") != trusted_spec.revision:
            raise RuntimeError("execution admission lost the trusted model revision")

        configuration = CpuEngineConfiguration(
            engine="faster-whisper",
            model="tiny",
            device="cpu",
            compute_type="int8",
            cpu_threads=2,
            beam_size=1,
            language="en",
            model_cache_path=manager.cache_root,
            model_revision=trusted_spec.revision,
        )
        with _offline_hub_environment():
            transcript = FasterWhisperTranscriber().open_session(configuration).transcribe(
                fixture
            )
        recognized = _words(" ".join(segment.text for segment in transcript.segments))
        matches = recognized & _EXPECTED_WORDS
        if len(matches) < _MIN_EXPECTED_WORDS:
            raise RuntimeError("offline trusted-model transcription was too weak")

        _rewrite_as_legacy_install(manager, store, "tiny")
        legacy_item = manager.inventory()[0]
        if not legacy_item.installed or legacy_item.policy_trusted:
            raise RuntimeError(
                "legacy managed model was not visible as installed-but-untrusted"
            )

        try:
            manager.resolved_revision("tiny")
        except ModelManagementError:
            execution_rejected = True
        else:
            raise RuntimeError("legacy untrusted model authorized a new execution")

        removed = manager.remove("tiny")
        if removed.resolved_revision != trusted_spec.revision:
            raise RuntimeError("legacy model removal returned the wrong revision")
        post_remove = manager.inventory()[0]
        if post_remove.installed:
            raise RuntimeError("legacy model remained registered after removal")

        return {
            "schema_version": 1,
            "catalog_sha256": hashlib.sha256(catalog_payload).hexdigest(),
            "trusted_install": {
                "model_id": manifest.model_id,
                "revision": manifest.resolved_revision,
                "verification": manifest.policy_trust.verification,
                "verified_files": manifest.policy_trust.verified_files,
                "total_bytes": manifest.policy_trust.total_bytes,
            },
            "offline_transcription": {
                "engine_version": transcript.engine_version,
                "segments": len(transcript.segments),
                "expected_words_matched": len(matches),
                "hub_offline": True,
            },
            "legacy_migration": {
                "visible": True,
                "policy_trusted": False,
                "execution_rejected": execution_rejected,
                "removable": True,
            },
        }


def main() -> int:
    print(json.dumps(verify_production_model_policy(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
