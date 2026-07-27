# D-001: QA -> Architect notification — band-floor figure delivered, cycle-set-corrected;
# R.3 held as instructed

**Author:** QA, 2026-07-27 (16:15 UTC, `date -u`, per HK-017). **For:** the Architect, per HK-015.
**Answers:** `2026-07-27-1603-architect-hold-r3.md` §4 in full.
**This is informational, not a request for a ruling** — the note asked for a number "whenever
convenient," not a decision, and nothing here changes anything on the record.

---

## 1. §4 point 1 — R.3 not started

Held, as instructed. §1.1/§1.2's reasoning holds up: C.1 already answered the candidate-cap axis
on real audio (+12 decodes, 1.6% of the gap), and R.4/R.4b's isolated-signal geometry cannot
produce a non-zero asymptote to attribute the real corpus's persistent ~10% strong-signal loss to.
No arm run this session.

## 2. §4 point 2 — the exact cycle-set intersection

Delivered in full in `2026-07-27-1611-qa-band-floor-cycle-set-correction.md`. Headline:

| | corpus 1 (40m, 68 cyc) | corpus 2 (20m, 126 cyc) |
|---|---:|---:|
| below-200 Hz, raw, % of miss population | 1.27% | 1.96% |
| **below-200 Hz, corrected, % of miss population** | **0.76%** | **1.96%** (no correction needed) |
| above-3000 Hz, % of miss population | 0.00% | 0.21% |

Both land inside your "~1–2%" bound as stated. **The self-check surfaced one thing beyond the
requested filter:** 4 of corpus 1's 10 raw below-200 rows turned out to be messages we also
decoded — WSJT-X reports them at 198 Hz, we decode the identical message at exactly 200.0 Hz, our
lowest bin's edge. Read as bin-edge quantisation (a signal a couple Hz under nominal `f_min` still
falls inside our lowest search bin's coverage), not a defect — traced via aggregate frequency
deltas only, no message text (NFR-021). The six genuine corpus-1 misses sit at 193–194 Hz, clear of
any plausible edge tolerance. Corpus 2 shows no equivalent case among its own near-edge rows.

**Combined range, both corpora, corrected: 0.76%–1.96% of the miss population** — tighter than,
and at the low end slightly below, the bound you quoted. Small, in the direction of "even less,"
not more.

## 3. What this does and does not change

**Does not change:** your ruling that the band-floor question is "worth measuring, not worth
assuming" — the NFR-018/soundcard-noise and `MaxPass0Candidates`-interaction cautions in the 15:55
note stand untouched, and nothing here commissions the `src/`+native work that would be needed to
act on it (HK-011 unaffected). **Does change:** the number to cite, per above, and — worth flagging
on its own terms — this is now the **eighth** instance in this thread of a self-check catching
something beyond what was asked (the 198→200.0 Hz pairing), on a task explicitly scoped as
"minutes, not a session." Noted for the record, not as a complaint about scope creep — it cost
under ten minutes and the number would otherwise have been quoted slightly wrong.

## 4. Cross-references

- `2026-07-27-1611-qa-band-floor-cycle-set-correction.md` — full detail, self-check, method.
- `2026-07-27-1603-architect-hold-r3.md` §4 — the request this closes out.
- `2026-07-27-1555-architect-r4b-ruling-and-band-limits.md` §2.2, §9 — the bound this refines.

---

*Per HK-014, nothing here is pushed or merged. Per HK-011, nothing here touches `src/` or native
code — arithmetic on already-collected `ALL.TXT` data, no capture, no rebuild.*
