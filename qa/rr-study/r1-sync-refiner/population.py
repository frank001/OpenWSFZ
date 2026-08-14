#!/usr/bin/env python3
"""r1-sync-refiner-instrument-validation -- validation population (tasks 3.1-3.4).

Builds the pre-registered offset/SNR grid deterministically (HK-021(g): strata fixed
globally, in this module, before any generation happens) and the coordinates each trial
needs to render its PCM on demand via the existing encoder-only synth chain
(qa/rr-study/synth: encoder.py -> symbols.py -> modulator.py -> channel.py -> wavio.py).

No per-trial WAV files are persisted (3,600 trials x 720 KB would be ~2.6 GB); instead
this module returns a deterministic MANIFEST (list of trial dicts) that fully determines
each trial's PCM via render_trial_pcm() -- audio is regenerated bit-identically from the
manifest on every harness run (deterministic: fixed seeds, no dict/set iteration order
dependency anywhere in this file -- R0 D3's hash-randomised-set-iteration pitfall does
not apply here since every collection walked below is a list/tuple, built in a fixed
order). This is what makes AC-5 (determinism) meaningful: three independent process runs
against the "same input population" means three independent constructions of this same
manifest, which are byte-identical by construction.

Strata (spec Requirement "Validation population is generated from a pre-registered,
adequately powered grid"; design.md Open Question resolutions recorded in
2026-08-14 QA report):

  FREQ_OFFSETS_HZ = {0, +-0.4, +-0.8, +-1.2, +-1.5}    (9 values)
  TIME_OFFSETS_S  = {0, +-0.01, +-0.02, +-0.03, +-0.039} (9 values)
  SNR_STRATA_DB   = {+5, 0, -5, -10, -15, -20}          (6 values)

"offset-class" (spec: "SNR x offset-class cell", n >= 200 floor) is operationalised here
as two classes, a judgment call recorded in the QA report per HK-004:
  - "grid"   -- (freq, time) drawn by cycling deterministically through the 9x9=81
                 fixed grid combinations above.
  - "random" -- (freq, time) drawn by uniform-random draws within the same ranges
                 (+-1.5 Hz, +-0.039 s), satisfying the "plus uniform-random draws"
                 clause of the Requirement text.

6 SNR strata x 2 offset classes = 12 cells x N_PER_CELL(200) = 2,400 signal trials.
"""
from __future__ import annotations

import pathlib
import sys

_HERE = pathlib.Path(__file__).parent.resolve()
_SYNTH_ROOT = _HERE.parent  # qa/rr-study
if str(_SYNTH_ROOT) not in sys.path:
    sys.path.insert(0, str(_SYNTH_ROOT))

import numpy as np  # noqa: E402

# ── Pre-registered strata (HK-021(g): fixed here, before any generation) ────────────
FREQ_OFFSETS_HZ = (0.0, 0.4, -0.4, 0.8, -0.8, 1.2, -1.2, 1.5, -1.5)
TIME_OFFSETS_S  = (0.0, 0.01, -0.01, 0.02, -0.02, 0.03, -0.03, 0.039, -0.039)
SNR_STRATA_DB   = (5.0, 0.0, -5.0, -10.0, -15.0, -20.0)
OFFSET_CLASSES  = ("grid", "random")

N_PER_CELL   = 200
SAMPLE_RATE_HZ = 12000
BUFFER_SAMPLES = 180_000   # 15 s @ 12 kHz (FT8_EXPECTED_SAMPLES)

# Coarse lattice position given to the refiner (the "candidate position" it is asked to
# refine relative to). Chosen away from band edges; 0.3 + 0.039 + 12.64 = 12.979 s < 15 s
# so even the widest injected offset keeps the full 79-symbol transmission inside the buffer.
F_LATTICE_HZ = 1000
T_LATTICE_S  = 0.3

# AC-3 noise-only population (task 3.4): same trial-count discipline as a signal cell
# (n >= 200), scaled to 6x for a well-powered null test (a single "cell" -- no SNR
# stratification applies to pure noise). Coarse positions are drawn across a broad band
# so the uniformity test is not confined to one search-space corner.
N_NOISE = 1200
NOISE_FREQ_BAND_HZ = (300.0, 2700.0)
NOISE_TIME_BAND_S  = (0.1, 1.0)

SEED = 20260815  # base seed for this change; distinct from any prior D-001 arm's seed

# ── Distinct-message generation (standing synth requirement) ────────────────────────
_GRID_LETTERS = "ABCDEFGHIJKLMNOPQR"  # 18 letters, A-R


