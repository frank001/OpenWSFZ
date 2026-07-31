# 20m (originally 80m) — no ANOVA report possible

**This is not an ANOVA report.** `qa/endurance/endurance_anova.py` was not run for this
instance because it cannot be: the script hard-fails (`[ERROR] no WAV files found`, exit code 2)
the moment `--wav-dir` contains zero `.wav` files, and this instance's `--wav-dir` candidates —
both `owsfz/wav/` (`cycleAudioArchive` was `off`) and `wsjt-x/wav/` (no WSJT-X GUI ever covered
this instance's audio) — are empty. See
`artefacts/20260728_live_run_2354-8081/contents.md` for the full account of why no audio exists
for this instance, and `memory/hk020-verify-run-goal-and-critical-config-before-arming.md` for
the process failure that let it happen.

## On "the band change this morning" specifically

Worth being precise about what that band change does and doesn't affect here, since it was raised
as a reason this might "need some work": `endurance_anova.py` operates entirely in the audio
domain — it re-decodes whatever WAV files it's given via `jt9` and matches the results against
`ALL.TXT` by cycle timestamp and message text. It has **no notion of dial frequency, band, or RF
context anywhere in its code** (checked directly — no `config.json` read, no frequency field used
in matching, statistics, or report generation). A mid-session band change would not have required
any script modification to handle correctly, *if* audio had been archived through the change —
jt9 decodes baseband audio the same way regardless of what the operator calls the band.

The actual, sole blocker is the complete absence of archived audio for this instance, for the
entire session — a config gap (`cycleAudioArchive: off` on both instances, WSJT-X only ever
covering the 40m instance), not a script limitation. No amount of band-change-awareness in
`endurance_anova.py` would produce a report here, because there is no audio to re-decode, from
before, during, or after the retune.

## What does exist for this instance

`owsfz/ALL.TXT` (20,254 lines, `artefacts/20260728_live_run_2354-8081/owsfz/ALL.TXT`) — OpenWSFZ's
own decode log, text only. This could support a decode-count/SNR-over-time description using only
OpenWSFZ's self-reported values (no independent jt9 cross-check, no matched-pair ANOVA), and any
such analysis **must** split its treatment at 2026-07-29T10:04Z (the live retune from 80m/3.573 MHz
to 20m/14.074 MHz) rather than treating the whole session as one band — unlike the audio-domain
ANOVA, a same-instance decode-count/SNR trend genuinely would conflate two different real bands if
analysed as a single continuous series. Not attempted here; flagging it as the one place "the band
change" is a real analytical concern, in case this text-only angle is wanted separately.
