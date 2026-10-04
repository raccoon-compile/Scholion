# Production update-signature qualification fixture

This directory is **qualification evidence**, not a published Scholion release.

The payload uses the same stable update-manifest schema, deterministic canonical JSON
encoding, artifact size/SHA-256 fields, release key ID, and native verification path as a
real release. The three tiny artifact files are inert text markers so hosted CI can exercise
trusted check/staging behavior without downloading or executing a release installer.

The payload bytes are frozen before signing:

- key ID: `release-2026-a`
- sequence: `1`
- version: `0.2.0-qualification`
- payload SHA-256: `a2fe67af89973f5d2b3978c3da4731ea4ce3b026585a43772699668244a49306`
- payload size: `1031` bytes

The private Ed25519 signing key remains outside Git, GitHub Actions, application resources,
logs, fixtures, and ordinary development files.

## External signing

Sign the exact `payload.json` bytes in a controlled environment with the production
`release-2026-a` private key. For OpenSSL 3.x, the operation is equivalent to:

```bash
openssl pkeyutl -sign -rawin \
  -inkey /private/location/scholion-release-private.pem \
  -in packaging/release-trust/update-qualification/payload.json \
  -out /tmp/scholion-update-qualification.sig
```

The result must be exactly 64 raw Ed25519 signature bytes. Only that signature is public
qualification material. Exact private-key locations, passphrases, recovery locations, and
private-key bytes must not be committed or pasted into issues/PRs/chat.

Once the signature is reviewed and added as `signature.bin`, Release Qualification uses
the installed/mounted native Tauri executable and its bundled production
`update-keys.json` to prove:

- the exact payload is accepted under `release-2026-a`;
- payload mutation, signature mutation, and unknown key IDs fail closed;
- the normal update service accepts the signed fixture at a fixed qualification time; and
- the exact inert platform fixture is staged using the signed size/SHA-256 contract.

The qualification clock is fixed within the payload validity interval so this evidence does
not become nondeterministically stale after the fixture's real-world expiry date.
