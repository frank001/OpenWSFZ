# `OSD-FA-A` E1 — result: **`E1-1` fires, decisively** — `osd_nhard_max` 60→40 eliminates 96.6% of noise-only FP events

QA, 2026-09-11 20:45Z (`date -u`, HK-017). Per Amendment 1 §5.1, continuing after the Architect's
`A1`/`B1` acceptance ruling (`2026-09-11-2021-...-part-a-b-acceptance.md`, `arch/osd-fa-a`
`d905ac3`).

**Headline: `E1-1` fires, and not marginally.** At `osd_nhard_max=60` (production default), `413` of
`4,000` M1 S5 noise slots produced ≥1 decode. At `40`, only `14` did. `p = 1.55 × 10⁻¹²⁰`.

---

## 1. HK-020 — critical config, verified against source, not assumed

| config | value | source |
|---|---|---|
| Population | 4,000 M1 S5 AWGN slots, `D:\...\awgn-fp-replay\_work\m1m4_s5\` (same population as Part 0) | Amendment 1 §5.1 |
| Input contract | `WavReader.Read` (int16/32768) → `NormalisePcm(pcm, 0.20)` | `Ft8Decoder.cs:271`/`:52` — **verified directly, not assumed to be Part 0's `WavReader`-only convention** |
| Equivalence used | `part_d.read_wav_normalised` (raw int16 → `normalise_rms(0.20)`) | mathematically identical to the production contract — see §2 |
| Legs | `nhard=60` (control), `nhard=40` (treatment), same session, paired by slot | Amendment 1 §5.1 |
| Event | slot with ≥1 decode — **count-based, no text used at all** | Amendment 1 §5.1 |
| Statistic | exact two-sided McNemar, `binomtest(min(r,a), r+a, p=0.5)` | `fp-parity/p3_parity.py`, reused (HK-018) |

**Added 2026-09-11, per the E1 acceptance ruling §1 (Clopper–Pearson 95%, independently
re-verified via `scipy.stats.beta`):** event rate at 60 = `10.325% [9.40%, 11.31%]`; event rate at
40 = `0.35% [0.19%, 0.59%]`; share of 60's events removed at 40 = `399/413 = 96.6% [94.4%, 98.1%]`.

**Disclosed deviation (per the E1 acceptance ruling §3 — not wrong, just missing from the original
report): `ft8_set_decode_params` is called TWICE PER SLOT** (alternating 60/40), in one process, on
one thread, between complete, synchronous `decode_all()` returns — never while a decode is in
flight. Base §2.5's literal "set before the first decode, never mid-run" is written for a single
setting per run; this is the OTHER of the two schemes the ruling accepts (§2 reminder). Ruled
harmless: the shim's own documented hazard (`ft8_shim.c:474–476`) is a race between a module-level
write and a **thread-pool read during a decode**, which cannot occur here (single thread, no decode
in flight when the setter runs); production hot-applies `OsdNhardMax` the same way in-process
(`Program.cs:867`); and `n_60` independently reproducing P3's own `413` (above) is itself empirical
confirmation nothing leaked between legs.

## 2. The input-contract equivalence, verified rather than assumed

Per the Architect's own reminder, this does **not** assume Part 0's convention transfers. Checked
directly against `Ft8Decoder.cs`:

- `PcmNormalisationTargetRms = 0.20f` (`:52`) — matches `p23_common.PROD_TARGET_RMS` exactly.
- `SilenceRmsThreshold = 1e-6f` (`:51`) — matches `p23_common.SILENCE_RMS_THRESHOLD` exactly.
- `NormalisePcm`'s own formula (`:497-508`): `scale = targetRms / srcRms`, applied uniformly, silent
  buffers returned unchanged — identical arithmetic to `p23_common.normalise_rms`.

**`normalise_rms(pcm, t) = pcm · (t / rms(pcm))` is scale-invariant to the caller's own choice of
intermediate units**: for `pcm_B = pcm_A / 32768`, `rms(pcm_B) = rms(pcm_A)/32768`, so
`normalise_rms(pcm_B, t) = normalise_rms(pcm_A, t)` exactly. Reading raw int16 magnitude and
normalising (`part_d.read_wav_normalised`, reused here) therefore produces **bit-identical** output
to `WavReader`'s `int16/32768` conversion followed by `NormalisePcm` — not an approximation, an
algebraic identity. This is the production input contract, used here, disclosed rather than
assumed.

## 3. Result

```
n_slots = 4,000
n_60 (event at nhard=60)  = 413
n_40 (event at nhard=40)  =  14
r (event@60, none@40)     = 399
a (event@40, none@60)     =   0
both                      =  14
neither                   = 3,587
n_discordant (r+a)        = 399
Exact two-sided McNemar p = 1.549e-120
```

~~**`n_60 = 413` matches the spec's own §5.5 resolution estimate ("~413 events") exactly** — the
prior sizing was accurate.~~ ⛔ **CORRECTED 2026-09-11, per the Architect's E1 acceptance ruling
§2 (`2026-09-11-2048-architect-osd-fa-a-e1-acceptance.md`, `arch/osd-fa-a` `5507063`): the "≈413"
in Amendment 1 §5.1 was not a sizing guess — it was `FP-PARITY` P3's own MEASURED count, the source
of the `10.325%` citable offline rate. `n_60` reproducing `413/4,000` exactly is an **independent
check that this leg's input contract matches P3's own**, stronger than "the prior sizing was
accurate."** **`a = 0`**: not one slot gained an event when the gate tightened.

**Row: `p < 0.05` and `r > a` (`399 > 0`) ⇒ `E1-1`.** Matches the Architect's blind prediction
(`E1-1`, confidence `0.6`) — **scores correct.**

**Consequence, per Amendment 1 §5.1:** Option B produces a detectable FP reduction on noise. Report
the rates: **event rate `10.325% → 0.35%`** (`413/4000` vs `14/4000`) at `nhard` 60 vs 40 on this
population — a **96.6% reduction** in noise-triggered FP events.

**Determinism:** two independent processes, identical seeds-free deterministic decode — every
figure (`n_60`, `n_40`, `r`, `a`, `both`, `neither`, `p`) byte-identical across both runs.

## 4. What this does and does not license

Per Amendment 1 §5.4 (strict order): `E1-1` alone does not draft anything — the consequence table
requires `E1-1 and E2-B1 and E3-N` together before the Architect is cleared to draft a
pre-registration for the default change. **This result only clears the first of three conditions.**
`E2` (genuine cost under oracle truth) is the only leg that can show this is safe; `E3` can only
show live harm, never safety. Continuing to `E2` next.

🛑 **Mandatory citation pairing (E1 acceptance ruling §4): never cite `E1-1` alone when speaking
about live FP — always pair it with `D1`.** On noise, OSD accepts with `nhard` in `(40, 60]`
account for ~97% of false-decode events (this result). **On live audio, OSD-path decodes are `≤
~1.9%` of output** (Part D3's CI upper bound). Option B's live reach is bounded by the `1.9%`, not
by the `97%`.

## 5. NFR-021

Not engaged. This leg is count-based only — message text was never extracted, read, or stored;
`dec.decode_all(pcm)` results are only ever tested for truthiness (`bool(d60)`/`bool(d40)`) before
being discarded.
