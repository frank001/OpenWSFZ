# Developer handoff: D-001 C.1 — is `K_MAX_CANDIDATES` costing us decodes?

**Authored by:** QA (per HK-000/HK-015). **Status:** ready for a Developer session. Needs a native
rebuild (`src/OpenWSFZ.Ft8/Native/ft8_shim.c`), so this is HK-011 work — not QA-only.
**Source:** `qa/cycleframer-alignment-replay/2026-07-26-0100-architect-to-qa-land-housekeep-and-continue-d001.md`
Part C.1, and `2026-07-26-0015-d001-consolidation-and-clean-slate.md` §3/§6.1.

---

## 1. Why this is the right experiment to run first

D-001's remaining gap is a decoder problem: 740 of 751 missing decodes (98.5%) are attributable to
the decoder, not capture or the live path
(`qa/cycleframer-alignment-replay/2026-07-26-0015-d001-consolidation-and-clean-slate.md` §1). The one
live lead: `ldpc_stats.py` over an 11h51m session shows sync-candidate yield **saturated at 140** —
`K_MAX_CANDIDATES` in `src/OpenWSFZ.Ft8/Native/ft8_shim.c:467` — in 8 of 10 deciles, with *identical*
candidate yield on cycles that decode 22 messages and cycles that decode none, while LDPC survival
collapses (`failCands` 82→136, `meanAbsLLR` 4.075→3.83).

Two readings are both possible from that one fact, and this experiment separates them:

- **If raising the cap raises decodes materially:** we have been truncating the candidate list
  before LDPC ever sees the missing signals, and which 140 survive is an artefact of scoring order,
  not signal quality. Part of the 740 becomes directly recoverable by tuning this constant.
- **If decodes stay flat while `failCands` rises:** the extra candidates found beyond 140 are
  spurious (noise crossing the sync-score floor), the cap is not the constraint, and the entire loss
  routes to the LLR-normalisation question (C.2 — do not scope it until this reports).

## 2. Critical prerequisite — a genuine stack-buffer-overflow landmine, found while drafting this

**Read this before touching `K_MAX_CANDIDATES`. Raising it without this fix will corrupt the native
stack, not just change decode counts.**

`ft8_shim.c:1297`:

```c
/* Size the local candidate array to the maximum across all passes */
ftx_candidate_t candidates[K_MAX_CANDIDATES_PASS2]; /* largest per-pass max */
int ncands = ftx_find_candidates(&mon.wf, pass_max_cands, candidates, pass_min_score);
```

The comment's assumption — that `K_MAX_CANDIDATES_PASS2` (200) is "the largest per-pass max" — is
true **only** at the current `K_MAX_CANDIDATES = 140`. For pass 0, `pass_max_cands` is
`K_MAX_CANDIDATES` (`ft8_shim.c:1275`), and `ftx_find_candidates` writes into `heap[heap_size]` for
every `heap_size < num_candidates`
(`native/ft8_lib_build/patched/ft8/decode.c:264-303`) — i.e. it will happily write up to
`pass_max_cands` entries into whatever array it's given, with **no bound related to the array's
actual declared size**. At `K_MAX_CANDIDATES = 300` or `600`, pass 0 writes past the end of a
200-element stack array. This is silent native stack corruption, not a crash you can rely on seeing
immediately — exactly the kind of bug that produces confusing, non-reproducible decode-count noise
if it ships unfixed and someone then tries to interpret the results.

**Fix, before building any of the three settings:** size `candidates[]` to the true maximum across
both passes, e.g.:

```c
#define K_MAX_CANDIDATES_ANY_PASS \
    (K_MAX_CANDIDATES > K_MAX_CANDIDATES_PASS2 ? K_MAX_CANDIDATES : K_MAX_CANDIDATES_PASS2)
...
ftx_candidate_t candidates[K_MAX_CANDIDATES_ANY_PASS]; /* largest per-pass max, either direction */
```

