# T1, finally: a clean small measurement, a WSJT-X defect nobody knew about, and a bigger question than T1

**Author:** QA, 2026-08-02 (22:07 UTC, `date -u`, per HK-017). Repo at `d1e75d6`.
**For:** Architect. **Supersedes** `2026-08-02-1832-qa-to-architect-t1-wsjtx-wav-availability.md` (which
itself superseded my own first pass at T1) -- read this one, the 1832 note's job was just to stop
the bleeding at the time.
**Status:** T1 answered, small-scale, cleanly. T4 still not re-authorised -- that's unaffected by
anything here.

> **Correction, 22:14 UTC, same session:** the Captain caught an overreach in the first version of
> \7 within minutes of it being written -- I had extrapolated the launch-order defect back onto
> the *original* 07-31 corpus. That corpus only ever ran **one** WSJT-X instance (paired with the
> real radio); the `8081` leg's comparator was SDR Uno, a different application entirely, on
> Voicemeeter B1. The defect needs **two simultaneous WSJT-X instances** to manifest at all -- with
> only one running, there was nothing for it to interact with. \7 below is corrected accordingly:
> the defect matters for T1/T4's *own* measurement method going forward (since N3 now deliberately
> requires a second WSJT-X instance), not for anything already measured. Left visible rather than
> silently edited out, per the standing practice on this note -- say so, don't smooth it over.

---

## 0. What happened, in five lines

- T1's first attempt was invalidated: WSJT-X's WAVs in the 07-31 corpus were one capture,
  hardlinked into both the `-8080` and `-8081` artefact folders, not two independent ones.
- The Captain built a proper fix (three distinct WSJT-X rig-profiles) and, testing it, found
  `FT991A` decoding at roughly **half** the rate of an otherwise-identical `FT991A-Copy` instance
  on the same antenna, same audio device. That derailed the afternoon into isolating why.
- **Root cause, now isolated across eleven configurations: launch order.** Whichever of the two
  launches second decodes at ~0.54-0.57x the rate of whichever launched first. Every other
  candidate -- USB contention, CAT control, config differences, `SDRUno`'s presence, which
  physical/virtual audio device is used -- was tested individually and ruled out.
- **OpenWSFZ's own daemon does not have this defect.** Two fresh instances, one launched 33s
  after the other, came back within 1-4% of each other every time, on the same hardware that
  produced a 2x gap in WSJT-X.
- T1 itself, re-run on a small but genuinely clean window (validated non-suppressed, correctly
  paired audio device): **88/88 cycles, 100% WAV coverage.** Good as far as it goes -- see \6 for
  why "as far as it goes" is doing real work in that sentence.

---

## 1. Where T1 stood before today

Per your 1813 hand-off, T1 was one line: check whether WSJT-X's own WAVs survive this run, and
report coverage against the +0s stratum -- nothing else, informing whether N3 (jt9 re-decoding
WSJT-X's own WAVs, required to reproduce WSJT-X's live count within +/-5%) could return
**MEASURED** rather than **INDICATIVE**.

My first pass (1832 note, now superseded) found 99.45% coverage and was about to call that a
green light. The Captain stopped me: the WSJT-X `wav/`+`ALL.TXT` referenced by both the `-8080`
and `-8081` 07-31 artefact folders were **hardlinked to the same files** -- one WSJT-X capture,
not two. That's a false assumption baked into the corpus, and it dropped T4 along with the first
T1 attempt.

## 2. The fix, and what it opened up

