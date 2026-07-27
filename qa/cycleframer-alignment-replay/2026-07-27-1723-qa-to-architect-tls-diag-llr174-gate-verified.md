# D-001: QA -> Architect report — `tls_diag_llr174` compile-time gate implemented, reviewed, verified

**Author:** QA, 2026-07-27 (17:23 UTC, `date -u`, per HK-017). **For:** the Architect (§1-§4), and the
record (§5).
**Answers:** the Developer-session diff produced from `dev-tasks/2026-07-27-d001-gate-tls-diag-
llr174-compile-time.md`, itself authored against your ruling
`2026-07-27-1622-architect-dll-size-ruling.md` §4 and handed off in
`2026-07-27-1634-qa-to-architect-tbss-nailed-and-devtask-handoff.md` §2.
**This is a notification, not an escalation.** The dev-task is complete and passed review; nothing
here asks for a re-ruling.

---

## 1. Verdict: approved

The Developer session implemented the dev-task's option (d) — a default-off
`#if FT8_ENABLE_RAW_LLR_CAPTURE` gate around `tls_diag_llr174` alone, per your ruling's §4
recommendation. I reviewed the diff against the dev-task's §3 ABI constraint and §6 acceptance
criteria and found no defects. Details below; full findings already delivered to the Developer/
Captain in-session, reproduced here for your record since the ruling was yours.

## 2. What was verified, and how

| Check | Method | Result |
|---|---:|---|
| Scope: only `ft8_shim.c` + both binaries + `libft8.version.txt` touched by this fix | file mtimes (everything else last-touched 2026-07-26, before this dev-task existed) | matches exactly |
| `tls_diag_llr174` array + its capture-loop write compile only under the gate, default 0 | diff read | confirmed |
| `ft8_get_last_candidate_llr` stays exported in every build, returns 0 (not a compile failure) when gated off | diff read | confirmed |
| **The ABI gotcha your ruling didn't need to address**: `ft8_set_candidate_diag_llr_capture`/`ft8_set_llr_shrinkage` must stay unconditionally exported, since `Ft8Decoder.cs` calls both every decode cycle regardless of the flag | diff read, **then proved behaviourally**: 297/297 `OpenWSFZ.Ft8.Tests` pass on both Windows and WSL against the rebuilt binaries — an `EntryPointNotFoundException` on either export would have failed the suite outright | confirmed, not just inspected |
| Windows `.dll` size | `ls -la` | 60,416 bytes (matches version.txt claim exactly; back to the pre-Phase-2c ~60.8 KB baseline your ruling used as the reference point) |
| Linux `.so` `.tbss` size | `readelf -S` — **ran it myself, independent of the Developer's claim**, same tool I used in the 16:34 handoff to nail the mechanism in the first place | `0xad0` = 2,768 bytes, matching the version.txt claim and the dev-task's 2,700-2,800-byte prediction |
| `FT8_SHIM_VERSION` unchanged at 20260035 | `tools/check_native_version.py` on both binaries | confirmed — no ABI/contract change, correctly not bumped |
| Diagnostic build (`-DFT8_ENABLE_RAW_LLR_CAPTURE=1`) still compiles | standalone `gcc -c` against `ft8_shim.c` with the flag | clean, no errors |
| `git diff --stat` surgical | `git status` + mtime cross-check | confirmed |

One item taken partly on the Developer's word rather than independently reproduced: `libft8.
version.txt` claims a locally-built diagnostic variant was runtime-checked to still return real,
nonzero, finite per-candidate LLR rows. I confirmed the diagnostic build *compiles*; I did not
relink a full `.so` and re-run it against a corpus to reproduce that specific runtime claim myself,
given everything else checked out to the byte. Flagging this so it's on the record, not because I
doubt it.

## 3. Net effect against your ruling

Your ruling's core finding — the real cost was per-thread committed memory (`.tbss`), not shipped-
binary disk size — is now resolved at the mechanism you named: `.tbss` drops from 100,208 bytes
(shim 20260035, array present) to 2,768 bytes, i.e. back to just the shim-20260034 scalar/array
group (~1.4 KB) plus the shim-20260035 shrinkage scalars and enable flags, exactly as predicted. The
`tls_diag_llr174` study capability itself is not lost — it rebuilds on demand via the one-off
`-DFT8_ENABLE_RAW_LLR_CAPTURE=1` flag, satisfying your ruling's §4 condition ("no workflow that
needs this buffer switchable in a *shipped* artifact").

## 4. What this does not settle

- **No push, no merge** (HK-014/HK-010) — Captain sign-off and `pre_merge_check.py` (Captain's
  trigger, HK-006) both still pending, neither run by me.
- **Branch disposition** remains the Captain's call (your ruling §7) — unaffected by this report.
- This closes the one blocker your ruling raised against the native binaries; it does not itself
  constitute a merge decision for `d001-c4-min-score-sweep` as a whole.

## 5. Cross-references

- `2026-07-27-1622-architect-dll-size-ruling.md` — the ruling (§2 real cost, §4 recommended fix,
  §7 scope limits).
- `2026-07-27-1634-qa-to-architect-tbss-nailed-and-devtask-handoff.md` — the `.tbss` mechanism
  confirmation and dev-task handoff this report follows up on.
- `dev-tasks/2026-07-27-d001-gate-tls-diag-llr174-compile-time.md` — the dev-task implemented and
  reviewed here.
- `src/OpenWSFZ.Ft8/Native/win-x64/libft8.version.txt` — Developer's own rebuild note, cross-checked
  independently in §2 above.

---

*Per HK-015, this is a report back to the Architect on a ruling's implementation, not an escalation.
Per HK-014, nothing is pushed or merged. Per HK-011, this review touched no `src/` or native code —
build/test runs only, no edits.*
