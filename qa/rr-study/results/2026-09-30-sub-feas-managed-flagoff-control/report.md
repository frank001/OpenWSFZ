# SUB-FEAS merge-gate control (spec 5g): flag-OFF managed `DecodeAsync`, `origin/main` vs the merge head

**Engineer → Architect, QA.** Run 2026-09-30, **17:20:09Z to 17:23:50Z** (`control.log`). Owner: Engineer (Captain: *"let the engineer do the 15 minute run"*).
Spec: `qa/rr-study/2026-09-30-0641-architect-to-qa-spec-sub-feas-speed-redesign.md` §5g on `arch/subtraction-feasibility` @ `a6edd0ae`.

## Verdict: PASS, 161 / 161 cycles identical, in order

`flagoff_managed_compare.py` printed (`compare.json`, exit 0):

```json
{ "cycles": 161, "identical_in_order": 161, "decodes_main": 3842, "decodes_head": 3842,
  "mismatching_cycles": [], "PASS": true }
```

## What was compared

| | `main` | SUB-FEAS merge head |
|---|---|---|
| Commit (clean detached checkout) | `c3f423625063e38a87a7852a6bcf5223a65058e9` (`origin/main` tip, fetched before the run) | `247ac391d11f6a7474fd4c42ae4815a23e09fd45` (code-identical to `319911ee`: `git diff --name-only 247ac391 319911ee -- src native` is empty) |
| `libft8.dll` SHA-256 (from the build output) | `91997e38038d9328edcb49cd1e8661706d0092ed2c73e808094c96c3980ad2c6` (no pin exists for main) | `ee00d118523ee2160750736225c67d8a056193908d168ed9a6ec3375ff990e4c` (**matches the required pin**) |
| Shim version printed by the harness | `20260051` | `20260056` |
| `OpenWSFZ.Ft8.dll` SHA-256, first 16 | `0ce1559c1f4c151d` | `0e6357ed4863017f` (different managed build, so the two builds really differ) |
| Harness build | `Replay81.csproj -c Release -p:RepoRoot=<checkout>` | same, plus `-p:HasSubfeas=true` |

- **Harness:** `replay81` from `qa/sub-feas` @ `70c01fc9` (`Program.cs` sha256 `0b15076c…`, `Replay81.csproj` `f896d7aa…`). Compare script `b6e1efe5` (`6fe90c64…`). Neither was modified.
- **Path:** public `Ft8Decoder.DecodeAsync`, `--mode off` (flag untouched; on the head build the harness calls `SetSubtractionEnabled(false)`, i.e. OFF). **One fresh process per (build, run)**, six processes in all, the same three runs and the same order on both builds. One warm-up cycle per process (discarded, not compared).
- **Input:** QA's `e1_derived_selection.json` (shape `runs/<run>/{warmup, E1}`; 49 + 77 + 35 = 161 stamps), generated from `e1_selection.json` (SHA `f58c0c7b…`). WAVs read in place, read-only, from QA's `artefacts` (nothing copied). I did not recompute the selection SHA myself; I rely on QA's statement that the derived file is generated with both source SHAs asserted.
- **Compared fields:** `freqHz`, `dt`, `snr`, ordered per cycle (the harness outcome line is `stamp,kind,idx,freqHz,dt,snr`). No message text and no text hash exists anywhere in the outputs (`--outcome-text-hash` and `--wsjtx-alltxt` were not passed). HK-037 holds.

## Checks beyond the script (the script alone would pass vacuously)

The compare script matches per stamp, so a cycle missing from both outcome files would pass. To rule that out I also checked, for **each** build:

| Check | `main` | head |
|---|---|---|
| CSV rows | 161 | 161 |
| rows with a non-empty `exception` column | 0 | 0 |
| cycles with zero decodes | 0 | 0 |
| row order equals the selection's `E1` order | yes | yes |
| outcome lines (all six fields) | 3842 | 3842 |
| bytes on stderr | 0 | 0 |

The three outcome files are **byte-identical** between the builds (`cmp`, one per run). That is stronger than the script's predicate, which compares only `(freqHz, dt, snr)`: the `kind` and `idx` fields are identical too.

## Limits (what this does and does not show)

- It closes the one missing link named in §5g: `main`'s managed decode path vs SUB-FEAS's, flag OFF, on the 161 real cycles. It says nothing about flag ON, speed, or any other corpus.
- 161 cycles from three runs of one real corpus. Every cycle decoded at least one message, so the zero-decode case (quiet cycles) is not exercised.
- The two `libft8.dll` files differ (as expected: SUB-FEAS changed native code). Identical outcomes across them on these cycles is what the flag-OFF native chain (earlier controls) predicted; this run did not re-test the native path on its own.
- Nothing ran on the station. The run overlapped QA's Test B replay (timing-insensitive), which only slows builds.

## Reproduce

`run_control.sh` (this directory) is the exact script; it needs the two detached checkouts (`git worktree add --detach <dir> c3f42362` and `247ac391`), the harness files from `70c01fc9`, and QA's selection and WAV root. Outputs went to the Engineer's gitignored `artefacts/sub_feas_control/`. Teardown: the script's processes had exited; orphan check for dotnet processes of mine: none (one `dotnet` process was found and identified as QA's Test B).
The two detached worktrees `C:\Users\Frank\w-eng-ctl-main` and `w-eng-ctl-head` are left in place until told to remove them.