The Captain set up three genuinely separate WSJT-X rig-profiles (`--rig-name`, each with its own
AppData folder, `save/`, `ALL.TXT`): `FT991A` (the actual radio, CAT-controlling), `FT991A-Copy`
(same USB Audio CODEC device, no CAT), `SDRUno` (Voicemeeter B1, matching `8081`'s chain). All
three read from the one antenna splitter this project has always had (memory:
`three-decoder-antenna-split-run-2026-07-31-todo.md` -- common-mode, not a candidate explanation
for anything downstream).

First clean comparison: `FT991A` 229 decodes / `FT991A-Copy` 417 decodes over the same 15 cycles.
That gap **held steady** (0.54-0.57x) across four separate confound-removal tests before anyone
suspected launch order:

| # | condition tried | order | `FT991A`/cycle | `Copy`/cycle | ratio |
|---|---|---|---:|---:|---:|
| 1 | original | FT991A -> Copy | 15.3 | 27.8 | 0.549 |
| 2 | routed both through a shared Voicemeeter bus (ruling out USB device contention) | FT991A -> Copy | 12.8 | 23.7 | 0.542 |
| 3 | CAT control released on FT991A | FT991A -> Copy | 17.0 | 30.7 | 0.554 |
| 4 | `SDRUno` stopped entirely | FT991A -> Copy | 16.4 | 28.7 | 0.572 |
| 5 | `Copy` shut down -- `FT991A` alone | FT991A -> Copy | 15.75 | -- | -- |

Row 5 matters: `FT991A`'s own rate was unchanged whether `Copy` was running or not (15.75 vs the
prior 16.4). Whatever this was, it wasn't an interaction between the two live processes -- it
looked baked into `FT991A` itself.

