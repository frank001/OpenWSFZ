# D-001: correcting myself — the shim version must be bumped, and a bump alone is not enough

**Author:** Architect, 2026-07-27 (17:38 UTC, `date -u`, per HK-017). **For:** QA (to author), and the Captain.
**Corrects:** `2026-07-27-1731-architect-tls-gate-accepted.md` §3, which ruled "correctly not
bumped." **That ruling was wrong.** The Captain's call is right and this note replaces it.
**Disposition change: this is a pre-merge requirement, not a bundled item.**

---

## 1. What I got wrong

My 17:31 §3 argued the version should stay at 20260035 because a build-flag variant is not a shim
revision. I was answering a question nobody asked, and missed the ordinary one sitting in front of me.

**The gate changed the shipped binary's observable behaviour under an unchanged version number:**

| binary | `FT8_SHIM_VERSION` | `ft8_get_last_candidate_llr` in the **default** build |
|---|---:|---|
| shim 20260035, before the gate | 20260035 | returns **real LLR data** |
| shim 20260035, after the gate | 20260035 | returns **zeros, always** |

Same version, same default build configuration, different behaviour. That is a plain contract break,
and catching exactly this is what the version exists for — `Ft8LibInterop`'s own comment says the
bump exists "so the startup ABI check catches a stale native binary." A managed build expecting
20260035 will happily load either of these and cannot tell them apart.

I wrote that defect down in §2 of the same note — three indistinguishable states — and then ruled in
§3 that the version was fine. Those two paragraphs are adjacent and they contradict each other. The
Captain caught it from one line of summary.

**A second, smaller error:** my proposed `-1` sentinel puts discovery at the *point of use*, mid-experiment.
For a diagnostic workflow whose entire output can be silently empty, the check belongs at **load
time**. Fail fast, not fail eventually.

## 2. What I got right, and why it still constrains the fix

My original objection stands and is the reason a bump *alone* does not close this: **a version number
cannot express a build-time variant.** Bump to 20260036 and the gate-on and gate-off builds of the
new source both still report 20260036 — the same collision, one revision later.

So the correction needs both halves. Version answers "which source revision"; something else must
answer "which build variant."

## 3. The fix

1. **Bump `FT8_SHIM_VERSION` 20260035 → 20260036** (`ft8_shim.h:333`) and `ExpectedShimVersion`
   (`Ft8LibInterop.cs:246`). Justified twice over: the shipped binary's behaviour changed, and item 2
   adds an export.
2. **Add `ft8_get_shim_capabilities()`** returning a bitmask — bit 0 = raw-LLR capture compiled in,
   remaining bits reserved. Version and capabilities then stay orthogonal and both are readable at
   load time, which is the property the version alone can never have.
3. **Managed side:** read capabilities in `LoadAndVerify`, log them at startup alongside the version,
   and make `SetCandidateDiagLlrCapture(true)` **throw** when the loaded binary lacks the capability —
   at the moment the workflow asks for it, not after it has collected a cycle of zeros.
4. **Keep the `-1` sentinel** from 17:31 §2 as defence in depth, but it is now secondary to item 3.

**Scope discipline:** this is one `#define`, one small export, one managed constant and one guard.
It should not turn into a redesign of the diagnostic surface.

## 4. One more reason this matters, from `libft8.version.txt`

The version file records that **CI rebuilds the Linux `.so` and macOS `.dylib` from the current
`ft8_shim.c` on every push**, and auto-commits them. Those rebuilds do not set
`-DFT8_ENABLE_RAW_LLR_CAPTURE=1` — correct for a shipped artefact — but it means the per-platform
binaries are produced by a path that can never enable the capability, while the committed Windows DLL
is produced by hand and could be either.

**So the three platform binaries can legitimately differ in capability while all reporting the same
version.** A capability query is the only thing that can tell anyone which one they actually loaded.
This makes item 2 the load-bearing half of the fix, not the optional half.

## 5. Disposition

**Changed from 17:31.** That note bundled the defect with a named trigger ("before the next workflow
using `ft8_get_last_candidate_llr`"). That was too lax for what this turns out to be.

**This is a pre-merge requirement:** the native binaries should not merge to `main` carrying a version
number that misdescribes them. It is a separate and much smaller item than the 16:22 size blocker —
that one is genuinely cleared and I am not re-raising it — but it lands in the same place, on the same
binaries.

QA authors the dev-task; a Developer session applies it; the Captain reviews the diff before push, per
HK-011. **I am not issuing the task.**

## 6. Note to myself, on the record

Two rulings in a row where I reasoned carefully about the interesting question and missed the plain
one — R.3's cap axis (already answered by C.1) and now this. Both were caught by someone else looking
at a summary rather than by me looking at the material. That is worth naming as a pattern rather than
logging as two incidents: I am reliably over-weighting the novel part of a problem and under-checking
the ordinary part.

## 7. Cross-references

- `2026-07-27-1731-architect-tls-gate-accepted.md` §3 — **withdrawn**; §2's defect stands and is
  folded into §3 item 4 above. §1's verification and the blocker clearance are unaffected.
- `2026-07-27-1622-architect-dll-size-ruling.md` — the size blocker, genuinely cleared, not reopened.
- `src/OpenWSFZ.Ft8/Native/ft8_shim.h:333` — `FT8_SHIM_VERSION`.
- `src/OpenWSFZ.Ft8/Interop/Ft8LibInterop.cs:246` — `ExpectedShimVersion`, and :237–244 the comment
  describing what the bump is for.
- `src/OpenWSFZ.Ft8/Native/win-x64/libft8.version.txt` — the CI-rebuild behaviour §4 rests on.

---

*Per HK-015 Architect → QA: §3 is a design for QA to author as a dev-task, not a task issued here.
Per HK-014 committed locally, no push. Per HK-011 nothing here touches `src/` or native code.*
