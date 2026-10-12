# Native release qualification checklist

Browser mocks are necessary but insufficient evidence for a desktop application. Before a release candidate is considered qualified, exercise the real native seams on representative machines.

Issue #114 owns the remaining representative native Processing task-transport evidence. Passing Playwright/axe, Rust tests, and hosted platform smoke is valuable but does not by itself close that requirement.

## Processing transport

For each supported OS, verify through the native Tauri window that:

- Processing readiness leaves `Checking…` and renders actual CPU/RAM/accelerator information;
- model inventory appears from the real Python bridge;
- previous-job history loads independently from readiness;
- model install/remove shows the relevant row in an explicit running state;
- transcription/model workers return only bounded public success/failure outcomes;
- a known safe application failure is shown immediately without a traceback/path/content leak;
- durable job state still refreshes after failure so Resume/Retry decisions are correct;
- speaker labeling is disabled with the backend's safe reason when the optional runtime is missing or security-held;
- the native host refuses a second supervised long-running Processing task while one is active;
- cancellation terminates the supervised child without turning native in-memory task state into job authority;
- a missing/broken Python interpreter produces a bounded, useful error;
- a child process that exits non-zero produces a bounded, useful error;
- an invalid protocol response produces a bounded, useful error;
- a stalled readiness request does not spin forever;
- a successful background refresh clears an older background warning without erasing an unrelated action error; and
- debug diagnostics do not include evidence paths, transcript text, request params, model-cache paths, or private exception details.

## Update channel

The browser Updates tests prove presentation and state-machine behavior only. A production release candidate must additionally prove through the real Tauri window that:

- a source/development build without the production verifier reports **Update checking is off** and performs no update request;
- a release build with the pinned production public key starts in **Never checked** and performs no background check;
- **Check for updates** contacts only the fixed Scholion metadata location;
- ordinary connection metadata is the only unavoidable network disclosure and no installation/corpus/hardware/model/behavior identifier is added to the request;
- a valid current stable manifest produces **Up to date** or **Trusted update available** as appropriate;
- bad signature, unknown/revoked key, expiry, future publication time, rollback, same-sequence equivocation, wrong channel, unsupported platform, offline transport, and malformed metadata all fail closed without blocking local evidence work;
- the highest trusted sequence survives application restart and is never transmitted;
- **Download and verify** stages only the artifact authorized for the current platform;
- short, oversized, or hash-mismatching downloads leave no trusted staged package;
- the staged file exactly matches the signed byte count and SHA-256;
- **Prepare for installation** re-verifies the cached signed metadata and exact staged bytes immediately before native handoff;
- missing, expired, mutated, oversized, or hash-mismatching staged state fails closed at preparation time;
- the staged filesystem path never crosses into React and preparation executes no installer;
- staging/readiness/handoff never presents itself as completed installation;
- **Continue installation** carries no caller path or installer arguments;
- on macOS, the exact verified DMG receives a quarantine marker that is read back successfully before OS handoff; Gatekeeper is never disabled or bypassed;
- on Windows, activation remains blocked unless the required publisher trust can be verified; and
- replacement/restart/recovery behavior is qualified on representative devices before release.

Record update qualification against the actual production public key and release metadata. Synthetic browser fixtures cannot satisfy this gate.

## Curated model trust

With the exact catalog intended for the release, verify natively that:

- every bundled faster-whisper entry came from a reviewed immutable revision and generated exact file-set/size/SHA-256 measurement;
- a fresh install requests the catalog revision rather than a moving upstream ref;
- a byte mutation, missing file, undeclared file, size mismatch, repository mismatch, or revision mismatch invalidates current policy trust;
- an older locally valid installation remains visible/removable after enforcement turns on but is refused for new transcription until curated reinstall succeeds;
- the Processing Center distinguishes **installed** from **trusted by this Scholion build**; and
- once the trusted snapshot is installed, transcription works offline with no hosted model/transcription service.

Do not populate the production catalog from whichever development snapshot happens to be present on a qualification machine.

## Representative machines

The Windows/macOS MVP does **not** require a five-machine benchmark zoo. Record the smallest real-device evidence set that proves the distinct release boundaries:

- one genuinely CPU-only class for #114 Processing task-transport qualification;
- one supported-accelerator class for #114 Processing task-transport qualification;
- Apple Silicon macOS for #173/#174 Gatekeeper, first-launch, update-handoff, replacement, and recovery behavior; and
- a real Windows system for #173/#174 signed-installer/update behavior once the production publisher-signing path exists.