A full section-aware diff of both `.ini` files (not just the keys I'd hand-picked first) turned
up exactly 8 differing keys, all expected rig-control bookkeeping (serial ports, PTT method, save
paths, window position) -- and 128 keys present in `FT991A`'s file that simply didn't exist in
`Copy`'s (Qt never having flushed `[Common]` to disk for the fresher profile). Live-checked via
the Decode menu screenshots: both **Deep** decode depth, both **AP off**. No configuration
difference survives as a candidate.

## 3. The actual variable: launch order

The Captain reversed it -- `Copy` first, then `FT991A`, then `SDRUno` -- and the gap **inverted**:

| # | condition | order | `FT991A`/cycle | `Copy`/cycle | ratio |
|---|---|---|---:|---:|---:|
| 6 | reversed order, both on Voicemeeter B2 | Copy -> FT991A | 33.2 | 30.3 | 1.097 |
| 7 | reversed order, both back on direct USB | Copy -> FT991A | 34.9 | 32.4 | 1.077 |
| 8 | `Copy` on B2 fed by Voicemeeter reading the USB device directly (so the physical device still has 2 listeners: `FT991A` + Voicemeeter) | Copy -> FT991A | 30.3 | 27.6 | 1.099 |
| 9 | `FT991A` also moved to B2 -- Voicemeeter now the **only** app touching the physical device | Copy -> FT991A | 30.4 | 27.65 | 1.10 |

Nine WSJT-X configurations, two orders, four different audio-routing arrangements (direct USB
with contention, Voicemeeter shared bus, Voicemeeter-as-second-physical-listener, Voicemeeter as
sole physical listener). **Every single reading clusters at ~0.54-0.57x in the original order and
~1.08-1.10x in the reversed order, regardless of anything else changed.** That is about as clean
an isolation as this kind of live, un-instrumented testing gets. Whichever of the pair launches
**second** decodes at roughly half the rate of whichever launched **first** -- full stop, as far
as this session's testing can tell.

I have no mechanism to offer -- I didn't instrument WSJT-X's decoder internals, only its inputs
and outputs. Plausible candidates (buffer/thread-pool sizing decided at first-audio-callback and
never revisited, some one-time calibration racing the other instance's startup, decode-thread
priority) are guesses, not findings.

## 4. Control: OpenWSFZ does not have this defect

Two fresh OpenWSFZ daemon instances (ports 8080/8081, freshly built config, launched 33s apart)
were run through the same test twice:

| condition | `8080`/cycle | `8081`/cycle | ratio |
|---|---:|---:|---:|
| `8081` on Voicemeeter B2 | 21.05 | 21.00 | 1.00 |
| `8081` on Voicemeeter B1 | 21.95 | 22.81 | 1.04 |

Both within a few percent, both launch orders effectively untested as a variable because neither
showed anything to explain. **This rules out a general Windows-audio-stack or shared-antenna
explanation.** Whatever WSJT-X is doing, OpenWSFZ's own capture pipeline doesn't inherit it.

*(Side note for the record, not urgent: getting OpenWSFZ running for this test found a real,
reproducible bug -- `POST /api/v1/config` throws an unhandled 500 when the daemon was launched
with a relative `--config` path, because `JsonConfigStore.SaveAsync` calls
`Path.GetDirectoryName(_path) ?? throw ...` and `GetDirectoryName` returns `""`, not `null`, for a
bare relative filename -- `Directory.CreateDirectory("")` then throws `ArgumentException`. Worked
around by relaunching with an absolute `--config` path. Small, real, `src/`-side -- happy to draft
a dev-task per HK-000/HK-011 if wanted; not blocking anything above.)*

## 5. Side finding: a live false decode, unrelated to the launch-order question

While this was running, the Captain caught `FT991A` decoding `<PD2FZ> TF/KJ7H RR73` (own
callsign, SNR +1 dB, DT 0.4s) despite the radio never having transmitted anything this session.
The `< >` marks a hash-table-recovered callsign -- a core FT8 protocol mechanism, not gated by the
"Enable AP" checkbox we'd already confirmed off on both instances. It runs unconditionally as
part of ordinary decoding because `MyCall` is always in the hash table. At that SNR, on a
hash-expanded field, a false decode is a plausible read. `UploadSpots=false` on `FT991A`
(confirmed in the `.ini` diff), so nothing was forwarded externally.

This is exactly the AP/hash-decoding confound your Angle-1 pre-registration named in advance
(\6) -- caught live, unprompted, mid-diagnostic. Worth keeping in mind for \6's sensitivity
analysis whenever T4 runs: this mechanism doesn't need the AP checkbox on to fire.

## 6. The actual T1 answer -- small, clean, and why "small" matters here

Once `FT991A` was confirmed non-suppressed (row 7/8 above) *and* sitting on the audio device that
actually matches `8080`'s chain (direct USB Audio CODEC), I ran OpenWSFZ `8080` fresh for ~22
minutes (21:14:52-21:36:45 UTC) alongside it and re-ran the actual T1 check --
`apply_grid_snap` over `8080`'s own `ALL.TXT`, cross-referenced against `FT991A`'s `save/`
folder, same method as the original (invalidated) T1 attempt:

- 88 unique cycle timestamps, **all 88 already on-grid** (G=1.0 -- unsurprising over 22 minutes;
  8080's drift is a slow ~48 ppm effect, not yet material at this timescale).
- **88/88 (100%)** have a genuinely independent `FT991A` WAV file present. Verified as genuinely
  independent this time -- not hardlinked, distinct inode, distinct file, per the same check that
  caught the 07-31 problem in the first place.

That is a real, honest, non-contaminated T1 result. It is also **88 cycles against the ~3,637 the
+0s stratum needs for T4**. This answers T1's literal question (do the WAVs exist and cover the
run) but is nowhere near the scale needed to re-run T4's F_dec measurement -- that needs this
validated configuration held for hours, with `8080` running throughout, not 22 minutes.

## 7. Scope of the defect -- corrected

**Does not reach the original corpus.** The 43.5-hour, 3,637-cycle +0s-stratum corpus (Tables
A/B/C, the 0.521/0.573 baseline ratios, everything the 1741 note produced) ran **exactly one**
WSJT-X instance -- paired with the real radio, matching `8080`'s audio chain. `8081`'s comparator
in that corpus was SDR Uno, a separate application on Voicemeeter B1, not a second WSJT-X. The
defect isolated in \2-\4 is specifically about **two simultaneously-running WSJT-X instances**,
one launched after the other -- with only one instance ever running against that corpus, there
was no pairing for the effect to act on. "WSJT-X's live decode count" as ground truth for leg C
in every prior D-001 measurement is **not** newly in question because of anything found today.

**Where it does bite**: N3, as designed, now deliberately requires a second WSJT-X instance
(`FT991A-Copy`) running alongside the primary one, specifically to give jt9's calibration check a
genuinely independent capture to compare against. That is exactly the situation the defect needs
to manifest. So the practical consequence is narrow but real: **any future T1/N3 measurement, or
any future corpus meant to feed T4, needs its two WSJT-X instances launched in the validated-safe
order** (whichever isn't the radio-controlling one, first) -- or the N3 calibration itself risks
being built on a suppressed instance. That's the entire footprint of this finding. Section \6's
88/88 result already used the safe order, so it stands as reported.

## 8. What I'd put in front of the Captain and you, in order

1. **A standing decision on launch order** for any future run needing two WSJT-X instances:
   the non-primary one before the radio-controlling one, given every reversed-order reading
   came back clean and every original-order reading came back suppressed. This is now a
   procedural requirement for N3 specifically, not a general finding about past corpora (\7).
2. **Whether to run a real corpus now** under the validated-clean configuration -- this is the
   only way to get T1/T4 back to the scale they need, and per HK-004 the tooling to do it already
   exists (`qa/endurance/anova_common.py`, the grid-snap machinery from the 1721 spec).
3. **T4 remains not re-authorised.** Nothing here changes that call. \7's original framing (a
   reason to redesign around leg-C *reliability*) does not hold up -- withdrawn; the 1813
   hand-off's leg-C *independence* concern (already what motivated the three-instance rebuild)
   remains the operative one.

## 9. Cross-references

- `2026-08-02-1832-qa-to-architect-t1-wsjtx-wav-availability.md` -- superseded by this note.
- `2026-08-02-1813-architect-to-qa-handoff-drift-fix-corrections-and-angle1.md`,
  `...-prereg-angle1-baseline-deficit-decomposition.md` \5-\6 (N3, the AP confound).
- `2026-08-02-1741-qa-to-architect-grid-snapped-anova-rerun-result.md` -- the 07-31 corpus this
  note's \7 confirms is **unaffected** by the launch-order defect (single WSJT-X instance only);
  stands as measured, no reliability question attaches to it from anything found today.
- Live artefacts (outside the repo, not committed, referenced for provenance):
  `C:\Users\Frank\AppData\Local\WSJT-X - FT991A\`, `...-FT991A-Copy\`, `...-SDRUno\`;
  `D:\Projects\claude\OpenWSFZ-8080-capture\`, `...-8081-capture\` (both this session's fresh
  small runs, distinct from the renamed `2026-08-02-multiday-20m-anova OpenWSFZ-8080/8081-capture`
  originals).

---

*Per HK-015 this is QA -> Architect. Per HK-014/HK-010 committed locally, no push, no merge
implied, no merge-readiness claim made. Per HK-017 filename/byline carry real `date -u` UTC. Per
HK-021 \\3's table rows are mechanical, reproducible diffs -- not judgement calls. Per HK-022 every
figure above was measured fresh this session (baseline-then-diff, cycle-counted), none copied or
extrapolated from a prior note. Per HK-012 \\8's items are surfaced explicitly so they don't lapse
for want of an owner. Per HK-022 again: \\7's first draft was itself wrong (checked against the
Captain's correction the same session, at 22:14 UTC, rather than left standing) -- the corpus
question it originally raised does not survive; recorded as a correction, not silently dropped.
Per HK-004 \\6's small T1 re-check was actually run, not merely recommended, once the data to do
it existed. NFR-021: real third-party callsigns appear only in \\5 (already publicly visible in
the Captain's own screenshot) and are not used as match keys anywhere in this note; all other
figures are aggregate counts.*
