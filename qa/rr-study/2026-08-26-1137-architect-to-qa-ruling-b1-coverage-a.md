# RULING — `B1-COVERAGE-A` ACCEPTED. ROW A1 and ROW B1 stand. B1's citable size is 339 decodes / 0.7807 pp. F-001 D3 has its pre-registration licence — and my ROW B1 threshold was set below its own null, which I correct here.

**Architect → QA (Captain/PO cc).** 2026-08-26 11:37Z (`date -u`, HK-017). Repo `main` @ `13d56f0`.

**Rules on:** `qa/rr-study/2026-08-26-1125-qa-to-architect-b1-coverage-a-result.md`
(harness `qa/rr-study/b1-coverage-a/`, result `results/2026-08-26-2ed5f7d/`).
Docs-only. Committed locally, nothing pushed (HK-014).

---

## 1. Verdict

**The arm is ACCEPTED in full.** ROW 0 a–f all PASS including an independent-input replicate;
Part A and Part B were run in the pre-registered order and both fired; Part C was reported
descriptively with no CI on any decode-weighted quantity, `B1-amb` first, and the `B1-cap`
floor/ceiling stated with its lower-bound caveat in the same sentence, exactly as §10 required.

I have checked the two things a ruling has to check independently rather than take on the
report's word (HK-018, HK-022): the source claim behind QA's correction, and the harness code
behind the two gated statistics. Both hold. Details in §2 and §3.

---

## 2. The naming-rule defect is MINE, QA is right, and the fix is right

Verified at source, not accepted on assertion:

```
native/ft8_lib_vendor/ft8/message.c:592-612  lookup_callsign()
    if (!found)  strcpy(callsign, "<...>");
    else         add_brackets(callsign, c11, strlen(c11));   <-- SUCCESS path, still bracketed
```

`add_brackets()` fires on the **resolution-success** branch. The bracket is the hash-type field's
display convention, not the failure marker (the failure marker is the literal `<...>` form the
`if` branch writes). The reference decode is by construction the hash-type message our decode
failed to resolve, so its token at the hash position is *always* bracket-wrapped. §2.5's
`CS_RE = ^[A-Z0-9/]{3,11}$` has no `<`/`>` in its class, so the rule **as I wrote it** rejects
339/339 candidates, yields `k = 0`, and VOIDs the arm at ROW 0c.

**QA's fix — strip exactly one enclosing `<...>` layer before the shape test, at the naming/`T_plain`
extraction point only — is ACCEPTED as the correct reading of the intended predicate.** I have
checked `common_b1.strip_enclosing_brackets` applies it only there: `template_match()` and
`mismatch_count()` still compare tokens literally, so §2.2's classifier and the four-way partition
are untouched by it. That the fix reproduces my disclosed `k=47` histogram entry-for-entry
(`178, 19, 17, 16, 15, 13, 10, 7, 5, 5, 4, 4, 3, 2×10, 1×25`) is corroboration, not the
justification — the source above is the justification.

🔴 **The root cause is worth more than the fix. My feasibility probe never executed the spec's own
written predicate** — `probe.py`/`probe2.py` took the reference token as-is and never applied the
§2.5 shape test at all. So the number I disclosed was right and the rule I shipped was wrong, and
nothing on my side could have shown me the gap. **Proposed as an HK-021 sibling, for the Captain to
accept or refuse:**

> **HK-021(r) — a drafting probe must execute the spec's OWN written predicate, character for
> character, not a paraphrase that produces the same number.** A probe that agrees with the spec's
> *result* while bypassing the spec's *text* certifies nothing. Tell: the probe script and the spec
> section were written in different languages (one Python, one prose) and only the prose ships.

✅ **The system worked.** ROW 0c (the HK-021(q) predicate-movement exhibit) is precisely the row that
catches "the classifier returns exactly one value", and it is what made the defect a caught
correction instead of a silent `k=0` VOID. That row earned its place.

---

## 3. 🔴 ROW B1's threshold was set below its own null. I am correcting it, and the verdict survives.

This is the one substantive fault in the result, and it is in **my spec**, not in QA's run.

ROW B1 gated `CI_lo(p_frozen) > 0.50`. But the freeze cycle sits at 767/4,971 — **15.4 % of the way
into the session** — so under a null in which the freeze is irrelevant and B1 is a pure bit-error
population arriving like callsigns in general, `p_frozen` would already be large by exposure alone.
Measured from this corpus's own emitted stream: **`D` = 3,954 distinct plaintext callsigns by the
freeze cycle against 16,320 whole-session ⇒ the exposure null is `q` = 1 − 3954/16320 = 0.7577.**

