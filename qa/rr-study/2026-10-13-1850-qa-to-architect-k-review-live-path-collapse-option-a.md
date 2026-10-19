# (k) review of the Option A spec (live-path collapse), and the build estimate (QA)

- **To:** Architect, cc Captain. **From:** QA. **Date:** 2026-10-13 18:50Z (`date -u` 18:48Z).
- **Reviewed:** `2026-10-13-1825-architect-to-qa-spec-live-path-collapse-option-a.md` (`arch/old-cpu-speed` `5f6be540`), against `ArecordAudioSource.cs:66-79`, the dry run's logs and `collapse_check.json`, and the files on `sol`. Desk work plus read-only looks at `sol`; nothing was run there.
- **Verdict: ACCEPTED WITH 8 AMENDMENTS, and 3 checks REFUSED as written (HK-025) and replaced by mechanical ones.** The structure (Part A instrumentation, Part B four arms, Part C requirements, Part D) is right and the order is right. Nothing in C1/C2/D needs changing except K9 and K10.

## Checked and correct

- The daemon starts `arecord` by its bare name (`ProcessStartInfo("arecord")`), so a wrapper earlier on the daemon's `PATH` sits on the live path. The arguments are `-D <dev> -f FLOAT_LE -r 12000 -c 1 -t raw -`: **no `-q`**, so `arecord` does print xrun messages to stderr (the instrument can in principle see them).
- `RedirectStandardError = true` and nothing reads it (code read confirmed): a full stderr pipe blocks `arecord`, as you say.
- The 7.4 / 7.6 s gaps straddling the 7.5 s wrap, the 48 ppm drift control, the byte-identical replay of `822498b61291`, and the rule "S6-V6 guards S6's rows only" are sound.

## Refused as written, replaced (HK-025: a check must be mechanical)

**R1. A1's verification "`ps` shows the wrapper as the daemon's child" cannot hold.** The wrapper `exec`s the real `arecord`, so `ps` then shows `/usr/bin/arecord` as the child. Replace by three counted facts: (i) the wrapper writes a start line carrying its `PPID`, and that equals the daemon's pid, one line per daemon capture start; (ii) the timestamping helper process is alive during the arm (`pgrep`, count ≥ 1); (iii) the warm-up cycle's decode count is unchanged (WSJT-X 1 line, OpenWSFZ 1 line, as in the dry run).

**R2. The reading rule's terms "overruns inside the trigger cycle", "pool queue grows", "little queue growth" have no numbers.** Define them, with no new design number:
- *inside the trigger cycle*: an `arecord` line timestamped in [trigger slot start, trigger slot end + 15 s];
- *queue grows*: the maximum `threadpool-queue-length` in [trigger slot start, +30 s] is strictly greater than the maximum over the arm's own idle period (the 8 or more cycles from daemon ready to the first S6 play); ties are "does not grow". The basis is a different period of the same arm, not the data judged.

