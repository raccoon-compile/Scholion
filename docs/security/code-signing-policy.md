# Code signing policy

Scholion treats code signing as one layer of a broader release-trust model. A platform signature can identify a publisher and protect executable integrity, but it does not replace Scholion's own signed release metadata, exact artifact hashes, deterministic provenance, SBOM material, or runtime qualification.

This policy is provider-neutral. A signing service or certificate authority may change without changing the guarantees Scholion requires from the release process.

## Trust layers

Scholion keeps three claims separate:

1. **Scholion release verification** means the project has authorized signed metadata that binds an exact platform artifact by identity, size, and SHA-256.
2. **OS publisher verification** means the operating system can validate the platform-specific publisher signature attached to the application or installer.
3. **OS notarization** means an additional platform service has reviewed or attested to an artifact. This is currently relevant to Apple's notarization service and is not interchangeable with publisher signing.

Release tooling and documentation must not collapse these claims into a single generic "trusted" state.

## Release authorization

Production release artifacts must come from an approved source commit and the reviewed release workflow.

The maintainer responsible for publication is also responsible for approving any production signing request and confirming that:

- the source commit is intended for release;
- the release workflow and build inputs are reviewed;
- only project-owned binaries are submitted under Scholion's publisher identity;
- returned signed artifacts match the expected release contents;
- applicable platform signatures verify before publication; and
- authoritative hashes and provenance are generated only after every byte-mutating signing or notarization step is complete.

A signing provider may add its own approval ceremony. Provider-specific mechanics are subordinate to these project rules.

## Windows

The Windows production release requires publisher signing before it can be described as production-ready.

The intended signing scope includes Scholion-owned Windows executables and the final NSIS installer. Bundled third-party executables, including reviewed upstream media tools, are not to be re-signed as though Scholion authored them.

Windows release qualification must verify the expected publisher signature on each intended signing target and fail closed when production policy requires signing but a signature is missing, invalid, or unexpected.

Where packaging contains project-owned executables inside a final installer, inner project-owned executables should be signed before final installer construction/signing when supported by the selected signing implementation.

## macOS

The current first-release policy does not require Apple Developer ID signing or Apple notarization.

The exact macOS artifact must still be project-verified through Scholion's signed release metadata, final SHA-256, provenance, SBOM material, and representative-device qualification. Release documentation must state clearly when the artifact is not Apple Developer ID signed or notarized.

Scholion must not strip quarantine metadata, disable Gatekeeper, or silently bypass macOS security policy.

If Apple Developer ID signing or notarization is added later, those steps must occur before authoritative artifact hashes and Scholion release metadata are finalized. The resulting Apple trust state must be recorded explicitly rather than inferred from project verification.

## Artifact identity

Project-owned release binaries must carry consistent product identity and version metadata appropriate to their platform.

The release workflow must verify package/application identity against the release configuration before publication. Identity checks include, where applicable:

- product name;
- application identifier / bundle identifier;
- product version; and
- expected platform artifact type.

Metadata is part of the release contract. It must not be treated as decorative packaging.

## Final-byte rule

Signing and notarization can change artifact bytes.

Therefore the authoritative release order is:

```text
approved source commit
  -> deterministic build
  -> verify package/application identity
  -> apply applicable platform signing/notarization
  -> verify applicable platform trust
  -> compute final SHA-256 + provenance
  -> bind exact final artifact in Scholion signed release metadata
  -> lifecycle / representative-device qualification
  -> publish exact artifact
```

No checksum calculated before the final byte-mutating trust step may be presented as the identity of the distributed artifact.

## Credential custody

Private signing keys, certificate material, passwords, API tokens, and equivalent secrets must not be committed to Git, embedded in application resources, written to ordinary logs, or published as release artifacts.

Managed/HSM-backed signing is preferred when practical because it avoids exporting long-lived private signing material into the build environment.

## Third-party binaries

Scholion may package reviewed third-party open-source binaries. Their provenance and integrity must be documented separately.

A third-party binary must not be signed under Scholion's publisher identity unless Scholion is actually responsible for that source and the applicable signing policy permits it.

## Privacy

Code signing does not grant a signing provider access to Scholion's local recordings, transcripts, research state, or application corpus.

See [Scholion Privacy Policy](../../PRIVACY.md) for the project's user-data and network-activity contract.

## External signing providers

A provider may be integrated only after the project has actually been approved or provisioned for that service.

Until then, documentation may describe a provider as under evaluation or pending, but must not state or imply that the provider signs Scholion releases.

Provider-specific credentials, identifiers, actions, or attribution belong in the implementation/onboarding layer rather than in this core policy.