Note `K_MAX_DECODED` (`ft8_shim.c:511`, `= K_MAX_CANDIDATES + K_MAX_CANDIDATES_PASS2`) already
scales correctly with `K_MAX_CANDIDATES` — no fix needed there, it just grows the cross-pass dedup
hash table (`decoded_msgs`/`decoded_ht`, both stack-allocated at `ft8_shim.c:1196-1197`). Sanity-
check total stack frame growth at 600: `decoded_msgs[800]` + `decoded_ht[800]` +
`candidates[600]` + `all_supp_cands/msgs/snrs[600]` each — comfortably under a native thread's
default 1 MB stack, but confirm no crash under the 600 setting before trusting its numbers (§5).

## 3. Method

For each of `K_MAX_CANDIDATES` ∈ {140 (baseline, already built and committed), 300, 600}:

1. Edit `src/OpenWSFZ.Ft8/Native/ft8_shim.c:467` (`#define K_MAX_CANDIDATES 140` → 300, then 600).
   **Pass 0 only** — leave `K_MAX_CANDIDATES_PASS2` (200, line 504) untouched.
2. Apply the §2 fix if not already present.
3. Rebuild `libft8.dll` — `native/ft8_lib_build/rebuild_shim.bat` builds against the patched sources
   in `native/ft8_lib_build/patched/` and copies the result to
   `src/OpenWSFZ.Ft8/Native/win-x64/libft8.dll` (see `src/OpenWSFZ.Ft8/Native/BUILD.md` for the
   underlying `cl`/`link` commands if the batch script needs adjusting). This is a local Windows dev
   binary only — do not commit it as a permanent change until §7's decision is made; CI rebuilds its
   own Linux `.so` from source on every run, using whatever `ft8_shim.c` is committed.
4. Re-decode the fixed corpus: **`artefacts/20260725_live_run_1806/wsjt-x/wav/`** (WSJT-X's own
   captured audio for the same 68 matched cycles used throughout the D-001 decomposition — using
   WSJT-X's audio rather than our own keeps the capture chain, already measured at 0.5% of the gap,
   out of this experiment entirely). Use `qa/rr-study/d001-param-sweep-2026-07-22/D001ParamSweep`
   with `--points k10_c0.10_n60` (the shipped production baseline —
   `kMinScorePass2=10, osdCorrThreshold=0.10, osdNhardMax=60`, matching `config.json` exactly) and
   `--dial-mhz 7.074`.