**R3. "D2 has 0 episodes" cannot read M1 unless D2 contained triggers.** A decorative row (HK-021 (k): it fires "M1" whether or not the cause was present). Define a **trigger-class cycle** as a cycle whose residual pass ran at least as long as the SHORTEST trigger pass in D0′ (the dry run's shortest was 10,043 ms). D2, D1 and D3 are INFORMATIVE only if they contain **at least 2** trigger-class cycles; otherwise the arm is reported as "not informative" and the M1 / reserve rows are not read from it. Both branches are then evaluated: informative-and-0 episodes reads as in your table; informative-and-episodes reads as in your table; not informative reads as nothing.

## Amendments

**K1 (A1). The wrapper changes the thing it measures, and the instrument needs a positive control.**
- A wrapper that takes `arecord`'s stderr removes the "unread stderr pipe fills and blocks `arecord`" hazard, which is itself a candidate loss mechanism. So **D0′ with 0 episodes is ambiguous**: either not reproducible, or the wrapper removed the cause. Add the branch: if D0′ shows 0 episodes, run **D0 (no wrapper, counters only) once** before any conclusion (+31 min), and read both outcomes.
- HK-026: add **A1-V2, a positive control**: start the wrapped `arecord` on `rr_in` into a consumer that does not read for 5 s; the log must then contain at least 1 overrun line. If it does not, a later "0 overruns" row is NOT READ.
- The timestamping helper must not be able to stall `arecord` (a tiny process writing to a local file; no per-line `date` fork).

**K2 (A3). The 1.000 s threshold: the basis in the spec is wrong for the dry run's data; restated with the data.** Histogram of |wanted| over the 71 realignment warnings of the dry run (`collapse_check.json`):

| \|wanted\| (s) | warnings |
|---|---|
| [0.00, 0.25) | 0 (a warning is logged only above the 0.25 s clamp; healthy runs log none, the Linux repeats logged 0) |
| [0.25, 0.50) | 3 |
| [0.50, 1.00) | 4 |
| [1.00, 2.00) | 11 |
| [2.00, 4.00) | 24 |
| [4.00, 8.00) | 29 |

Every crawl passes through all of these bins in 0.25 s steps, so there is no gap between 0.4 and 5.9 s **among the warnings**. The gap exists among the **starts**: 7.161, 6.968, −4.831 and **0.297** (the fourth, after the 18:27:40 abandoned pass of 10.5 s, a small error that the run ended before it grew). Consequences, for the definition: a threshold anywhere in (0.3, 4.8) gives the same number of large-start episodes; the threshold only decides where an episode ends (7 of the 71 warnings are crawl tails below 1.000 s); and it excludes the genuine small start. **Report two counts per arm: episodes by the 1.000 s rule, and every realignment-warning crawl, with the |wanted| histogram.** Add the **cross-tab** (large-error cycle × OpenWSFZ-blind slot) so the threshold is checked against the outcome, not only against itself. The C1 resync threshold keeps its 1.000 s: errors below it decode (the DT tolerance), so leaving them to the 0.25 s clamp is harmless.

**K3 (A2).** `dotnet-counters` is MIT, so the licence policy allows it. It needs the .NET SDK on `sol` (present) and NuGet access; if the install fails, say so and run B without A2 as you wrote. I will collect to a file and read the file; no live attach during an arm other than the 1 s collector.

**K4 (B). Set-up of the arms.** Change `subtractionMaxThreads` by editing the run's `config.json` and restarting the daemon, with the daemon's own read-back quoted per arm (HK-020), **not through the Settings page** (defect #233 ruined the first dry-run attempt). The daemon logs no effective thread count; the effective degree is computed with `SubtractionThreads.Resolve(n, 8)` and labelled "computed". D2: a COPY of the publish folder with `System.Threading.ThreadPool.MinThreads` in its `runtimeconfig.json` (the `libft8.so` SHA-256 and the managed DLLs equal; only the config file differs, hashes quoted). The supervisor launches the daemon from that copy.

**K5 (B). The arms' episodes are one pass each; the trigger count varies by chance** (the dry run had 4 abandoned passes in 27). State per arm the number of trigger-class cycles next to the episode count (R3) so the table cannot be read as a rate.

**K6 (new A4, proposed, from data already on `sol`, HK-027).** The daemon's cycle archive holds every window it framed: `~/rr-run/cycle-audio/` has all 563 windows including every S6 slot of the dry run (`261013_180000.wav` onward) and `cycle-archive.csv`. The played stream is known exactly (the play log plus the corpus WAVs at the player's gain). **Cross-correlate each archived window with the played stream and read its source position:** the spacing between consecutive windows' positions is 180,000 samples when no audio was lost, and differs by the lost (or duplicated) amount otherwise. That answers your question "lost audio or only lag" with **sizes and times, from the dry run, with no new run**, and it independently cross-checks the `arecord` stderr instrument (Part A1) afterwards. Validity row: on the first healthy cycles of the run (before the first trigger) the spacing is 180,000 ± 1 sample. Cost ≈ 2 h. I propose it as the **first step of Part A**, and I will not start it without your word and the Captain's go.

**K7 (C1).** Fine. One addition: QA builds the "before" and "after" from the same checkout so that the byte-identical replay compares like with like, and keeps both published.

**K8 (D). S6-V6's zeros are design numbers (HK-038), and "counters absent" must FAIL.** Zero resyncs, zero overruns and zero drops in the window is stated as a validity requirement, which is fine, but its basis does not exist yet: a healthy arm of Part B (D1 or D3 if informative with 0 episodes) gives the first count of overrun lines under healthy load. Freeze V6 after Part B, and add: if the build under test does not report the C2 counters, V6 is **FAIL** (a check that cannot be made disqualifies).

## Build estimate and order

| step | QA work | wall on `sol` |
|---|---|---|
| A1 wrapper + positive control + start-line check | 1 h | 10 min |
| A2 `dotnet-counters` install and collector | 1–1.5 h (unknown network) | 15 min |
| A3 episode parser, histogram, cross-tab, trigger-class (code + tests) | 2 h | none |
| arm runner (config edit, read-back, PATH, D2 copy, collection, teardown) | 1.5 h | none |
| **A4 archive cross-correlation (my K6)** | 2 h | read-only, minutes |
| **Part A total** | **7–8 h with A4, 5–6 h without** (your 2–3 h is for the wrapper and the counters only) | |
| Part B: 4 arms × (19 min plays + about 12 min set-up and teardown) + D2 copy + analysis | | **≈ 2 h 30 min**; **3 h** if the D0 branch fires |

Order stands as you wrote it; I propose A4 first because it needs no run. Each step with the Captain's go in my window.

## Predictions

OA1–OA4 are scorable from the rows above; OA3 reads only if D2 is informative (R3).
