> **Status note (Developer, 2026-11-08).** Authorised by the Captain ("go for the developer"). Architect build spec `qa/rr-study/2026-11-08-1614-architect-to-qa-spec-coh-res-cand.md` (Amendments 1 and 2); QA task `dev-tasks/2026-11-08-coh-res-cand-272.md`. Branch `feat/coh-res-cand` from `origin/main` `e3db42cf`. Nothing pushed.

## 1. Implementation (Developer, `src/`; C# only)

- [x] 1.1 `decoder.coherentFallbackResidualCandidates` (bool, absent or false = off): `DecoderConfig.CoherentFallbackResidualCandidates`, a volatile field on `Ft8Decoder`, set by the daemon before the first window and on save, read once per window; config overlay (HK-035); no Settings control.
- [x] 1.2 The residual decode's snapshot is taken at `SubtractionPass.cs:446` right after `DecodeAll`, on its thread, only when requested; carried in `ResidualPassReport.CohSnapshot` (R2) and `ThirdPassResult.CohSnapshot` (R3); a failed snapshot is contained.
- [x] 1.3 `CohFallbackAudioSelector.Select` returns the snapshot with the buffer; the residual-side run gets it, the original run keeps `cohSnapshot`; a missing snapshot is `fallback-orig`.
- [x] 1.4 Log fields `resCand`, `resEligible`, `origEligible` while effective; counters `GetResidualCandidatesCounters()`.
- [x] 1.5 **No native change**: `git diff --stat origin/main -- native/ src/OpenWSFZ.Ft8/Native/` empty; `libft8.dll` SHA-256 `1ba8dc3d6a7d032764b3eaf65e7e5ef850c56b35569ad880b53d6708524db914`.

## 2. Tests (Developer; no fixed sleeps, TESTING_STRATEGY section 11)

- [x] 2.1 `CohResCandTests`: OFF is a no-op (one snapshot); Original mode no effect; R3 and R2 each give the residual run its buffer's snapshot and the original run `cohSnapshot`; Residual mode; a missing snapshot (null or throw) for each buffer gives `fallback-orig`; the residual pass keeps its decodes when its own snapshot fails; no duplicate text; a never-started original run counts the original snapshot's eligible candidates.
- [x] 2.2 Config key: absent reads false, explicit values, wire name (`CoherentFallbackResidualCandidatesConfigTests`).

## 3. Housekeeping (Developer)

- [x] 3.1 `VERSION` 0.68 to 0.69 everywhere the gates check; `check_version_bump.py`.
- [x] 3.2 `REQUIREMENTS.md` FR-103 and changelog row 1.65; every requirement in the delta spec has scenarios; `openspec validate --all --strict`.

## 4. Acceptance (QA; the Captain's order: HK-039 review, then the arms, then `pre_merge_check.py`, then the push)

- [ ] 4.1 HK-039 review record of the Developer's commit before any acceptance run.
- [ ] 4.2 B-NAT, B-OFF (40 cycles), arms A (OFF) and B (ON) on 400 cycles of night `20260930_1930`; rows B-WIRE, B-DUP, N-GO, N-STOP, U-OK, U-FAIL, B-AB per build spec section 3.
- [ ] 4.3 `pre_merge_check.py` on a clean checkout; the Captain's merge sign-off (HK-010); default ON is a separate decision.