def _grid_locator(index: int) -> str:
    """Deterministic distinct 4-char Maidenhead grid locator for trial `index`.

    18 * 18 * 100 = 32,400 distinct values -- comfortably more than the ~3,600 trials
    in this population, so every trial's message text is guaranteed distinct.
    """
    index = index % 32_400
    a = _GRID_LETTERS[(index // (18 * 100)) % 18]
    b = _GRID_LETTERS[(index // 100) % 18]
    dd = index % 100
    return f"{a}{b}{dd:02d}"


def message_for_trial(index: int) -> str:
    """Fictional CQ+grid message (Q1AW is the canonical fictional example callsign
    already used by qa/rr-study/gen_decoder_fixtures.py; NFR-021 compliant)."""
    return f"CQ Q1AW {_grid_locator(index)}"


# ── Manifest construction ────────────────────────────────────────────────────────────

def build_signal_population(seed: int = SEED) -> list[dict]:
    """Build the 2,400-trial signal-bearing population (12 cells x 200 trials).

    Deterministic: strata are fixed module constants, iterated in fixed order (tuples,
    never dict/set), and the "random" offset-class draws come from a single
    np.random.default_rng(seed) consumed in a fixed, reproducible sequence.
    """
    rng = np.random.default_rng(seed)
    trials: list[dict] = []
    grid_combos = [(f, t) for f in FREQ_OFFSETS_HZ for t in TIME_OFFSETS_S]  # 81, fixed order

    trial_index = 0
    for snr_db in SNR_STRATA_DB:
        for offset_class in OFFSET_CLASSES:
            for i in range(N_PER_CELL):
                if offset_class == "grid":
                    freq_offset_hz, time_offset_s = grid_combos[i % len(grid_combos)]
                else:  # "random"
                    freq_offset_hz = float(rng.uniform(-1.5, 1.5))
                    time_offset_s  = float(rng.uniform(-0.039, 0.039))

                trials.append({
                    "trial_index": trial_index,
                    "cell": f"snr={snr_db:+.0f}_class={offset_class}",
                    "snr_db": snr_db,
                    "offset_class": offset_class,
                    "freq_offset_hz": freq_offset_hz,
                    "time_offset_s": time_offset_s,
                    "coarse_freq_hz": F_LATTICE_HZ,
                    "coarse_time_offset_s": T_LATTICE_S,
                    "message": message_for_trial(trial_index),
                    "render_seed": seed + 1 + trial_index,  # distinct AWGN realisation per trial
                })
                trial_index += 1
    return trials


def build_noise_population(seed: int = SEED) -> list[dict]:
    """Build the AC-3 pure-noise-only population (task 3.4), n=N_NOISE trials.

    No injected signal; `coarse_freq_hz`/`coarse_time_offset_s` are drawn (deterministically,
    same rng discipline as above) across a broad band so AC-3's uniformity test samples the
    refiner's behaviour across the search space, not one fixed corner.
    """
    rng = np.random.default_rng(seed + 1_000_000)  # offset from the signal-population stream
    trials: list[dict] = []
    for i in range(N_NOISE):
        coarse_freq_hz = int(round(rng.uniform(*NOISE_FREQ_BAND_HZ)))
        coarse_time_offset_s = float(rng.uniform(*NOISE_TIME_BAND_S))
        trials.append({
            "trial_index": i,
            "coarse_freq_hz": coarse_freq_hz,
            "coarse_time_offset_s": coarse_time_offset_s,
            "render_seed": seed + 2_000_000 + i,
        })
    return trials


def per_cell_counts(trials: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for t in trials:
        counts[t["cell"]] = counts.get(t["cell"], 0) + 1
    return counts


# ── PCM rendering (on-demand, from the manifest) ─────────────────────────────────────

def render_signal_pcm(trial: dict) -> "np.ndarray":
    """Render one signal-bearing trial's PCM (float32, 180,000 samples @ 12 kHz)."""
    from synth import encoder  # noqa: PLC0415 -- lazy, mirrors siggen.py design D-5

    true_freq_hz = trial["coarse_freq_hz"] + trial["freq_offset_hz"]
    true_dt_s    = trial["coarse_time_offset_s"] + trial["time_offset_s"]

    clean_or_noisy = encoder.encode_message(
        trial["message"],
        base_freq_hz=true_freq_hz,
        dt_s=true_dt_s,
        snr_db=trial["snr_db"],
        seed=trial["render_seed"],
        sample_rate_hz=SAMPLE_RATE_HZ,
    )
    pcm = np.asarray(clean_or_noisy, dtype=np.float32)
    assert pcm.shape == (BUFFER_SAMPLES,), pcm.shape
    return pcm


def render_noise_pcm(trial: dict) -> "np.ndarray":
    """Render one AC-3 pure-noise trial's PCM (no injected signal)."""
    from synth.channel import noise_sigma_for_snr  # noqa: PLC0415

    rng = np.random.default_rng(trial["render_seed"])
    # Arbitrary reference sigma: a unit-amplitude signal at 0 dB SNR in the 2500 Hz
    # reference band (matches the synth's own AWGN convention -- see channel.py).
    dummy_signal = np.ones(BUFFER_SAMPLES, dtype=np.float64)
    sigma = noise_sigma_for_snr(dummy_signal, snr_db=0.0, sample_rate_hz=SAMPLE_RATE_HZ)
    noise = (rng.standard_normal(BUFFER_SAMPLES) * sigma).astype(np.float32)
    return noise
