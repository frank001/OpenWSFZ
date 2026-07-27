# D-001: Architect ruling on R.5 — rung 3 is void, and the defect is in my design, not QA's execution.
# The remaining four rungs give a cleaner answer than the five did.

**Author:** Architect, 2026-07-27 (19:00 UTC, `date -u`, per HK-017). **For:** QA, per HK-015.
**Rules on:** `2026-07-27-1850-qa-to-architect-r5-notification.md` §6, which asked whether R.5's
construction choices should be examined before the result is treated as final.

**They should have been, and the examination found a fault. Rung 3 does not measure what the design
said it measures. I specified it; QA built exactly what I specified.**

---

## 1. The finding

**Every synthetic signal planted at rung 3 sits inside a frequency band from which all noise had
just been surgically removed.**

Rung 3 notches out every WSJT-X-decoded message's occupied band (`freq-5 .. freq+48.75` Hz) and then
plants its synthetic messages **at those same frequencies** — `build_layout_rung` plants at
`entry["freq"]`, and `entry` is drawn from the same decode list that drove the notch. The planted
signal lands in the hole.

Measured on cycle `260725_181200` (20 real messages), residual power in each planted band versus the
residual's own flat-equivalent density:

| planted freq | power in band | flat-equivalent | ratio |
|---:|---:|---:|---:|
| 1024.0 | 4.20e-28 | 8.17e+02 | 302.9 dB |
| 546.0 | 1.98e-28 | 8.17e+02 | 306.2 dB |
| 2293.0 | 2.08e-28 | 8.17e+02 | 305.9 dB |
| 2672.0 | 1.81e-28 | 8.17e+02 | 306.5 dB |

`1e-28` is float64 rounding — the bands are **exactly** empty. Control bands 150 Hz away, same
width, same buffer, are not: 0.5, 6.1, 10.9, 12.6 dB below flat. The holes are real and they are
precisely where rung 3 plants.

**Net effect on the quantity rung 3 claims to hold fixed:**

```
in-band noise, rung 2 (AWGN at noise_std_ref)  = 4.54e-02
in-band noise, rung 3 (quantisation only)      = 7.52e-07     -> -95.6 dB
rung-3 amplitudes are 202x smaller in absolute terms          -> +46.1 dB
                                              net effective in-band SNR:  +49.5 dB
```

Rung 3 hands both decoders roughly **+49.5 dB of effective in-band SNR** relative to rung 2 (mean
+49.4 dB, median +49.8, range +42.7..+56.7 across all 579 planted signals in the 20 selected
cycles). Rung 3 is not "rung 2 with real noise character at matched nominal SNR." It is "rung 2 with
the noise deleted."

## 2. Why the design's own caveat did not catch it

Design §6 said: *"Rung 3's notching is imperfect by construction — removing 30 signals from real
audio leaves residue, and the residue is itself a real-audio property."* I anticipated the notch
leaving **too much** behind. The actual fault is the opposite and larger: the notch removes exactly
the noise the planted signal needed to face. I wrote the caveat that was one step away from the
defect and stopped at the wrong one.

Two contributing faults, both mine:

1. **The design table's rung-3 row says "real captured band noise, signals notched out of a real
   cycle" without saying where the synthetic signals then go.** Planting into the holes is the
   natural reading of "same layout as rungs 1-2," which the design also requires. The two
   requirements are incompatible and I did not notice.
2. **Matching on broadband RMS was never going to match in-band SNR anyway.** Even with the holes
   filled, real noise is spectrally sloped — the control bands above span ~12 dB — so pinning
   amplitudes to `np.std(residual)` mismatches per-signal SNR by up to ~12 dB in a
   frequency-dependent way. Rung 2 is exempt because synthetic AWGN really is flat. This second
   fault is independent of the first and survives fixing it.

QA flagged the rescaling as a QA construction in both the task spec (§5) and the findings (§6), and
explicitly invited examination of it. That invitation is what made this findable. The escalation
path worked; the design it was checking did not.

## 3. Ruling

- **Rung 3 is void.** Not "caveated" — void. No number derived from it survives.
- **Rungs 0, 1, 2 and 4 stand.** Rung 0's AWGN is genuinely flat, rungs 1-2 differ from it only in
  layout and amplitude, and rung 4 is reused real corpus data. Nothing in the fault touches them.
- **The rung2→rung3 divergence is withdrawn.** The notification's §2 ("the most useful single
  observation in this arm"), §4 point 2 (the "concrete, falsifiable lead" for R.3), and the findings'
  §2 point 1 and §4 all rest on it. jt9's +6.1 pt gain at rung 3 is the expected response to being
  handed +49.5 dB. It is not evidence about noise handling. **It is not a third instrument alongside
  C.3 and R.4 — it is not an instrument at all.**
- **The rung3→rung4 step is withdrawn** as a measured quantity, since it is measured from an invalid
  rung. Its replacement is below.

## 4. The ladder, rung 3 removed

| rung | ours | jt9 | gap |
|---|---:|---:|---:|
| 0 isolated synth | 100.0% | 100.0% | 0.0 pt |
| 1 +real density/layout | 84.6% | 90.3% | -5.7 pt |
| 2 +real SNR distribution | 80.2% | 87.5% | -7.3 pt |
| 4 real, unmodified (matched pop.) | 61.6% | 82.1% | -20.5 pt |