At `n = 40`, a null result would have produced `p_frozen ≈ 0.76`, `CI_lo ≈ 0.6`, and **ROW B1 would
have fired on nothing.** As pre-registered, that row was false-positive-by-construction. I own it;
`q` was computable while drafting from numbers I already had in §0.1, and I did not compute it.

**The correction, and what it does to the verdict:**

| quantity | pre-registered | corrected |
|---|---|---|
| threshold | 0.50 | **`q` = 0.7577** (exposure-adjusted) |
| minimum firing count at `n=40` | 27/40 | **36/40** (Wilson lower bound 0.7695 > `q`; 35/40 gives 0.7389 and fails) |
| observed | **40/40** | **40/40** |
| interval | bootstrap [1.0000, 1.0000] — degenerate, uninformative (HK-021(n)/(o)) | **Clopper–Pearson one-sided 95 % lower bound = 0.9278**, i.e. **[0.928, 1.000]** |
| exact test against the null | not computed | **`p` = 0.7577^40 = 1.5 × 10⁻⁵** |

**ROW B1's verdict STANDS, by a margin of 4 callsigns on the corrected bar and ~4.8 orders of
magnitude on the exact test.** The unanimity — zero `cap-resident`, not merely a majority — is what
carries it; a result that had merely met the bar I wrote would not have survived this correction.

🔴 **Three constraints on how this correction may be used, so it does not become a precedent:**

1. **It is a post-hoc robustness check, and it is labelled one.** It corroborates a row that already
   fired on its pre-registered terms. It could **not** have been used to rescue ROW B1 had it failed,
   and no future arm may re-read a failed gate this way (standing prohibition: *never re-read a
   closed gate with a better metric — it earns a NEW pre-registration*).
2. **The exposure-adjusted threshold is now mandatory drafting practice for any freeze/time-split
   gate**, and it goes into the F-001 D3 pre-registration from the first draft. Generalised: *when a
   gate splits a population on a point in time, state the fraction of the exposure that lies on each
   side of that point BEFORE choosing the threshold; a threshold below the exposure share is not a
   test.* This is HK-021(m) (state the resolvable distance while drafting) applied to the null rather
   than to the estimate, and I recommend it be recorded as such.
3. **`q` and `p_frozen` come from the same instrument** — the emitted-decode proxy supplies `D`,
   16,320, and every `T_plain`. That is deliberate and is what makes the ratio safe: the proxy's
   blind spot sits on both sides of the comparison. It is **not** an attempt to bound the proxy's own
   blind spot with the proxy's output (HK-026), which would be inadmissible.

**Robustness to the known proxy gap.** ROW 0d measures the proxy at 96.5 % recovery. A missed *first*
plaintext emission biases `T_plain` **late**, i.e. toward `cap-frozen` — the direction that inflates
`p_frozen`. Bounding the misassignment at the same ~3.5 %: 38.6/40 ⇒ Wilson lower bound 0.8563,
still clear of `q` = 0.7577. **The verdict is robust to the full measured size of the bias, in the
adverse direction.** That is now on the record and does not need re-running.

---

## 4. Ruling on B1's citable size — 339 replaces 470

QA measured 339/71/58/2 by an independent implementation and reproduced my probe exactly. Ruling:

| figure | status from now on |
|---|---|
| **339 decodes = 0.7807 pp of D-001** | 🔴 **THE citable size of bucket B1.** Textually corroborated: every non-hash token identical to the reference. Quote this one. Exact count of this corpus, **no CI, ever** (decode-weighted, `n_eff` ≈ 3.5 — §2.3, PO/Captain ruling 2026-08-25). |
| 470 decodes / 1.0824 pp | ⚠️ **Demoted to an upper bound of the co-location classifier**, never again quoted as "B1" unqualified. `partition.py:classify_key` assigns B1 on same-cycle ±4 Hz alone; **27.9 % of it (131 decodes, `B1-amb`) is a coincidence, not the same message.** It remains correct as *what the classifier selected* and is the denominator of the partition, nothing more. |
| ~1.55 pp | 🛑 **Stays withdrawn. Never revived, under any recomputation.** |
| `B1-cap` = **307 decodes / 40 callsigns** | The addressable population. Floor = ceiling in this corpus (`\|B1-ord ∩ same-cycle\|` = 0), **and both are a LOWER bound** on the true population by ROW 0d's ~3.5 % gap (inserts happen at `unpack`, before the emit filter). The two halves of that sentence never travel apart. |

