# Developer handoff: correct the D6 comment's false "L = −R" claim in `WasapiAudioSource.cs`

**Authored by:** QA (per HK-000/HK-015). **Status:** ready for a Developer session.
**Source:** ruling S7.4.3 (`qa/cycleframer-alignment-replay/2026-07-30-2253-architect-ruling-
cross-band-density-law-and-capture-chain.md`), accepting QA rec 4
(`2026-07-30-2221-qa-to-architect-capture-chain-and-cross-band-findings.md` §4/§5 rec 4).
**Priority:** low. Currently harmless — see §2.

---

## 1. What is wrong

`src/OpenWSFZ.Audio/WasapiAudioSource.cs` lines 121-125 (and the fuller comment at line 331-336)
assert:

```csharp
// D6: LeftChannelSampleProvider replaces StereoToMonoSampleProvider.
// StereoToMonoSampleProvider averages (L + R) / 2 — when the device
// delivers a differential (balanced) signal (L = −R), every output
// sample is zero regardless of signal amplitude. Extracting the left
// channel alone carries the full signal without phase cancellation.
```

This was measured directly on 2026-07-30 and is **false on current hardware**
(`Microphone (2- USB Audio CODEC)`):

```
corr(L, R) = 1.000000
RMS(L - R) = 0.000000000
```

L and R are **sample-for-sample identical**, not differential. Measured with a standalone,
throwaway tool (`qa/audio-capture-lr-phase-check/` — not part of `OpenWSFZ.slnx`, no `src/`
dependency, dumps raw WASAPI stereo PCM with zero processing: no channel extraction, no
resample, no decode), capturing 8 s live off the same device with the radio connected and
receiving (`artefacts/lr_phase_check/raw_stereo.wav`, git-ignored, NFR-021).

## 2. Why this is low priority — currently harmless, but should not stay undocumented

When L = R exactly, "take the left channel" and "average L+R" produce **identical output**. There
is no live bug and no data-quality consequence from this specific step today — this also **rules
out channel-handling as a contributor** to the separately-measured ~10-13% capture-chain effect
under investigation in the same thread (Measurement B, S6 of the same ruling).

The problem is purely that the comment is now factually wrong and would mislead a future engineer
who trusts it as documentation — e.g. if hardware changes, or a new capture device is added, and
someone reasons from this comment instead of re-measuring.

## 3. What to change

**Do not simply delete the differential-signal claim.** Per the ruling's addition to QA's
original recommendation: replace it with the measurement, its date, and its method, so the next
engineer inherits a checked fact rather than re-assuming an unchecked one.

Suggested replacement text for both comment sites (lines 121-125 and 331-336 — check both are
updated consistently; the fuller one at 331 documents the type):

```csharp
// D6: LeftChannelSampleProvider replaces StereoToMonoSampleProvider.
// StereoToMonoSampleProvider averages (L + R) / 2. Extracting the left channel alone was
// originally justified by a claim that this device delivers a differential (balanced)
// signal (L = -R), which would make an averaged output zero regardless of amplitude.
//
// MEASURED 2026-07-30 on 'Microphone (2- USB Audio CODEC)' with the radio connected and
// receiving: L and R are sample-for-sample IDENTICAL, not differential --
// corr(L,R) = 1.000000, RMS(L-R) = 0.000000000 (qa/audio-capture-lr-phase-check/,
// artefacts/lr_phase_check/raw_stereo.wav). The original differential-signal claim is FALSE
// on this hardware. Left-channel extraction is harmless here (L=R makes it equivalent to
// averaging) and is kept for now, but do not rely on the differential-signal justification --
// re-measure with the standalone tool above before trusting it on any new capture device.
```

Keep the mechanism (left-channel extraction) unchanged — this is a comment-only correction, not
a behavioural change. Do not silently drop the historical context (why left-channel extraction
exists at all); future maintainers still need to know it was a deliberate choice, just not for
the reason originally stated.

## 4. Definition of done

- [ ] Both comment sites (~line 121-125, ~line 331-336) updated to state the measured fact
      instead of the unverified differential-signal claim, per §3.
- [ ] No behavioural change — `git diff` touches only comments.
- [ ] `dotnet test tests/OpenWSFZ.Audio.Tests` (or the relevant project) passes unchanged.
- [ ] `python3 tools/pre_merge_check.py` green (HK-006).
- [ ] Per HK-011: present the diff to the Captain for explicit pre-push sign-off. Per HK-010:
      merge always needs the Captain's explicit sign-off, green CI notwithstanding.

## 5. Cross-references

- `qa/cycleframer-alignment-replay/2026-07-30-2253-architect-ruling-cross-band-density-law-and-capture-chain.md`
  §7.4 item 3 — the instruction this handoff implements.
- `qa/cycleframer-alignment-replay/2026-07-30-2221-qa-to-architect-capture-chain-and-cross-band-findings.md`
  §4 — the original L/R measurement and its methodology.
- `qa/audio-capture-lr-phase-check/` — the standalone measurement tool.
- `artefacts/lr_phase_check/raw_stereo.wav` — the raw capture (git-ignored, NFR-021).
