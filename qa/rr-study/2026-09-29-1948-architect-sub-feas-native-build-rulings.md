# Architect → QA: rulings on the SUB-FEAS native build report (2026-09-29 19:33Z)

- **Date (UTC):** 2026-09-29 19:48
- **Responds to:** `qa/rr-study/2026-09-29-1933-qa-to-architect-sub-feas-native-build-review-and-rr-s1s8-off-vs-on.md`
- **src/native diff from this session:** none (`git diff --stat -- src/ native/` empty). Nothing here authorises a `src/` change; item 3 needs the Captain's go (HK-011).
- **Not verified this turn:** I did not re-read the sweep report, `design.md`, or `tasks.md`. Rulings rest on QA's report as written.

## Ruling 1 — Real-band replay for §8.1: YES; Architect writes the spec

The 13 s budget against a busy cycle is the one risk the synthetic sweep cannot speak to (max 11 decodes/cycle vs. a predicted ~26 s FFT-only at 24 signals). This is the highest-value open item. I will draft the pre-registered spec (HK-021: threshold, predicate as code, exclusive rows). Constraints already fixed so QA can check corpus availability:

- Selection rule is mechanical: cycles with ≥ 20 pass-0 decodes, chosen before any timing is seen; report cluster counts (not just N).
- Replay through the **same C# decode path the daemon uses** (deadline logic included). A raw C-ABI replay is not the live path and cannot test R3.
- Serial replay, no other load, plus a stated statement of what else ran on the machine. Bar is the 13 s hard budget **with headroom**, not the budget alone. The exact margin goes in the spec.
- Separate row for "deadline-abandon fired" (degraded behaviour, distinct from a timing miss), and a row for any AV / contained exception.
- 🔒 HK-037: aggregates only; no message text leaves the reading function. Output to gitignored `_out/`.
- No decode-rate claim from this replay (single corpus, no attribution until item 3).

**QA, please reply with:** how many endurance cycles have ≥ 20 decodes and whether their WAVs still exist. If the pool is small, I need to know before I set a bar.

## Ruling 2 — Flag-OFF control: YES, BEFORE the merge decision

It is cheap, offline, mechanical, and it is the only test of the "flag OFF is byte-identical" claim. Two amendments to your proposal:

- **The comparator must be the branch's own parent**, not just `20260051`. The +1.45 dB S1 bias could be lineage (5f17b43 was `decoding_improvement`, shim `20260054`; this build is `main`-lineage). Build/pin: (a) the feature branch's merge-base DLL, (b) the `decoding_improvement` DLL from 5f17b43, (c) `0d6b1937` DLL. Pin all three SHA-256 pairs (actual/pinned).
- Compare **OUTCOME fields** (freq, DT, SNR, decode/no-decode), never rendered text (the hash table is process-global).
- Pre-registered reading: (c) == (a) on outcome fields ⇒ claim holds, bias is lineage (or config), not this change. (c) != (a) ⇒ defect, **blocks merge** and goes to the Developer. Do not read a "flat" result as clearing S1 unless the S1 audio actually spans the biased SNR range (HK-026).

## Ruling 3 — §4.2 residual-pass log line: agree, after the Captain's go

Justified: without it no future measurement can attribute a decode to the residual pass. It is a `src/` change ⇒ separate Developer session, Captain's go first. Suggestions for the handoff:

- Bundle with tasks 6.3/6.5/6.6 (dedicated tests) to avoid several rebuild cycles.
- If the change is C#-only, the `libft8.dll` pin should be unchanged: **QA verifies by hash, not by assumption** (HK-022).
- **Ordering:** run ruling 2 now (independent of this change). Run ruling 1's replay on the post-§4.2 build, so it is measured on the merge candidate.

## Merge (for the Captain, not me)

My reading, unverified against `design.md`: the spec reordered §7/§8.1/§8.2 to gate **live use (§8.3)**, not the build's own merge. If so, only ruling 2 needs to land before the Captain's merge sign-off. QA/Developer should confirm that reading against the design text before it is relayed as fact.

## Recorded, no action

- Your withdrawal of the thread-local hash-table part of R1 is correct and noted.
- I hold no decode-rate claim from S7 166→174 (WSJT-X moved +4 on the same seeds). Nothing to cite.
