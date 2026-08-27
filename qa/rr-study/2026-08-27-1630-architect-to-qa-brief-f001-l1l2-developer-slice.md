# ARCHITECT -> QA — IMPLEMENTATION BRIEF: `F-001` L1+L2 Developer slice

**From:** Architect · **To:** QA · **Date:** 2026-08-27 16:30Z (`date -u`, HK-017) · Repo `main` @ `900306d`
**Ordered by:** the PO, 2026-08-27, following the R5 ruling.

Provenance: `qa/rr-study/2026-08-27-1615-architect-to-qa-ruling-f001-r5.md` (Sec.6) and the R5 spec's
Sec.8 design brief, **as amended by that ruling**.

🔴 **This is a brief for QA, not a dev task.** HK-015: `dev-tasks/*.md` are QA's to author. HK-011:
`src/` work is a separate Developer session with the Captain's sign-off — **this document authorises
nothing on its own.** HK-014: nothing pushed.

---

## Sec.1 — Scope

**IN:** L1 (parse the 2-token Type-4 form) and L2 (normalise the `dest` token before comparing).
Both are **managed-only**. No native change, no ABI change, no shim version bump.

**OUT, explicitly:**

- **L3** (own-hash compare). Needs shim → ABI → answerer and a build past `20260046`. Second slice,
  after this one is proven.
- **Displayed names / harm 1.** No change to any name shown or logged — see the constraint in Sec.3.
- **The misresolution remedy** (ARM 2 / the remedy pre-registration, still with the PO/Captain).
  Different mechanism, different code. **This slice does not collide with it and need not wait.**
- **Any efficacy claim.** HK-021(p) still binds: until a binary exists and transmits, route 5's
  benefit is asserted from the protocol, never measured.

---

## Sec.2 — The sites, verified today (not inherited from the R5 spec)

Re-grepped against the working tree at `900306d`. **The R5 spec named five comparison sites; there are
more `dest`-consuming sites than that, and the Developer must see all of them.**

| # | site | what it does | named in R5 Sec.8.2? |
|---|---|---|---|
| 1 | `QsoAnswererService.cs:1631` | `TryParseMessage` — the 3-token gate (**L1**) | yes |
| 2 | `QsoCallerService.cs:1349` | second, independent copy of `TryParseMessage` (**L1**) | yes |
| 3 | `QsoAnswererService.cs:1079` | `dest.Equals(ours, OrdinalIgnoreCase)` (**L2**) | yes |
| 4 | `QsoAnswererService.cs:1161` | `dest.Equals(ours, OrdinalIgnoreCase)` (**L2**) | yes |
| 5 | `QsoCallerService.cs:938` | `dest.Equals(ours, OrdinalIgnoreCase)` (**L2**) | yes |
| 6 | `QsoCallerService.cs:1385-1394` | inline `parts[0]` compare — **does not go through `TryParseMessage`**; already normalises base-vs-compound (`PD2FZ/P` → `PD2FZ`) | yes |
| 7 | `QsoAnswererService.cs:1127` | `dest.Equals("CQ", …)` — the "partner still calling CQ" check | 🔴 **NO** |
| 8 | `QsoCallerService.cs:959` | `dest.Equals("CQ", …)` — same check, caller copy | 🔴 **NO** |

Sites 7/8 do not compare against our call, so they are not L2 comparison sites — **but they consume
the same `dest` variable**, and any implementation that normalises at the parse boundary changes what
they see. A bracketed token is never `"CQ"`, so no new CQ match can be created; the point is that the
Developer must have decided this rather than discovered it.

`TryParseMessage` (site 1) is exactly as transcribed in R5 Sec.3.1 — confirmed by reading, character
for character. The transcription that the R5 harness ran against is sound.

---

## Sec.3 — The implementation trade-off, and the constraint that decides it

Two shapes are available. **This is the Developer's call with the Captain, not mine** — but the
trade-off must not be discovered mid-build.

**(A) Normalise at the parse boundary.** Strip one `<`/`>` pair inside both `TryParseMessage` copies
plus the inline path at site 6. Smaller diff, covers sites 3/4/5/7/8 at once, one place to reason
about.
🔴 **Cost, verified:** `dest` reaches a log call at `QsoAnswererService.cs:~1131` (`partner, dest`).
Normalising at the boundary **changes that log line's text**. That is not a UI name and so is not
harm 1 in the strict sense — but the R5 ruling promised "no change to any displayed name", and a log
line is close enough that it must be a decision, not a side effect.

**(B) Normalise at each comparison.** Logs stay byte-identical. **All of sites 3/4/5/6 must move
together** — fixing a subset is a defect, and there are two independent parse copies to keep in step.

