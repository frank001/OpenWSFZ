# Decode config comparison — WSJT-X vs OpenWSFZ, passband and threshold settings

**Author:** QA, 2026-08-06 (19:33 UTC, `date -u`, per HK-017). Repo `main` at `f6c5b46`.
**Requested by:** the Captain, 2026-08-06 — "check whether WSJT-X's own passband/threshold
settings differ from ours."
**Follows on from:** `2026-08-06-1920-qa-wav-content-comparison-1713.md`, which found the raw
audio content matches closely in-band and ruled out a level/frequency-response explanation
for the standing 29.9%-agreement anomaly. This note checks the other candidate the Architect
flagged: **decoder configuration**, not captured audio.

---

## 1. OpenWSFZ's own settings — solid, both parts verified from source/artefact

**Frequency search passband: hardcoded, not configurable.**
`src/OpenWSFZ.Ft8/Native/ft8_shim.c:1183` — `monitor_config_t cfg = { .f_min = 200.0f,
.f_max = 3000.0f, ... }`. Every OpenWSFZ decode, every run, searches exactly 200–3000 Hz.
There is no setting anywhere in `AppConfig`/`DecoderConfig`/the web UI that changes this — it
is baked into the native shim.

**Tunable decode parameters, as actually used for the `20260803_live_run_1713` corpus** (from
that run's own `contents.md`, captured live at gather time, not reconstructed):

| parameter | value used | valid range | default |
|---|---:|---:|---:|
| `kMinScorePass2` (pass-1 candidate score floor) | 10 | [5, 30] | 10 |
| `osdCorrThreshold` (OSD normalised correlation gate) | 0.10 | [0.05, 0.40] | 0.10 |
| `osdNhardMax` (OSD max Hamming-distance gate) | 60 | [30, 100] | 60 |

All three sit exactly at their documented defaults (`src/OpenWSFZ.Ft8/Interop/Ft8LibInterop.cs:600-602`,
`src/OpenWSFZ.Abstractions/DecoderConfig.cs:34-36`) — **no non-default tuning was in play for
this corpus.**

## 2. WSJT-X's settings — read from the live machine, ⚠️ NOT verified against the capture date

WSJT-X ships no equivalent artefact-gathering step (HK-016 only gathers our own logs/WAVs/
`ALL.TXT`), so there is no record of its settings *at the time of the 08-03 capture* anywhere
in this repo. The only source available is this machine's live `WSJT-X.ini`
(`C:\Users\Frank\AppData\Local\WSJT-X\WSJT-X.ini`), read under the `[FT991A]` profile
(`CurrentName=FT991A`, matching the `Microphone (2- USB Audio CODEC)` device the 08-03 run's
`contents.md` records):

| key | value | what it is |
|---|---:|---|
| `NDepth` | 3 | Decode-menu depth radio button — the top of its 1–3 range |
| `FT8AP` | false | AP (a priori) decoding off |
| `Ftol` | 50 | frequency search tolerance, Hz |
| `DTtol` | 3.0 | time-offset tolerance, seconds (decoded from the Qt `@Variant` float encoding) |
| `RxBandwidth` | 2500 | Hz — semantics uncertain, see §3 |
| `MultithreadedFT8decoder` | false | |
| `reduceFalseDecodes` | false | |
| `SpecialOpActivity` | false | |

**This table is today's snapshot, not history.** Checked directly: `wsjtx.exe` (PID 12024) and
its `jt9` decoder subprocess (PID 1112) are running *right now*, both started 21:27 local time
this evening — minutes before this file was written — and the `.ini`'s last-write timestamp
matches. Qt writes this file from whatever the live UI state is; nothing here is pinned to
2026-08-03. **I cannot certify these are the values that were active for the corpus** — only
that they are what the FT991A profile holds today, unless the Captain confirms nothing was
changed in the intervening three days.

## 3. What this does and does not establish

- **Passband is a wash as an explanation.** Neither side's audio content analysis (previous
  note) nor this config check gives a reason to suspect a passband mismatch: OpenWSFZ's is
  hardcoded 200–3000 Hz; WSJT-X's `RxBandwidth=2500` is very plausibly the same order of
  magnitude, but I don't have WSJT-X source in this repo to confirm whether that key gates the
  *decoder's* candidate search the way OpenWSFZ's `f_min`/`f_max` does, or is a CAT/rig-filter
  setting passed to the transceiver instead — genuinely uncertain, not something I'll assert
  either way.
