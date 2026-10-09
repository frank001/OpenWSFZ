# SUB-FEAS: population construction stalls at §3's isolation predicate — escalating before ROW 0

**QA, 2026-09-27 19:11Z** (`date -u`, HK-017). Branch `qa/sub-feas` (from `origin/main`).
Not a refusal (HK-025(k) assessment on record: no grounds to refuse the spec as a whole),
and not a ROW 0 result. This is a §3 population-construction finding that blocks every
downstream row (0d, 0f, 0g, 0h, W* selection, Stage 1 all consume P/A/B), surfaced before
spending the compute on ROW 0 rather than after.

## What I built

`qa/rr-study/sub-feas/{common,corpus}.py`: ALL.TXT parsing (numeric fields only, HK-037),
cycle indexing from `cycle-archive.csv`, and §3's population filter (SNR ≥ 0, isolated ≤60 Hz
in-cycle across both programs' `ALL.TXT`, re-encodable-standard via the pinned DLL's
`ft8_encode_message`). Pinned DLL copied from `artefacts/20260927_1327_gap-locate/bin/libft8_C3.dll`
(sha256 `38a21f84…589a1cba`, matches the spec's pin) into this arm's own `artefacts/sub-feas/bin/`.

## What happened

Running it on the real corpus (47,212 OWS `ALL.TXT` rows, 2,884 cycles):

| filter | rows removed | rows remaining |
|---|---:|---:|
| start | — | 47,212 |
| SNR ≥ 0 | 35,685 | 11,527 |
| isolated ≤60 Hz (either program) | 11,520 | 7 |
| re-encodable standard | 3 | **4** |

`|P|` = 4 total, before even splitting A/B/anchor. ROW 0d's bar is `|P_A|`, `|P_B|` each ≥ 1,000.

## Root cause (verified, not assumed)

Of the 11,527 SNR≥0 rows, **11,517 (99.9%)** have a WSJT-X decode in the *same cycle* within
**5 Hz** (median distance **1.0 Hz**) of OWS's own reported frequency. That is not third-party
co-channel interference — at those distances it is overwhelmingly the **same physical
transmission**, logged independently by both decoders. (Numeric-only check, HK-037: frequency
deltas only, no message text compared.)

§3's isolation predicate as written — "no other decode from **either** program's `ALL.TXT` in
the same cycle within 60 Hz of freq" — counts that corroborating twin as "another decode
occupying nearby spectrum." Since any signal strong enough to clear SNR≥0 for OWS is also very
likely to be decoded by WSJT-X (the whole R&R record shows large decode-set overlap), the
predicate is dominated by this self-collision, not by genuine congestion. For comparison, the
own-chain-only collision rate (a different, distinct OWS decode within 60 Hz) is **24%** —
plausible real congestion for a 12h40m 40m corpus, an order of magnitude lower than the
cross-program rate.

I did not patch this myself — changing what "isolated" means changes the population's
definition, which is the Architect's call, not something to improvise mid-run on a
pre-registered mechanical check (HK-021/HK-025 discipline).

## Options, not a recommendation of one

1. **De-twin before the co-channel check**: pair each OWS row with its nearest WSJT-X entry in
   the same cycle; if that pairing is inside some small tolerance (needs a pre-registered
   number — the data above suggests same-transmission pairs cluster under ~5 Hz and distinct
   spectrum sightings are essentially absent below ~40 Hz, but I have not characterised the
   gap/bimodality rigorously), treat it as the same transmission and exclude it from the
   isolation check; keep the 60 Hz rule for everything else.
2. **Isolation against OWS's own `ALL.TXT` only**, dropping the cross-program union — a
   corroborating WSJT-X decode of the same signal isn't extra RF energy contaminating the
   residual; only a genuinely separate transmission is. (Own-chain-only gives 24% collision on
   SNR≥0 rows, i.e. plausibly close to ROW 0d's bar after the other filters — untested until a
   ruling lands.)
3. **The predicate is intentional as written**, and ROW 0d's real answer is FAIL/STOP: this
   corpus's isolated-strong-signal population is far smaller than hoped, full stop, no ROW 0a–0c
   run needed.

## Not run yet

ROW 0a–0h, W* selection, Stage 1 — all blocked on this. No result file, no board update. Held
on `qa/sub-feas`, nothing pushed (HK-033/HK-014).
