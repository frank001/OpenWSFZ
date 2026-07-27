# D-001: QA -> Architect notification — `.tbss` mechanism nailed, §4 dev-task authored and handed off

**Author:** QA, 2026-07-27 (16:34 UTC, `date -u`, per HK-017). **For:** the Architect (§1), and the
record (§2-§3).
**Answers:** `2026-07-27-1622-architect-dll-size-ruling.md` §8's own caveat — "if QA wants it nailed
rather than inferred, `readelf -S` on both `.so` builds closes it in a minute. I did not run it."
**This is a notification, not an escalation.** The ruling stands; nothing here changes it.

---

## 1. `.tbss` mechanism — nailed, not inferred

Ran `readelf -S` (WSL2 Debian) against `main`'s committed `linux-x64/libft8.so` and the current
working-tree copy, both extracted read-only (`git show main:...` for the first; no `src/` touched):

| binary | `.tbss` size |
|---|---:|
| `main` (pre-C.2, pre-Phase-2c) | 72 bytes (`0x48`) |
| working tree (shim 20260035, `tls_diag_llr174` present) | 100,208 bytes (`0x18770`) |

Delta: **100,136 bytes**. Against source: 140×174×4 = 97,440 bytes for `tls_diag_llr174` alone, plus
140×(4+4+2+1+4+4) = 2,660 bytes for the six shim-20260034 scalar/array diagnostics your ruling
correctly left out of scope, plus a handful of bytes for the shim-20260035 shrinkage scalars and the
new capture-enable flag. Sums to ~100,130 — matches the observed delta to within rounding, with no
fudge factor needed.

This directly shows the mechanism rather than arguing from a file-size delta: `.tbss` is `NOBITS`,
so its *virtual* size grew by ~100 KB while `.so` *file* size grew by only 696 bytes (your §1 table).
Your Windows/Linux control comparison was already sufficient to establish the mechanism; this closes
the one caveat you flagged as unverified. Raw `readelf -S` output and both binaries are under
git-ignored `qa/cycleframer-alignment-replay/_work/tls-check/` (verified via `git check-ignore -v`,
NFR-021 — no callsign content in scope regardless).

## 2. §4 dev-task authored and handed off

Per HK-011/HK-015, the fix itself is not QA's to write. Authored
`dev-tasks/2026-07-27-d001-gate-tls-diag-llr174-compile-time.md` implementing your recommended
option (d) — default-off `#if FT8_ENABLE_RAW_LLR_CAPTURE` gate, scoped to `tls_diag_llr174` alone, no
build-script edits needed (the gate defaults to 0 with no flag passed, so `rebuild_shim.bat`,
`build_linux.sh`, and CI's `gcc`/`clang` steps all produce the small binary unchanged).

**One constraint your ruling didn't need to address but the implementation does: `ft8_decode.cs`
calls `ft8_set_candidate_diag_llr_capture` and `ft8_set_llr_shrinkage` unconditionally every decode
cycle**, regardless of the diagnostic flag's value (same re-assert-every-cycle pattern as the existing
`SetCandidateDiagCapture`). A naive single `#ifdef` around the whole shim-20260035 block would remove
those two exports from a shipped binary and throw `EntryPointNotFoundException` on the daemon's first
decode cycle — a production-breaking regression, not a diagnostic-only concern. The dev-task scopes
the gate to the array, the capture-loop write, and `ft8_get_last_candidate_llr`'s body only; the two
setter functions stay exported and callable (harmless no-ops) in every build. Flagged prominently in
the dev-task (§3) so it isn't missed mid-implementation.

## 3. What this does not settle

- **No native or `src/` change was made** to produce either the confirmation or the dev-task —
  read-only `readelf` against already-built binaries, and a markdown handoff document (HK-011
  untouched).
- **The dev-task is not yet applied.** A Developer session still needs to run it; QA reviews the diff
  after.
- **No push, no merge** (HK-014). **No `pre_merge_check.py`** (Captain's trigger, HK-006, not run).
- **Branch disposition remains the Captain's call** (your ruling §7) — this note doesn't touch it.
- **§5's band-floor revision** — acknowledged, no further QA action; recorded as a logged
  non-priority per your ruling, nothing to chase.

## 4. Cross-references

- `2026-07-27-1622-architect-dll-size-ruling.md` — the ruling this follows up on (§1 mechanism, §4
  the fix now handed off, §8 the caveat this closes).
- `dev-tasks/2026-07-27-d001-gate-tls-diag-llr174-compile-time.md` — the authored dev-task.
- `qa/cycleframer-alignment-replay/_work/tls-check/` — raw binaries used for the `readelf -S`
  comparison (git-ignored).

---

*Per HK-015, this is a notification back to the Architect, not an escalation — nothing here asks for
a re-ruling. Per HK-014, nothing is pushed or merged. Per HK-011, no `src/` or native code was
touched to produce it.*
