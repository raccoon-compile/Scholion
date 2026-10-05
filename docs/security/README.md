# Scholion security design notes

Scholion is local-first, but local-first is not synonymous with automatically safe. Security work covers evidence custody, hostile media parsing, process capability, dependency/model provenance, update authenticity, secret/key storage, and recovery semantics.

## Current release-hardening plan

See **[Pre-release security hardening roadmap](release-hardening.md)** for the current gate structure covering:

- signed application metadata and privacy-preserving manual updates;
- curated model policy rooted in signed Scholion releases;
- native package signing/activation and representative qualification;
- hostile-media parser containment and the boundary between current controls and a real OS sandbox; and
- deliberately deferred keychain/application-layer encryption work that requires a concrete threat/recovery model.

The application-side update/model-trust mechanics were completed in merged PR #144, issue #145 completed the pre-packaging trust-input/redundancy/documentation/icon freeze, PR #164 established the Windows/macOS managed-runtime and exact unsigned preview-package boundary, PR #166 completed deterministic release provenance plus evidence-safe Windows uninstall/reinstall qualification, PR #167 completed repository-owned packaged FFmpeg/FFprobe custody, PRs #170/#172 established native Ed25519 verification and deterministic trust-input custody, and PRs #207/#209 completed the real production public-key/model-policy and signed-fixture qualification. Windows publisher signing, macOS open-source distribution qualification, native update activation, representative-device evidence, and final publication are the remaining first-release gates.

See **[Signed update and model trust channel](update-model-trust.md)** for the implemented exact-byte signed update envelope, anti-rollback/expiry/equivocation semantics, privacy-preserving update behavior, and project-owned pinned model metadata with complete file-set/size/SHA-256 verification.

See **[Production trust inputs](production-trust-inputs.md)** for the frozen native verifier choice (`ed25519-dalek` 3.0.0), key-rotation/custody rules, the reviewed faster-whisper trust entries, and the completed production-shaped package/signed-fixture qualification. Private signing material remains external to the repository and CI.

See **[Code signing policy](code-signing-policy.md)** for the provider-neutral distinction between Scholion release verification, OS publisher verification, and OS notarization, plus the post-signing final-byte rule.

Issue #114 remains qualification-only for representative native Processing task transport. Issue #135 remains the upstream-blocked official Linux binary gate.

Backup/restore, packaged semantic custody, and broader research-native features are post-MVP product work rather than pre-release security blockers. Repository vulnerability reporting and disclosure policy remain in the root **[SECURITY.md](../../SECURITY.md)**.
