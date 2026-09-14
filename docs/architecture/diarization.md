# Anonymous speaker diarization 👥

Scholion treats diarization as **speaker-timeline evidence**, not identity.

In ordinary language: diarization tries to answer **who spoke when inside this one
recording?** It gives recording-scoped labels such as `speaker-01` and `speaker-02` so a
transcript can say which anonymous voice most likely owns a passage.

It does **not** mean “identify this human,” and Scholion does not infer that
`speaker-01` in one recording is the same person as `speaker-01` in another.

![Anonymous speaker diarization 👥 diagram](../diagrams/generated/anonymous-speaker-diarization.svg)

[Diagram source (Mermaid)](../diagrams/src/anonymous-speaker-diarization.mmd)

## What the user would see

The intended CLI surface is opt-in:

```bash
uv run scholion transcribe interview.wav --diarize
```

If the speaker count is known:

```bash
uv run scholion transcribe focus-group.wav --diarize --speakers 4
```

Or provide a bounded range:

```bash
uv run scholion transcribe meeting.wav --diarize --min-speakers 2 --max-speakers 6
```

Exact and bounded speaker-count options are mutually exclusive. Speaker-count options
are invalid without `--diarize`.

The desktop Processing Center exposes the same intent without requiring CLI knowledge.
When **Label speakers automatically** is enabled, the user can leave speaker counting on
**Let Scholion estimate**, provide an exact count they already know, or provide a minimum
and maximum range. These values are user-supplied constraints, not speaker identities or
claims that the model independently inferred the participant count.

## Current operational status: patched runtime and real-model acceptance qualified ✅

The first adapter targets the open-source pyannote `community-1` pipeline.

Scholion now locks Lightning 2.6.6 or newer for the diarization extra. Lightning 2.6.6
shipped the upstream fixes for CVE-2026-58659 / PYSEC-2026-3624, the
checkpoint-loading remote-code-execution vulnerability that previously held this feature
closed. The runtime still fails closed before pyannote import or model acquisition when
the installed Lightning version is older than 2.6.6 or cannot be proven stable.

The locked Lightning 2.6.6 + pyannote 4.0.7 runtime has been installed from the clean
lock graph, exercised through the deterministic diarization/status tests, built as a
distribution, and reinstalled through the clean-wheel diarization lane.

One scanner-specific exception remains temporarily because GitHub's reviewed advisory
copy currently records the malformed fixed version `2022.6.15`. PyPA's canonical
advisory records `fixed: 2.6.6`, the advisory text says releases through 2.6.5 are
affected, and Lightning 2.6.6 release notes document the fixes. The OSV exception is
therefore bounded metadata-drift compensation, not permission to run an affected
Lightning release, and expires so the repository must re-evaluate the upstream record.

PR #183 completed the separate credential-gated real-model boundary. Scholion's pinned
two-speaker acceptance fixture contains overlapping speech and a ground-truth RTTM. The
acceptance harness supplies the fixture's known two-speaker count, downloads Community-1
through authenticated Hugging Face access, runs real inference against the pinned ground
truth, then runs inference again from the local cache with model download disabled.
Pyannote telemetry remains disabled for both runs.

That proof matters because it exercises the actual model/runtime/native-audio path rather
than substituting a mock or import-only check. It is still a bounded acceptance fixture,
not a claim that diarization is perfect on arbitrary meetings, many-speaker recordings,
heavy overlap, similar voices, or poor microphones.

So the current product description is deliberately precise:

> **Diarization is integrated on the patched Lightning 2.6.6+ runtime, clean-install
> qualified, and proven against real Community-1 two-speaker inference plus cache-only
> reuse. Speaker attribution remains probabilistic derived evidence that users may need
> to correct on difficult recordings.**

## Privacy and model-acquisition boundary

Pyannote model acquisition may require accepting upstream model conditions and
authenticating with Hugging Face.

Scholion does not store a Hugging Face token in its own configuration.

Any model download authorization is narrowly scoped to diarization:

```bash
uv run scholion transcribe interview.wav \
  --diarize \
  --allow-diarization-model-download
```

That flag does **not** authorize faster-whisper model downloads. ASR model acquisition
remains the separate explicit `scholion models install MODEL` path.

Pyannote telemetry is disabled by Scholion before package import. Diarization provenance
records `telemetry_enabled: false`. Recording audio remains local during inference.

Once a snapshot is resolved into Scholion's configured private model cache, inference
uses the local snapshot path.

## Dependency footprint

Diarization is intentionally a separate dependency extra because pyannote brings a
large PyTorch-based stack:

```bash
uv sync --locked --extra transcription --extra diarization
```

Representative CPU-only Windows/Linux/macOS installation size, peak RAM, and sustained
real-time factor still need physical-device qualification before Scholion should call
this a comfortable feature for an 8 GB machine.

## The evidence model

The primary diarization artifact is a source-relative speaker-turn timeline:

```text
00:00.0 ─ 00:12.4  speaker-01
00:12.4 ─ 00:18.8  speaker-02
00:18.1 ─ 00:20.0  speaker-01   # overlap can exist
```

Overlap is real evidence, not an error condition.

Raw backend labels are not stable API. Scholion sorts turns deterministically and maps
them to `speaker-01`, `speaker-02`, and so on in first-seen timeline order.

The current canonical transcript schema keeps optional diarization fields in the same
structural contract rather than inventing a new schema version for each combination of
features.

## Why Scholion is conservative about putting a speaker name on text

ASR and diarization still come from independent evidence streams. Word-level timing
simply gives Scholion finer coordinates for reconciling them.

When native word timing exists, Scholion compares **each word interval** with the
speaker-turn timeline:

