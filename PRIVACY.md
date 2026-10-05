# Scholion Privacy Policy

**Last updated: October 4, 2026**

Scholion is a free, open-source, local-first desktop application for recorded evidence. Its privacy model is intentionally simple: recordings, transcripts, research notes, speaker labels, saved searches, and other user research stay on the user's computer unless the user deliberately moves or publishes them.

This policy describes the official Scholion project and the software distributed from [raccoon-compile/Scholion](https://github.com/raccoon-compile/Scholion). Forks, third-party builds, operating-system services, package hosts, model hosts, and other external services have their own privacy practices.

## What Scholion does not collect

The Scholion project does not operate an account system, hosted corpus, cloud transcription service, behavioral analytics service, advertising system, or product telemetry backend.

Scholion does not intentionally send the project maintainers:

- recordings or video;
- transcript text or canonical transcript evidence;
- research notes, tags, collections, saved searches, or speaker names;
- local file paths or recording names;
- hardware or model inventory;
- application usage history;
- installation or device identifiers; or
- crash reports.

Scholion does not sell user data and does not use user data for advertising.

## What stays on the user's computer

Scholion stores application state locally. Depending on the features a user chooses, local state can include:

- references to source recordings and their verified identity;
- canonical transcript JSON;
- human-authored research such as notes, tags, collections, saved searches, and speaker display names;
- private search and research indexes;
- processing checkpoints and temporary working material;
- downloaded model files and model-trust metadata;
- application preferences; and
- local release/update trust state.

Canonical transcript evidence and human-authored research are treated as durable user-owned data. Search indexes, derived exports, caches, and other rebuildable projections are treated separately so they can be recreated without becoming the only copy of unique evidence or research.

Scholion does not upload this local corpus to the project maintainers.

## Network activity

Scholion is designed to work locally, but some explicit actions require a network connection.

### Application update checks

A manual update check requests signed release metadata from a fixed GitHub-hosted location. The request does not include an installation ID, recordings, transcripts, research content, hardware inventory, model inventory, or behavioral telemetry.

GitHub and its delivery infrastructure can observe ordinary network metadata associated with the request, such as an IP address, request time, and standard transport information. Their handling of that information is governed by their own policies.

Source/development builds without the production update-verification material keep application update checking off.

### Application downloads

Official release artifacts are distributed through GitHub. Downloading Scholion therefore creates ordinary network traffic to GitHub and its delivery infrastructure. Scholion does not control GitHub's independent logging or privacy practices.

### Model downloads

When a user explicitly chooses to install a transcription or diarization model, Scholion may connect to Hugging Face to obtain the reviewed model files. Hugging Face and its delivery infrastructure can observe ordinary network metadata associated with those requests and, for models requiring authentication, information necessary to authenticate the request.

Model downloads are explicit. Once the required model is installed, supported local transcription and diarization workflows can run from local model custody without uploading the recording to a hosted transcription service.

Scholion disables pyannote metrics/telemetry when loading the supported diarization integration.

## Local transcription and research

Transcription, diarization, indexing, search, evidence navigation, playback authorization, note-taking, speaker labeling, and research workflows are designed to run locally.

The original recording is treated as read-only during normal processing. Scholion creates transcript evidence and derived working material separately.

The desktop interface does not receive unrestricted filesystem, database, shell, or update-network authority. Sensitive filesystem paths are kept behind the native/application boundary where possible rather than being exposed to the WebView.

## Logs and diagnostics

Scholion does not automatically upload application logs or diagnostic reports to the project maintainers.

Local logs and qualification evidence are designed to minimize disclosure of private paths and user content. A user can still choose to share logs, screenshots, files, or other information when reporting a problem. Anything a user deliberately posts to GitHub or another public service is subject to that service's privacy practices and the visibility chosen by the user.

## Operating-system and security services

Windows, macOS, antivirus products, certificate infrastructure, application reputation systems, or other operating-system services may independently perform security, certificate, reputation, or download checks when Scholion is installed or launched. Those checks are performed by the relevant platform or service, not by Scholion's application telemetry, and are governed by the provider's policies.

## Deletion and retention

Scholion provides explicit controls for removing local application state and, where separately authorized, source media.

Scholion does not claim cryptographically guaranteed secure erasure. Modern filesystems, SSDs, snapshots, backups, synchronization tools, and operating-system caches can retain copies outside Scholion's control.

Because the Scholion project does not receive a copy of the user's local corpus, the project maintainers generally have no remote copy of that corpus to delete.

## Third-party services

Depending on the actions a user chooses, Scholion may interact with:

- **GitHub**, for source code, release downloads, and signed application-update metadata;
- **Hugging Face**, for explicitly requested model downloads; and
- **operating-system trust/security services**, which may independently evaluate downloaded or installed software.

These services are separate controllers of their own network and account data. Their privacy policies apply to their services.

Scholion does not grant these services access to the user's local recordings, transcripts, or research merely by using Scholion.

## Changes to this policy

Changes to this policy are made in the public Scholion repository and are reviewable through version control. Material changes should accompany the release or code change that makes them necessary rather than silently broadening data collection.

## Questions or privacy reports

Privacy questions or reports about Scholion can be raised through the project's public issue tracker:

https://github.com/raccoon-compile/Scholion/issues

If a report would itself contain sensitive information, do not post recordings, transcripts, private paths, credentials, or other confidential material publicly. Use the private reporting path documented in [SECURITY.md](SECURITY.md) when appropriate.