**Constraint either way:** the `<...>` all-dot marker is **not a callsign** and must never compare
equal to anything (R5 Sec.3.2's guard: reject empty, reject all-dot). This is the one line where a
mistake is silent and severe.

---

## Sec.4 — The decision this session must make explicitly

🔴 **This is the crux, and it is a PO/Captain decision, not an implementation detail.**

L2 makes an already-resolved hash **actionable**. Per the R5 ruling Sec.6.2, that promotes an existing
harm 1 (a wrong name displayed) into a harm 2 (**an unsolicited transmission to a station that did not
call us**). The evidence, both directions, stated together:

- **Against acting in the unengaged state:** when an own-hash-equivalent rule fires, it is wrong
  ~3 times in 4 in this corpus (G3 MIN, CP one-sided 95% lower **0.7102**, against an a-priori base
  rate of 1/4,096 = 0.000244).
- **For acting anyway:** a fire is **rare**. 129 of 11,233 hypothetical own-calls take any false fire
  across four days; mean 0.084, median 1 among those affected. Our own call: **0** observed
  (🔴 λ = 0.379 — HK-021(j), not evidence of absence).
- **The asymmetry that matters:** in the partner-bound states (`WaitReport`, `WaitRr73`) the existing
  `fromPartner && toUs` conjunction already contains this at no cost. **In the unengaged state there
  is no partner to bind against — and that state is exactly where the benefit lives** (someone
  answering our CQ with a nonstandard call). Restricting L2 to partner-bound states is safe and
  guts most of the value. That trade is the decision.

**QA: put this in the dev task as an explicit decision with a recorded answer.** It must not be
resolved by whichever branch the code happens to fall into.

---

## Sec.5 — Proposed acceptance criteria (mechanical, HK-021 shape)

QA to finalise; these are drafted to be checkable, with hard thresholds and consequences as
assertions.

1. **Both parse copies move together.** A test asserts the 2-token form parses in *both*
   `QsoAnswererService` and `QsoCallerService`. Consequence: a single-copy fix fails the build.
2. **The all-dot marker never matches.** `<...>` as `dest` yields `toUs == false` for every own-call
   input, including an own-call of `"..."`. Hard: any true ⇒ fail.
3. **Bracket-stripped equality.** `<PD2FZ>` as `dest` with `ours = PD2FZ` yields `toUs == true`;
   `<PD2FZ>` with `ours = PD2FZQ` yields false. Exercises L2's own boundary.
4. **The compound-callsign precedent is preserved.** Site 6's existing `PD2FZ/P` → `PD2FZ` acceptance
   still passes unchanged. Consequence: a regression here means L2 broke an existing normalisation.
5. **Log-text decision is asserted, not assumed.** If shape (A) is chosen, a test pins the new log
   text; if (B), a test pins that it is unchanged. Either way the choice is visible in the diff.
6. 🔴 **PROPOSED — the zero-fire corpus replay.** Replay `artefacts/20260803_live_run_1713/owsfz`
   through the new build with `ourCallsign = PD2FZ`. **The answerer must fire `toUs` exactly zero
   times.** Rationale: `PD2FZ` occurs zero times as a plain token in either log (R5 ruling Sec.4), so
   it can never have entered a hash table and can never be printed as a resolved `<PD2FZ>` — the
   correct answer is a hard zero. Any non-zero fire is either a bracket-guard defect or a
   misresolution reaching the answerer, and both are exactly what this slice risks.
   ⚠️ Needs the binary, so it is a post-build gate, not a pre-build one. **It does not need a
   transmitting station** — which is why it is worth having under the PO's bench-only decision.

---

## Sec.6 — What this slice will and will not have established (stated once)

**PO decision, 2026-08-27: bench/unit coverage for now; no transmitting live run in this slice.**
Recorded so nobody has to reconstruct it later.

Consequence, and it is not a criticism of the decision — it is the thing that must not silently
disappear: **after this ships, route 5's benefit remains asserted from the protocol and never
measured.** Bench tests exercise our own encoder against our own decoder, which tests
self-consistency, not alignment (HK-022). The efficacy question needs a transmitting station and a
nonstandard-call correspondent, and it stays open. Sec.5 criterion 6 recovers the *cost*-side
regression check offline; it recovers nothing on the benefit side, because nothing offline can.

---

## Sec.7 — What this brief does not do

- **Authorises no `src/` change.** HK-011: separate Developer session, Captain's sign-off. QA drafts
  the `dev-tasks/*.md`; QA proposes and stops.
- **Does not revise** ARM 1B (A1/51.3%), ARM 1C's VOID, ARM 1D's C3+D3, the accepted defect, or
  GH #132/#60.
- **Does not pre-judge** the ARM 2 / remedy pre-registration, which remains with the PO/Captain.
- **Adopts no HK-021 sibling.** (v), amended (w) and new (x) all sit with the Captain.
- **Makes no efficacy claim, in either direction.** G3-2 UNFAVOURABLE did not kill route 5 and this
  brief does not resurrect it — it scopes the part that can be built and checked today.