5. **Deviation required from "use the harness unmodified":** the harness currently constructs
   `Ft8Decoder(new SystemClock(), logger: null)` (`Program.cs`, both `sharedDecoder` and the
   per-WAV fallback) — with `logger: null`, the `failCands`/`meanAbsLLR`/`prenormVar` debug lines
   (`Ft8Decoder.cs:420`, `"failCands={FailCount} meanAbsLLR={MeanAbs:F3} prenormVar={PrenormVar:F4}"`)
   are never emitted anywhere, so they cannot be reported as asked without a change. Add a minimal
   `ILogger<Ft8Decoder>` to the harness that writes Debug-level lines to a per-setting log file
   (e.g. `<out-dir>/<point>/decode.log`), pass it into the `Ft8Decoder` constructor(s) in place of
   `null`, and parse the resulting file the same way `ldpc_stats.py` parses the live daemon log
   (same regex shape: `RE_LLR` in that script matches this exact line format) — but pointed at the
   harness's own log instead of `artefacts/.../owsfz/*.log`. This is a **QA-tooling change under
   `qa/`, not `src/`** — record it as a deviation in this file's own "Done" annotation, the project's
   standing convention (see `tasks.md`'s `**Done (deviation recorded):**` style), not as a silent
   edit to "the unmodified harness."
6. Record, per setting: total decodes (sum across the 68 cycles), `failCands` and `meanAbsLLR`
   aggregated the same way `ldpc_stats.py` already aggregates them (median/mean across cycles — mirror
   its existing methodology rather than inventing a new one), and decode elapsed time (the harness
   already tracks `totalDecodeMs` per WAV × grid point — report median/p90 ms per cycle against the
   15 s per-cycle budget).

## 4. Interpretation — decisive either way

- **Decodes rise materially** (compare against the 1288 already measured on this same
  `wsjt-x/wav/` corpus at the current 140 cap,
  `2026-07-26-0015-d001-consolidation-and-clean-slate.md` §1) ⇒ we have been truncating the candidate
  list. The cap becomes a tuned parameter and part of the 740 is directly recoverable. Report the
  recovered count and whether 300 or 600 is where it plateaus.
- **Decodes stay flat while `failCands` rises** ⇒ the extra candidates beyond 140 are spurious, the
  cap is not the constraint, and the whole of the 740 routes to C.2 (LDPC/LLR-normalisation
  scoping) — do not attempt to fix this by raising the cap further.

## 5. Watch for — budget breach is a real finding, not a failed experiment

Decode time scales with candidate count against a 15 s per-cycle production budget (current median
373–653 ms per the live session, so there is headroom, but 600 candidates is ~4× pass 0's current
work). If a setting wins on decodes but its p90 (or worse) decode time threatens the 15 s budget,
**record that as a finding** — it means that setting is not directly shippable even if it recovers
decodes, and C.2/C.3 need to know the recovery has a cost attached, not that the experiment failed.

Also confirm no crash/hang at 600 before trusting its numbers — this is the setting furthest from
the value the shim has ever run at in production, and §2's fix is new and unverified at that scale.

## 6. Definition of done

- [ ] §2's `candidates[]` sizing fix applied and confirmed present at all three settings tested
      (140 does not strictly need it, since `K_MAX_CANDIDATES_PASS2`'s current 200 already covers
      it, but apply it anyway so the 140 baseline run is on the same code path as 300/600 — no
      hidden variable between settings).
- [ ] Three rebuilds (140/300/600), each re-decoding the full 68-cycle `wsjt-x/wav/` corpus at
      `k10_c0.10_n60`.
- [ ] Report table: setting → total decodes → `failCands` (median/mean) → `meanAbsLLR` (median/mean)
      → decode elapsed time (median/p90 ms per cycle).
- [ ] The harness logger addition (§3.5) committed under `qa/`, with the deviation recorded in this
      file.
- [ ] `python3 tools/pre_merge_check.py` green (HK-006) before any "ready" claim.
- [ ] `git status` clean of any rebuilt `libft8.dll` unless §7 below decides to keep a new cap value
      — do not leave a locally-rebuilt DLL staged by accident (it will silently change every other
      test's decode counts on this machine).
- [ ] Per HK-011: present the `src/` diff (and any decision to change `K_MAX_CANDIDATES` permanently)
      to the Captain for explicit pre-push sign-off. Per HK-010: `gh pr merge` always needs the
      Captain's explicit sign-off, green CI notwithstanding.

## 7. What happens after this reports

QA owns the analysis and reports back per the ownership table in the source handoff (§D). **If the
result contradicts `2026-07-26-0015-d001-consolidation-and-clean-slate.md` §1's decomposition table
in any way, escalate to the Architect rather than quietly revising it** — that table is what closed
the capture-chain avenue, and per the source handoff it should not be revised without a look.
Do not scope C.2 (LDPC/LLR normalisation) until this reports — C.1 changes the candidate population
LDPC is being asked to survive, so scoping C.2 first would be scoping against a moving target.

## 8. Cross-references

- `qa/cycleframer-alignment-replay/2026-07-26-0015-d001-consolidation-and-clean-slate.md` §3, §6.1
  — the mechanism and the two-question decomposition this experiment resolves.
- `qa/cycleframer-alignment-replay/2026-07-26-0100-architect-to-qa-land-housekeep-and-continue-d001.md`
  Part C.1 — the instruction this handoff was drafted from.
- `qa/cycleframer-alignment-replay/ldpc_stats.py` — the log-parsing methodology to mirror for
  `failCands`/`meanAbsLLR` aggregation.
- `src/OpenWSFZ.Ft8/Native/BUILD.md` — full native build commands (Windows/Linux/macOS) if
  `rebuild_shim.bat` needs adjusting.
- `qa/rr-study/d001-param-sweep-2026-07-22/Program.cs` — the offline decode harness; §3.5's logger
  addition is the only change needed to it.
- `src/OpenWSFZ.Ft8/Ft8Decoder.cs:420` — the existing `failCands`/`meanAbsLLR`/`prenormVar` Debug log
  line this experiment reads.