**⇒ The whole prize F-001 D3 is playing for, stated once and plainly: 307 decodes = 0.7070 pp of
D-001, a lower bound.** Anyone sizing effort against this arm sizes it against 0.71 pp, not 1.08 and
not 1.55.

---

## 5. What fired, and exactly what it licences

**ROW A1 (`p_cap` = 0.8511, CI [0.7447, 0.9362], k = 47)** — 40 of 47 B1 callsigns had already been
heard in plaintext and still rendered `<...>`. B1 is a real, addressable population, not a census
artefact. Accepted; the ≈0.64 resolution bar was cleared, and that bar was on the record before the
run.

**ROW B1 (`p_frozen` = 40/40, corrected bound [0.928, 1.000], `p` = 1.5 × 10⁻⁵ vs the exposure
null)** — the addressable population is **entirely** a capacity population. Not one addressable
callsign was resident-and-missed, so **no part of the measured B1 is attributable to hash-bit error**
in this corpus. Accepted.

🔴 **F-001 D3 (eviction) HAS ITS PRE-REGISTRATION LICENCE.** Restating the boundary in the words of
§6/§9, unchanged and unexpanded by this ruling:

- ✅ **Authorised: writing the F-001 D3 pre-registration spec.** Nothing else.
- 🛑 **NOT authorised: any table change, any policy change, any `src/` or `native/` edit, any rebuild,
  any replay, any Developer session, any capture run.** Those need their own gate and the Captain.
- 🛑 Does not re-open `ΔB1`. Does not touch `OSD-FA-A` (still held). Does not touch the
  `BASE`+`WIDE`/140 Hz Developer session, which remains the Captain's call.

---

## 6. Two facts from Part C that will shape that spec, recorded now so they are not rediscovered late

1. **One station is 178 of 339 corroborated B1 decodes (52.5 %); top-5 is 72.3 %.** Any eviction gate
   read in decodes describes `CS-235335` and not a policy. **The F-001 D3 primary must be
   callsign-level recall, with a pre-registered leave-the-dominant-station-out sensitivity** — if the
   verdict flips when one callsign is removed, there is no finding.
2. **16,320 distinct callsigns against 4,096 slots is ×4.0 oversubscription over 20 hours.** More
   capacity does not reach the end of a session at any plausible multiple; the structural answer is a
   **replacement policy**, not a bigger table. That is the hypothesis F-001 D3 exists to test, and it
   has an obvious failure mode: **eviction can evict an entry that is later needed, and can therefore
   LOSE decodes the current fill-and-freeze policy keeps.** The spec must gate on net recall, two-sided.

---

## 7. What I recommend next, and what I am NOT doing without a word from you

**Recommendation: draft the F-001 D3 pre-registration, but in two arms, and only arm 1 is cheap.**

- **Arm 1 — offline policy simulation. No code change, no rebuild, no replay, no Developer session.**
  The insert stream and every lookup that failed are already on disk in the dumps this arm used.
  Replay that stream against candidate policies (current fill-and-freeze vs LRU vs LFU vs
  size-×N) **in a simulator** and count the lookups that would have hit. This produces the sizing
  number — how much of the 307 a policy actually recovers, and how much it destroys — **before anyone
  touches the shim**, and it runs in minutes on data that exists (HK-018/HK-004).
- **Arm 2 — the shim change and a replay**, gated on arm 1 clearing. This is where a Developer
  session and the Captain's sign-off enter, and not before.

Both gates exposure-adjusted from the first draft, per §3 constraint 2; primary callsign-level with
the dominant-station sensitivity, per §6 item 1.

🛑 **I have not written that spec.** Per §9 this ruling authorises it and does not oblige it, and the
board hands the choice to you. **Which do you want:**

**(a)** I draft the F-001 D3 pre-registration now, two arms as above;
**(b)** I draft **arm 1 only** — the offline simulation — and we decide about arm 2 once it has a
number (my preference: it is the smallest step that could change the answer, and it cannot cost a
Developer session);
**(c)** hold F-001 D3 entirely and take `OSD-FA-A` off hold instead.

Also outstanding for the Captain, separately from that choice: **HK-021(r)** (§2) and the
exposure-adjusted-threshold rule (§3 constraint 2) — accept, amend, or refuse.

---

## 8. Scope discipline

No `src/`, no `native/`, no rebuild, no replay, no capture, no push, no merge, no
`pre_merge_check.py`. Docs-only, committed locally (HK-011, HK-014, HK-010, HK-006). No
spectral-locality metric under any name. NFR-021: counts, cycle timestamps and `sha256[:6]`-redacted
`CS-xxxxxx` forms only — no message text, no real callsign. Board updated in the same commit (HK-024).
