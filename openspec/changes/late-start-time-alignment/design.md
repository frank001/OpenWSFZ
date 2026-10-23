## Context

`origin/main` `85fbaadc`. `Ft8TimeHelper.ClampSampleCountToWindowBoundary` (`Ft8TimeHelper.cs:46-59`) keeps the leading samples and cuts the tail at the 15 s boundary; it is called from `QsoAnswererService.TransmitAsync` (`:1614`, the call at `:1627`) and `QsoCallerService.TransmitAsync` (`:1321`). The manual-engage fire sites fire at any lateness: `QsoAnswererService.cs:783-801` (pending target), `:715-730` (jump-in), `QsoCallerService.cs:777-784` (pending responder); `AnswerCqAsync`/`TryEngageExternal` arm a pending target and push a wake-up batch (`ArmPendingTarget`, `:454-476`) so the loop fires "within the current cycle window".

## Decisions

1. **One helper, both services.** A new `Ft8TimeHelper` function takes `now`, the buffer length and the sample rate and returns the number of samples to skip and to load (and an "do not key" result). The services call it where they call the clamp today. (R1.)
2. **t is read once.** `t` is `now - windowStart` at the moment `TransmitAsync` is about to load audio, using `_timeProvider.GetUtcNow()` (as `TransmitAsync` already does at `:1627-1628`). Never `DateTimeOffset.UtcNow`: the fire sites and `ArmPendingTarget` still use `UtcNow` for arming and for the 60 s expiry (`:466`, `:764`), which is fine, but the new offset check at the fire sites must use `_timeProvider` so the tests can inject time (QA amendment M3). The existing test-only arming helpers (`:482-500`) are used for T6 and T7.
3. **Audio really starts a little later than t** (QA amendment M2): PTT KeyDown, `ptt.leadTimeMs` and the output device's latency add about 0.05 to 0.3 s. The skip is computed from t at load, which is harmless for DT (the receiver's window is +-2.48 s). At the 2.36 s edge the full clip can end that much past the boundary, so the retained clamp can still fire there; it stays as the safety net, and the R3 log line records the t that was used. The rule is not "the clamp never fires".
4. **The fire-site cut-off (R2).** At each of the three fire sites, after the phase check passes, if t >= 11.25 s the target is retained (return without clearing) and the next correct-phase batch re-evaluates it. A manual engage past 11.25 s therefore transmits about 18.75 s later.
5. **R3 log line** at every late start (t > 2.36 s): offset, samples skipped, samples loaded, in milliseconds, at Information, written at the moment the skip is computed. A "not keyed at t >= 11.25 s" decision is also Information (today the zero-remaining skip is Debug).
6. **Requirement titles are kept** in the OpenSpec delta ("Manual engage fires unconditionally within a correct-phase window" and "Transmission never keys past the current window's boundary") so the MODIFIED blocks match the main spec; the new body text carries the 11.25 s cut-off. A later cleanup may rename them.
7. **Open question for the Architect (QA amendment M4), not blocking:** the skipped start begins mid-symbol with no ramp, so the key goes down with a tone already at full amplitude: a key-click risk. Today's tail truncation already ends without a ramp. If a short raised-cosine ramp-in is wanted, T2 to T4's "first loaded sample equals the input sample at N" must be reworded. Until the Architect decides, the Developer implements NO ramp and says so in the commit.

## Risks

- **A manual engage past 11.25 s waits about 19 s** with no feedback in the UI; that is the chosen behaviour.
- **Retries and continuations use the same `TransmitAsync`**, so they are aligned too when late; the existing retry-budget tests must stay green.
- **WSJT-X source read was master, not the 2.7.0 tag**; the 0.75 and the 500 ms are as found there.
