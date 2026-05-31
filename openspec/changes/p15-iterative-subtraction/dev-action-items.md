# Developer Action Items — p15-iterative-subtraction QA Review

**Date:** 2026-05-31
**Branch:** `feat/p15-iterative-subtraction`
**Source:** QA Review (second pass)

---

## 🔴 Required Before Merge

### 1 — Fix suppression description in `specs/iterative-subtraction/spec.md`

**File:** `openspec/changes/p15-iterative-subtraction/specs/iterative-subtraction/spec.md`
**Lines:** 3–4 (the "Second-pass spectrogram-domain residual decode" requirement)

The current text says:

> *"…setting all waterfall tiles covering the signal's 79-symbol window and **all 8 FT8 tone bins**… to the noise-floor median raw byte"*

This is wrong. The implementation uses **narrow suppression**: the exact decoded tone bin (from `ft8_encode`) plus its ±1 nearest neighbours — at most 3 bins per symbol, not 8. The rationale for this choice is already in `design.md §Decision 2`.

**What to write instead** (adapt as needed):

> *"…setting the exact decoded tone bin and its ±1 nearest neighbours (to cancel Hann-window first sidelobes), as determined from `ft8_encode()`, to the noise-floor median raw byte for each of the 79 FT8 symbols across all time and frequency over-sampling sub-bins."*

---

## 🟡 Recommended (Strong — Apply Before Merge)

### 2 — Add a unit test for `GetLastPassCounts` with a silent buffer

The spec contains this scenario (in `specs/ft8lib-interop/spec.md`):

> *"WHEN `DecodeAll` is called with a silent buffer AND THEN `GetLastPassCounts(2)` is called, THEN it SHALL return `[0, 0]`."*

There is currently no automated test for this. Add one alongside the existing interop or decoder tests. It should:

1. Call `Ft8LibInterop.DecodeAll` with 180 000 zeroed samples.
2. Call `Ft8LibInterop.GetLastPassCounts(2)` on the **same thread** immediately after.
3. Assert the returned array is `[0, 0]`.

This is cheap to write and protects the TLS mechanic from future regression.

### 3 — Remove the unnecessary `(uint16_t)` cast in dedup slot calculation

**File:** `src/OpenWSFZ.Ft8/Native/ft8_shim.c`
**Line:** dedup block inside the pass loop

```c
// Current — confusing cast
int  slot = (int)(msg.hash % (uint16_t)K_MAX_DECODED);

// Replace with
int  slot = (int)(msg.hash % K_MAX_DECODED);
```

The cast is harmless (340 fits in `uint16_t`) but a future reader will wonder what it is protecting against. Remove it.

---

## ⚪ Noted — No Action Required This PR

These are on record; no work needed now.

| # | Item |
|---|---|
| N-1 | macOS `libft8.dylib` rebuild — CI will handle on push (tasks.md 4.5). |
| N-2 | Style compression in `hash_table_lookup` / `hash_table_add` — not a defect; future cleanup if desired. |
| N-3 | `MaxResults = 140` is below the two-pass ceiling of 340 — practical risk nil; tracked as prior Finding 4 for future housekeeping. |

---

## Checklist

- [x] R-1 — spec.md suppression text corrected
- [x] R-2 — `GetLastPassCounts` silent-buffer test added
- [x] R-3 — spurious `(uint16_t)` cast removed (win-x64 DLL rebuilt; linux/macOS via CI)
- [x] Re-submitted to QA

---

---

# Round 2 — QA Review (Final Pass, 2026-05-31)

**Source:** QA Review — code review findings

---

## 🔴 Required Before Merge

### R2-1 — Fix `findings.md` status text — factually wrong post-p15

**File:** `openspec/changes/p10-decoder-ground-truth/findings.md`
**Line:** 68

Despite being marked `[x]` in `qa-review.md`, this fix was **not applied**. A `git diff HEAD` on the file confirms only the timestamp changed — the status sentence was never rewritten.

**Current text (wrong):**

> *"The ~33% miss rate relative to WSJT-X is a known, accepted limitation of ft8_lib **not implementing iterative subtraction (second-pass decoder)**. This is a product-level decision **deferred to a future change**. No action required."*

After p15, iterative subtraction *has been implemented*. This sentence is factually false.

**Replace with:**

> *"Iterative signal subtraction was implemented in p15 (`p15-iterative-subtraction`) using spectrogram-domain ±1-bin narrow suppression. The remaining ~31% gap to WSJT-X is the ceiling of the spectrogram-domain approach: FFT-waterfall ±3.125 Hz frequency resolution prevents coherent PCM-domain waveform cancellation. Closing the remaining gap requires sub-Hz carrier-frequency estimation and PCM-domain waveform subtraction, scheduled as a future change."*

---

## Checklist

- [x] R2-1 — `findings.md` status text corrected to reflect p15 implementation
- [x] Re-submit to QA for final approval

Once R2-1 is done, QA will sign off and the PR may be marked ready-for-review.
