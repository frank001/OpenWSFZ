# CS-MAP: what the crowded signals lean misses look like (data on disk only)

**To:** QA (Engineer may run it as a QA peer)
**From:** Architect, 2026-11-26
**Why:** LC-BASE (`qa/rr-study/results/2026-11-26-lc-base/lc-base-result.md`, QA `d6d63eee`) showed that the room left is crowded signals: a WSJT-X decode with another one within ±50 Hz is missed a median 3.1 times as often as an isolated one at the same SNR, and most misses are stronger than −15 dB. Before choosing what to change in the decoder, we need to know **how** those misses are crowded: how close the neighbour is, how much stronger, and whether lean decoded the neighbour.
**Approved:** Product Owner, 2026-11-26 ("both at once": this alongside DR-3).
**Process:** a measurement. **No replay, no build, no code change**: it uses LC-BASE's run data only. No bars. If something cannot be done from the data on disk, say so and skip it.

---

## 1. Input

- LC-BASE's lean (L) and classic (C) runs on **H40** and **H20** (240 cycles each), and **S40** (170 cycles, the reused A6 and L5 runs): the per-row files under `D:\Projects\claude\_qa-scratch\lc-base\` and DR-0/DR-2e's scratch folders, and each night's `wsjt-x/ALL.TXT`.
- The match rule is LC-BASE's (same text, same cycle, within 10 Hz, one-to-one).
- 🔒 HK-037: message text is read only inside the function that pairs rows; only numbers leave it.

## 2. Per WSJT-X decode (computed by code)

For every WSJT-X decode **T** in a slice, find its **nearest neighbour N**: the other WSJT-X decode in the same cycle with the smallest |Δf|, where Δf = f(N) − f(T). Record:

| Field | Definition |
|---|---|
| `dF` | Δf in Hz, signed |
| `dSNR` | SNR(N) − SNR(T), WSJT-X's SNR field |
| `dDT` | DT(N) − DT(T), seconds |
| `n50` | number of other WSJT-X decodes within ±50 Hz of T |
| `T_by_L`, `T_by_C` | was T matched by L / by C |
| `N_by_L` | was N matched by L |
| `N_batch_L` | if so, the batch L published it in (1 = round 0, 2 = rounds 1 to 3, 3 = XC) |

## 3. What is reported (per slice, counts and shares only)

Only **crowded** T (`n50` ≥ 1). For each table: the number of T, and the share **missed by L**; the same for C in a second column.

1. **By `|dF|`:** < 6.25 Hz (inside one tone spacing), 6.25 to 12.5, 12.5 to 25, 25 to 50.
2. **By `dSNR`:** neighbour weaker by more than 3 dB; within ±3 dB; stronger by 3 to 10 dB; stronger by more than 10 dB.
3. **By `N_by_L`:** neighbour decoded by L (split by `N_batch_L`) or not.
4. **The two-way table `|dF|` × `dSNR`** for L only: count of T and share missed.
5. **By `|dDT|`:** < 0.16 s (one symbol), 0.16 to 0.5 s, > 0.5 s.
6. **By `n50`:** 1, 2, 3 or more.

Plus one line per slice: **of the crowded T that L missed, the share whose nearest neighbour L did decode.** That one number decides between the two main directions:
- **high** ⇒ lean finds the neighbour but does not recover T after subtracting it: work on the subtraction and the retry rounds
- **low** ⇒ lean loses both: work on finding and separating two overlapping signals in the first pass

## 4. Close-out

Result `qa/rr-study/results/2026-11-26-lc-base/cs-map-result.md` (beside LC-BASE), in LC-BASE's format; figures optional. The Architect then proposes the first decoder change to the Product Owner from §3.

## 5. The Architect's expectations (priced, written before the run; scored in the ledger)

| # | Prediction | P |
|---|---|---:|
| CM-1 | On H40 and H20, more than half of the crowded T that L missed have their nearest neighbour decoded by L | 0.75 |
| CM-2 | On H40 and H20, in more than half of those misses the neighbour is stronger (`dSNR` > +3 dB) | 0.65 |
| CM-3 | L's miss share is highest at `|dF|` < 12.5 Hz and falls with `|dF|`, on all three slices | 0.55 |
| CM-4 | C's miss shares follow L's within 5 pp in every `|dF|` band on H40 and H20 (the same structure for both engines) | 0.60 |
