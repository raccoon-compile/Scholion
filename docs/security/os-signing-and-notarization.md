# OS distribution trust

Scholion has two separate distribution-trust layers. They must not be collapsed into one another.

1. **Scholion project trust** verifies Scholion's signed update metadata and exact staged artifact bytes using the project's Ed25519 release key.
2. **Operating-system distribution trust** is platform-specific. Windows can authenticate the publisher through code signing. macOS can provide Apple Developer ID identity and notarization when the project participates in Apple's paid developer program.

The first-release policy intentionally treats those platform paths differently.

## First-release policy

### Windows

The Windows production release remains required to use an appropriate production code-signing credential/certificate path. The final application/installer bytes must be signed, the signature must be verified on the exact bytes users receive, and the post-signing SHA-256 identity must be bound into release evidence.

Private Windows signing material must stay outside Git, application resources, ordinary CI logs, and published artifacts.

### macOS

Scholion is free and open-source software. The project does **not** currently budget for the recurring Apple Developer Program membership required for Developer ID signing/notarization. Apple Developer ID notarization is therefore **not a first-release blocker**.

The macOS production artifact must instead satisfy all of the following:

1. the exact artifact is built from the approved release commit and reviewed production trust inputs;
2. Scholion's signed Ed25519 release metadata binds that exact artifact by platform, size, and SHA-256;
3. release publication includes human-auditable SHA-256 checksums, deterministic provenance, SBOM material, and qualification evidence for those same bytes;
4. the download/release surface explicitly states that the macOS build is **not Apple Developer ID signed/notarized** and may require explicit per-app approval by macOS;
5. representative macOS qualification exercises the exact distributed artifact and records the actual Gatekeeper/first-launch behavior observed on the tested system; and
6. Scholion never strips quarantine metadata, disables Gatekeeper, or silently bypasses macOS security policy on the user's behalf.

This is **Scholion project verification**, not Apple certification. The project should not describe the macOS package as Apple-trusted, Apple-notarized, or Apple-certified.

If funding later becomes available, Developer ID signing/notarization may be added as an additional platform trust layer. It must not replace Scholion's own release-signature, checksum, provenance, or SBOM evidence.

## Why the distinction matters

Scholion's Ed25519 release key answers a project-level question:

> Did the Scholion project authorize metadata that binds this exact platform artifact?

Windows code signing answers a platform publisher question:

> Does Windows recognize the publisher credential that signed these exact application/installer bytes?

Apple Developer ID/notarization would answer a separate Apple-platform question:

> Did an Apple-issued Developer ID sign this submission, and did Apple's notarization service accept it?

These are complementary claims. None of them should be represented as stronger than it is.

## macOS user disclosure

The release notes and repository download guidance must say, in substance:

> Scholion's macOS build is not Apple Developer ID signed or notarized. Scholion is free/open-source software and the project does not currently participate in Apple's paid Developer ID/notarization program. macOS may warn that it cannot verify the developer or require explicit per-app approval before first launch. Scholion publishes signed release metadata, SHA-256 checksums, deterministic provenance, SBOM material, and qualification evidence for the exact distributed artifact. Do not disable Gatekeeper globally.

Do not hard-code a regional Apple membership price into durable security documentation. Fees and platform rules can change independently of this repository.

## Relationship to Scholion's Ed25519 update key

| Object | Purpose | First-release status |
|---|---|---|
| Scholion Ed25519 release key | signs Scholion update metadata and authorizes exact artifact identity | required |
| Windows signing credential | lets Windows identify/trust the publisher of the Windows application/installer | required |
| Apple Developer ID identity/notarization | lets macOS evaluate an Apple-identified/notarized direct-download app | optional/deferred until funded |

The installed application contains only public verification material it needs. Private project/platform signing material never belongs in the shipped app.

## Release sequence

1. **#177** create and safeguard the real Scholion Ed25519 release key and reviewed public verification catalog;
2. **#178** review and pin the first-release faster-whisper snapshots;
3. **#168** bind those exact public trust inputs into a production-shaped candidate and qualify them end to end;
4. **#173** complete Windows code signing and qualify the macOS open-source distribution trust/disclosure path;
5. **#174** activate only already-project-verified staged updates through the narrow native host while preserving each platform's applicable security policy;
6. **#114** record representative native device qualification, including actual macOS first-launch behavior; and
7. **#175** publish final checksums, provenance, SBOM, signatures, signed update metadata, disclosure, and supported release artifacts.

`release_ready` remains false until the applicable release gates are complete.

## Boundaries

- no Mac App Store distribution is required;
- no platform signing credential belongs in source control, fixtures, logs, or ordinary artifacts;
- Windows signing does not replace Scholion's Ed25519 release verification;
- Scholion's Ed25519 verification does not claim Apple notarization;
- Scholion must not automate Gatekeeper bypass or global security weakening;
- hosted CI package success does not substitute for representative-device evidence;
- official Linux binary distribution remains separately governed by #135.

Related: #168, #173, #174, #175, #177, #178, #114, #135, `production-trust-inputs.md`, `update-model-trust.md`.