```text
word overlaps speaker-01 only
    → word.speaker_ref = speaker-01

word overlaps speaker-01 + speaker-02
    → word.speaker_ref = null

all words in one ASR segment resolve to speaker-01
    → segment.speaker_ref = speaker-01

words in one ASR segment resolve to speaker-01 → speaker-02
    → segment.speaker_ref = null
```

If word evidence is absent, Scholion preserves the older conservative whole-segment
rule: the segment gets a speaker only when exactly one unique diarized speaker overlaps
that segment.

The exact speaker-turn timeline is preserved either way.

That refusal matters. It is better to preserve “we know these voices overlap here” than
to confidently put the wrong speaker label in front of a sentence.

See [word-level timestamp alignment](word-alignment.md) for the timing, checkpoint, and
source-relative assembly contract.

## What alignment now unlocks ✨

Word timing lets Scholion stop treating a long ASR segment as the smallest practical
text coordinate.

The first payoff is already structural: a speaker handoff can be represented inside one
recognized segment without assigning the entire segment to either person.

The same evidence seam can support:

- precise transcript highlighting;
- more exact jump-to-audio behavior;
- durable annotations anchored to smaller evidence spans;
- clearer overlap presentation; and
- user-authored names over anonymous speaker evidence.

Alignment does **not** solve simultaneous speech. If two active speakers overlap the same
word interval, the word remains unattributed. Later source separation may provide more
evidence, but Scholion does not manufacture certainty in the meantime.

## User-assigned display labels without biometric identity

Scholion now lets the user say:

```text
speaker-01 → Dr. Chen
speaker-02 → Interviewer
```

through the local transcript library:

```bash
scholion library speakers list TRANSCRIPT_ID
scholion library speakers name TRANSCRIPT_ID speaker-01 "Dr. Chen"
scholion library speakers forget-name TRANSCRIPT_ID speaker-01
```

The design rule is that this is **display/user-authored state**, not a rewrite of the
underlying anonymous diarization evidence.

![User-assigned display labels without biometric identity diagram](../diagrams/generated/speaker-display-labels.svg)

[Diagram source (Mermaid)](../diagrams/src/speaker-display-labels.mmd)

The label is meaningful user knowledge and does **not** share the deletion semantics of
a rebuildable search index. It is written to private user state separately from lexical
and semantic indexes.

A label is bound to the transcript ID, exact canonical transcript SHA-256, and anonymous
speaker reference. If the canonical transcript changes, the old label is retained as
user-authored state but is treated as stale and is not silently applied to the new
speaker generation.

Before accepting a new label, Scholion verifies that the current canonical bytes still
match the hash recorded in the library and that the anonymous speaker actually appears
in canonical evidence. Both segment-level refs and aligned word-level refs count, so a
speaker involved only in a mixed-speaker handoff remains nameable.

Scholion can therefore stay anonymous-by-default while still letting a researcher make
their own recording understandable.

See [Give the anonymous speakers names](../speaker-names.md) for the human-facing guide.

## Better overlap handling before source separation

Overlap still deserves two distinct product steps.

First, Scholion improves **representation and presentation** using finer word timing,
explicit multi-speaker turn evidence, user-controlled display labels, and UI/export
behavior that does not force one speaker when multiple voices are active.

Only later should Scholion consider **speech/source separation**, where the audio itself
is decomposed into estimated sources before or during recognition.

Source separation is materially heavier. It adds compute, model/dependency custody,
quality uncertainty, and new provenance questions. It should be justified by real
recordings after the simpler evidence model is strong.

🧜‍♀️ Deep technical water is permitted. Inventing confidence is not.

## Canonical and derived output behavior

When every aligned word in a segment resolves to one anonymous speaker, the segment can
retain that same `speaker_ref` as a convenience label and derived TXT/SRT/WebVTT views
may prefix it.

Mixed or ambiguous segments remain unlabeled at the segment level even when some words
have useful speaker evidence. Export rendering never changes timestamps or becomes
canonical custody.

User-assigned display labels remain a presentation layer over stable anonymous speaker
references and durable transcript coordinates. The current naming commands do not bake
the human label into canonical JSON or derived transcript exports.

## Qualification boundary

The deterministic test surface covers:

- adapter/cache-only versus download policy;
- telemetry-disable behavior;
- deterministic anonymous-label normalization;
- canonical schema integration;
- executor integration;
- conservative word/segment speaker projection;
- mixed-speaker handoffs and ambiguous word overlap;
- durable user display-label binding to exact canonical hashes;
- word-only speaker discovery for mixed handoffs;
- stale-generation isolation and corrupted-state rejection;
- derived exports; and
- the fail-closed Lightning security gate.

The locked diarization dependency graph remains in normal/scheduled vulnerability
auditing.

A clean-wheel distribution lane imports the real pyannote/PyTorch runtime without
executing the gated model. The dependency security hold is lifted for locked Lightning
2.6.6+, and PR #183 added the separate real-model proof: authenticated Community-1 model
acquisition, pinned two-speaker/overlap ground truth, real inference, and a second
cache-only inference with model download disabled. That lane remains manual and
credential-gated because Community-1 acquisition requires authenticated Hugging Face
access; routine pull requests continue to use deterministic and clean-install coverage
without exposing the repository secret.

## Current deliberate limits

This capability does not currently provide:

- biometric speaker identification;
- cross-recording speaker linking;
- automatic inference of a human speaker's real name;
- a guarantee that engine word timing or diarization is always correct;
- polished overlap presentation;
- display labels baked into canonical or derived transcript artifacts;
- simultaneous-speaker/source separation; or
- a claim that the dependency footprint is suitable for every low-memory device.

The stable rule is:

> **Preserve speaker evidence first. Add convenience only when it does not fabricate
> certainty.**