These are evidence classes, not necessarily four different computers. One machine may satisfy more than one applicable row when it genuinely has the relevant hardware/platform characteristics. Do not manufacture CPU-only evidence merely by disabling a supported accelerator if the purpose of the check is resource discovery/admission.

Linux Wayland/X11 qualification becomes a release requirement only when #135 is unblocked for an official Linux binary. A 32/64 GB high-end workstation remains useful post-MVP performance/calibration evidence, not a first-release gate.

Hardware policy must remain conservative on small devices and must not artificially disable feasible acceleration on capable devices.

### Current qualification status

| Class | Current evidence | Status |
|---|---|---|
| CPU-only representative machine | Hosted CI exercises CPU code paths, but no representative real-device #114 task-transport qualification has been recorded | **Pending** |
| Supported-accelerator representative machine | Earlier development dogfooding proved accelerator discovery before the complete task-feedback/trust tranches landed | **Partial; rerun current main** |
| Apple Silicon macOS | Platform smoke exists, representative native desktop/task/update/Gatekeeper qualification not yet recorded | **Pending** |
| Windows release device | Platform smoke and unsigned package lifecycle qualification exist; signed installer/update behavior awaits #173 publisher trust and representative-device evidence | **Pending** |
| Linux Wayland/X11 | Source/development qualification remains useful, but official Linux release evidence is deferred while #135 is open | **Deferred from Windows/macOS MVP** |

Do not upgrade a `Partial` row to qualified based only on browser mocks or hosted CI. Record the date/version, operating-system class, CPU/RAM class, accelerator class (if any), exercised flows, and pass/fail result without publishing local usernames, hostnames, home-directory paths, recording names, or copied private logs.

## Linux desktop stack

Qualify at least one Wayland and one X11 session. Record whether WebKitGTK requires the per-launch `WEBKIT_DISABLE_DMABUF_RENDERER=1` workaround. Do not silently persist that environment variable system-wide.

The current GTK3-era Tauri graph is separately release-blocked by issue #135 because of the tracked GLib unsoundness. Passing this functional checklist does not waive that dependency gate.

## Hostile-media containment

Current FFprobe/FFmpeg controls already include no-shell invocation, file-only media protocols, explicit timeouts, FFmpeg `-nostdin`, bounded FFprobe metadata, source mutation checks, and planned private decode output. Those controls are useful but are not an operating-system sandbox.

Before making a strong hostile-media-hardening claim, qualify the maintained platform containment design documented in [Pre-release security hardening](../security/release-hardening.md): Linux namespace/seccomp-style reduction, macOS hardened/sandbox restrictions, and Windows restricted-token/AppContainer/job-object equivalent as appropriate. Exercise malformed/truncated/adversarial media through that real native boundary.

## Dependency/bootstrap recovery

From a clean checkout on each OS:

1. bootstrap Python with the project-local toolchain (`python3.12 scripts/bootstrap_python.py` or the documented Windows equivalent);
2. delete `.venv` and prove it can be recreated without deleting `.tools/uv`;
3. run `npm ci` from `frontend/`;
4. run `npm run doctor:desktop`;
5. run the locked native Cargo compile;
6. launch the native app and exercise Processing readiness and one supervised long-running task; and
7. exercise the Updates screen in the build's actual trust-key state.

Also qualify a pull in which one or more lockfiles changed. The contributor workflow should identify which disposable installed state must be synchronized instead of recommending global package upgrades.

## Supply-chain and containment gates

Before public distribution, execute the acceptance criteria in [Pre-release security hardening](../security/release-hardening.md) for signed manifests, update/model trust, platform signing, and hostile-input/process containment.

The repository now implements fixed-endpoint manual update orchestration, private anti-rollback state, exact signed artifact staging and pre-handoff re-verification, bounded native activation, the reviewed production Ed25519 public verification catalog, the reviewed tiny/small/medium faster-whisper policy, and deterministic release/model trust metadata generation. Production enablement still requires Windows publisher signing, the representative native evidence above, completion of the remaining platform-specific activation/recovery qualification, and final #175 publication evidence. Linux binary release remains separately blocked by #135. This checklist must not turn hosted CI or synthetic fixtures into implied representative-device completion.

Application-layer encryption/keychain work follows its documented threat model and recovery contract rather than being inferred from this checklist.