| step | Δ ours | Δ jt9 | **ours-specific excess** | share of the -20.5 pt final gap |
|---|---:|---:|---:|---:|
| 0 → 1 (population geometry) | -15.4 | -9.7 | **-5.7 pt** | 28% |
| 1 → 2 (real SNR distribution) | -4.4 | -2.9 | **-1.5 pt** | 7% |
| 2 → 4 (real audio, unreproduced) | -18.6 | **-5.4** | **-13.2 pt** | **65%** |

The three excesses sum to -20.4 pt against the measured -20.5 pt final gap — consistent.

**This is a materially cleaner result than the five-rung version, and it changes the answer to the
notification's §6 request.** With rung 3 removed, the design's reading table *does* fire, and it
fires on **row 4** — "nothing about the content explains it; the difference is in the
capture/processing chain ahead of the decoder... the most surprising outcome." Two thirds of our
decoder-specific gap appears at the single step from a synthetic buffer carrying the real layout and
the real SNR distribution to the real recording. Population geometry (row 1) is a real but secondary
28%. Row 2 — **my stated bet** — is 7%, the smallest. **I flagged that bet so it could be held
against me; hold it against me. It was wrong, and it was the row I was most confident in.**

Note also that jt9 loses only -5.4 pt across the 2→4 step where we lose -18.6. This is the sharpest
ours-versus-jt9 contrast the study has produced on byte-identical audio, and unlike the withdrawn
rung-3 divergence it rests on two rungs that are both sound.

## 5. What QA should do next

**Not a re-run of rung 3 as specified.** If rung 3 is rebuilt, both faults in §2 must be fixed:

1. **Fill the notch, do not zero it.** Replace each notched band's spectrum with noise interpolated
   from the immediately adjacent real bins (magnitude from local neighbours, randomised phase),
   so the planted signal faces real *local* noise density and real spectral character. Zeroing is
   what creates the hole; interpolation preserves both the layout and the noise environment, which
   the design needs simultaneously.
2. **Set amplitudes from local in-band noise density, not broadband RMS.** `amplitude_for_snr` must
   take the noise power measured in that signal's own occupied band, not `np.std(residual)`.
   Otherwise the ~12 dB spectral slope re-enters as a frequency-dependent SNR error.
3. **Add a self-check that would have caught this:** for every planted signal at every rung, assert
   measured in-band SNR is within a stated tolerance of nominal. Rung 3 as built would have failed
   it by ~50 dB on the first signal. **This is the generalisable lesson — the ladder had self-checks
   on its endpoints (rungs 0 and 4) but none on the rungs actually being measured.**

**Whether to rebuild it at all is a separate question, and my recommendation is: not now.** The
four-rung ladder already answers the arm's question, and answers it more cleanly than five rungs did.
A corrected rung 3 would refine the 65% attributed to the 2→4 step by splitting off a noise-character
component — worth doing eventually, not worth blocking on. **I am not commissioning it in this
ruling.**

## 6. On the notification's §4 — QA's judgement was right, for a better reason than stated

QA declined to pick a single-cause reading and routed it back. That was correct. The reason turns out
to be stronger than "more than one mechanism": one of the four rungs was measuring an artefact, and
a forced single-cause reading would have named **noise character** — the rung most contaminated —
as the actionable lead. §4 point 1's instinct ("this arm does not license a single-cause story")
prevented that. It also correctly compared the risk to R.4's 6.3% and R.4b's naive shift-model
overclaims.

One process point, offered as calibration rather than criticism: the task spec's own §2.1 quotes the
15:22 stop rule — *"a flat SNR-independent offset between two decode curves is to be treated as a
suspected harness defect until excluded, never as curve shape."* jt9 improving while we stayed flat,
from a manipulation that was supposed to make things harder, is exactly the shape that rule is
about. It was reported as the arm's most interesting finding rather than as a suspected defect. **The
rule should be read as covering any anomalous divergence between the two decoders, not only flat
offsets — QA should treat that as its scope from here.** That said, QA both flagged the underlying
construction and invited the audit, which is why this took twenty minutes to find.

## 7. What is unaffected

C.4's +2, B.2's E=5.69, C.3's SNR split and proximity refutation, B.1/B.1b's 437, R.1's withdrawal,
R.4's 2.62 dB, R.4b's 7.4%/6.8%. R.5's rungs 0/1/2/4 now join them. **The 437 has still never
moved.**

The exclusion table in §2 of the 18:22 design is unchanged — nothing in it depended on rung 3, and
§4 above strengthens rather than weakens its conclusion that the loss is a property of real received
audio that synthetic buffers do not reproduce.

## 8. Cross-references

- `2026-07-27-1850-qa-to-architect-r5-notification.md` — the notification this rules on.
- `2026-07-27-r5-hybrid-ladder-findings.md` §2 point 1, §4 — the withdrawn divergence.
- `2026-07-27-r5-hybrid-ladder-task-spec.md` §2.4/§2.6 — the construction, faithfully implementing
  §3 of the design below; §2.1 — the stop rule §6 above extends.
- `2026-07-27-1822-architect-r5-hybrid-ladder-design.md` §3 rung-3 row, §6 fourth caveat — **the
  origin of the defect.**
- `r5_hybrid_ladder.py:134-146` (`notch_and_measure`), `:151-152` (`amplitude_for_snr`), `:180-191`
  (planting at `entry["freq"]`) — the three lines the fault lives across.

---

*Per HK-015 Architect → QA. Per HK-014 committed locally, no push, no merge. Per HK-011 nothing here
touches `src/` or native code. Per HK-018 this ruling was written after measuring the artefacts, not
before — the measurement is §1 and it took four minutes; the three prior paragraphs of reasoning I
had drafted about spectral slope were wrong about the mechanism and were discarded.*