- **One real, if unverified-historically, asymmetry:** WSJT-X's `NDepth=3` is its most
  exhaustive decode-depth setting, while OpenWSFZ's three tunables all sit at their
  least-aggressive documented defaults for this corpus. The two controls aren't on the same
  axis (WSJT-X's is a single depth dial; OpenWSFZ's are three independent gates), so "WSJT-X is
  tuned harder" is not a safe conclusion from this alone — but it is the one config difference
  on record worth someone's attention, **conditional on confirming it was also true on
  2026-08-03.**
- **Does not resolve the 29.9%-agreement TODO.** It narrows the field further alongside the
  audio-content note: no smoking gun in either the captured signal or the settings actually on
  record for OpenWSFZ. What remains unchecked: WSJT-X's actual depth/AP/passband *as of the
  capture*, and anything about its internal candidate search this repo has no visibility into.

## 4. Open question for the Captain — answered

**The Captain confirmed, 2026-08-06 (in conversation, immediately following this note's first
draft): WSJT-X's settings have not been touched since the 3rd — "same as before, Deep and AP
disabled."** That resolves both the stability question and the one label I'd hedged on: `NDepth=3`
is WSJT-X's **"Deep"** setting (not "Deepest" — I had no source-level confirmation of the label
mapping and flagged it as uncertain; the Captain's own terminology settles it). §2's table can
now be cited as the settings that were live during the `20260803_live_run_1713` capture, on the
Captain's word rather than a written artefact from that date — worth noting as the evidentiary
basis if this is cited further downstream.

**Revised §3 reading, with this now settled:** WSJT-X ran FT8 decoding at its **Deep** depth
setting, AP off, for the corpus. OpenWSFZ ran with all three of its tunables at documented
default. Both are their respective "no special tuning" states, not one side pushed harder than
the other — softens the §3 asymmetry flag considerably. The remaining open items stand as
written: whether `RxBandwidth=2500` gates WSJT-X's decode search window the way OpenWSFZ's fixed
`f_min`/`f_max` does is still unconfirmed, and the 29.9%-agreement TODO is still unresolved by
either this note or the audio-content one.

## 6. Correction, 2026-08-06 20:07 UTC — wrong `.ini` file cited

While setting up the live cross-decode replay (separate session, same evening), it turned out
the running WSJT-X instance is launched `--rig-name=FT991A`, which per WSJT-X's multi-instance
convention uses its **own separate AppData directory**:
`C:\Users\Frank\AppData\Local\WSJT-X - FT991A\WSJT-X - FT991A.ini`. §2 above instead read
`C:\Users\Frank\AppData\Local\WSJT-X\WSJT-X.ini` — the plain, default-profile directory, which
turned out to be untouched since 2026-08-02 (confirmed by its `ALL.TXT`'s stale mtime) and is
not what any live session this week has actually been using.

**The numbers in §2's table are, by coincidence, unaffected** — `NDepth=3`, `Ftol=50`,
`DTtol=3.0`, `FT8AP=false`, `JT65AP=false`, `RxBandwidth=2500`, `SpecialOpActivity=false` are
identical in the correct file. Two keys I'd listed (`MultithreadedFT8decoder`,
`reduceFalseDecodes`) are **absent entirely** from the correct file rather than present and
`false` — likely never explicitly written because they've never been toggled off their
compiled-in default, not a substantive difference, but stated precisely rather than carried
over from the wrong source.

**Lesson, not just a fix:** I read a plausible-looking file that happened to exist and matched
the docs I expected, without checking whether it was the one the *running* process actually
uses. The multi-instance convention (separate AppData dir per `--rig-name`) was already on
record from the 2026-08-02 launch-order investigation
(`2026-08-02-2207-qa-to-architect-wsjtx-launch-order-defect-and-t1-result.md`) — I didn't
connect it here on the first pass. Any future reference to this machine's WSJT-X config should
resolve the actual running command line first (`Get-CimInstance Win32_Process -Filter
"Name='wsjtx.exe'"` → `CommandLine`) rather than assume the default `WSJT-X\` directory.

## 5. Cross-references

- `qa/cycleframer-alignment-replay/2026-08-06-1920-qa-wav-content-comparison-1713.md` — the
  audio-content half of this same question.
- `artefacts/20260803_live_run_1713/contents.md` — OpenWSFZ's settings, captured live for that
  run.
- `src/OpenWSFZ.Ft8/Native/ft8_shim.c:1183`, `Ft8LibInterop.cs:600-602`,
  `DecoderConfig.cs:34-36` — the hardcoded passband and the tunables' defaults/ranges.
- `qa/cycleframer-alignment-replay/2026-08-05-1459-architect-to-qa-spec-reciprocal-density-asymmetry.md`
  §6 — the "may indicate something wrong with one leg's configuration" flag this answers part of.
