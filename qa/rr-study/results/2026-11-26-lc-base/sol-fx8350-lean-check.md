# Quick check: the lean decoder on older hardware (sol, AMD FX-8350)

**Date:** 2026-11-26 · **Author:** QA · **Asked by:** the Captain ("sol is online, do a quick check with the lean decoder to see how it behaves on older hardware"). A quick check, not a measurement campaign: one run per engine, no bars. Aggregates only (NFR-021): numbers from the harness's per-cycle files; no message text left the PC.

## The machine

`sol`: Gentoo Linux 6.6, **AMD FX-8350** (Piledriver, 2012; 4 modules / 8 logical processors, 4.0 GHz max, 8 MiB L2, 8 MiB L3), 32 GB RAM, idle at the start (load 0.5, nothing of ours running). Instruction sets: AVX, FMA/FMA4, SSE4.2; **no AVX2**. The reference PC of the other measurements is a 16-logical-processor desktop.

## What was run

- **Build:** `main` at `546ad125` (the lean chain, PR #291) with the replay harness `Ft8.FitProbe` published for `linux-x64` (self-contained, `HasLean`), and the **CI-built Linux `libft8.so` of `main`** (shim 20260078, SHA-256 `22c8cb8f40a45c1d68a2df2f32485d221fc36d5219d8131e1d7d80b14885c644`, asserted equal on sol after the copy). That is the file a Linux user receives, built generic (`gcc -O2`, no `-march`); **it contains no AVX, AVX2 or FMA instruction** (objdump: 0 `ymm`, 0 VEX-encoded), so the FX-8350 cannot hit an illegal-instruction fault.
- **Audio:** the first **40 cycles of slice S40** (40 m night `20261114_2312`, `261115_072930` onward; the warm-up cycle before them; the same WAVs as LC-BASE), copied to sol. The decode counts were compared with the Windows lean run of the same cycles (DR-2e's 16-thread run); no WSJT-X file was copied, so no rate against WSJT-X is computed here.
- **Lean:** `--engine lean --lean-threads 8 --effort normal` (8 threads = `min(8 logical processors, 16)`, i.e. what the **auto default resolves to on this CPU**), the flags of LC-BASE's arm L otherwise. **Classic:** `--engine classic --threads 8`, the first 20 of the same cycles (a shorter run for comparison). Both on the otherwise idle machine, one after the other.

## Result

| | Lean, 8 threads (40 cycles) | Classic, 8 threads (20 cycles) | Reference: lean on the Windows PC, 16 threads (same 40 cycles) |
|---|---:|---:|---:|
| Last batch published, median | **4.85 s** | 11.77 s | 1.53 s |
| p95 | **6.54 s** | 12.78 s | 1.98 s |
| Maximum | 7.25 s | 12.78 s | 2.08 s |
| CPU per cycle (process, user + system) | **31.4 CPU-s** | 45.7 CPU-s | 13.4 CPU-s (whole S40) |
| Peak memory | 636 MB | 580 MB | not measured |
| Cycles abandoned / native errors | 0 / 0 | not scored here | 0 / 0 |

The cycle is 15 s long. On the same 20 cycles the lean engine's last batch (median 4.65 s, p95 6.15 s) came **2.5 times sooner** than classic's, and classic's 20 cycles had 7 whose last batch was later than 12 s (none later than 15 s), leaving it about 2 to 3 s of slack on an otherwise idle machine; lean leaves about 8 s.

## Does it decode the same?

**Yes, exactly, on all 40 cycles.** Per cycle, the number of decodes, results, rounds run, fit-skipped signals, abandoned flag and error code on sol equal the Windows 16-thread run's: 40 of 40 for each of the six fields. That is a different operating system, compiler (gcc against MSVC), CPU generation (no AVX2, different FMA handling) and thread count (8 against 16). The decodes of the lean engine do not depend on the platform in this check, which the numeric goldens could not promise (a golden holds only on the platform that recorded it).

## Reading

- **On a 2012-era 8-thread CPU the lean engine works and stays well inside the cycle**: median 4.9 s, worst 7.3 s of 15 s. It uses about **2.3 times the CPU** of the Windows PC (31.4 against 13.4 CPU-s per cycle; the fit CPU 21.8 against 8.5 CPU-s per cycle) and about 600 % of the 800 % the 8 threads can offer.
- **Classic on the same machine is close to the edge:** a last batch at 11.8 s median and 12.8 s worst, on an idle PC. A daemon that also captures audio, serves the web page and runs the QSO logic on such hardware would have little left. The lean engine as the default (DR-3) is the safer choice on older hardware.
- The auto thread default resolved to 8 here and was the setting measured; fewer threads were not tried (a quick check). The Windows PC's table (2 to 16 threads) shows the wall time rises steeply below its logical-processor count.

## Not claimed

One run per engine, the machine idle, 40 and 20 cycles of one night (a quiet-to-average stretch of 40 m, 32 to 34 decodes per cycle). No decode rate against WSJT-X (no WSJT-X text copied). No real-time soak with audio capture, and no measurement on a machine that is also doing other work. The classic run is shorter and only a comparison.

## Files

- Run data (numbers only; no message text in these files): `sol:~/lc-sol-check/{out8,outC}/` and the copies `D:\Projects\claude\_qa-scratch\lc-sol\{out8,outC}` (`run.csv`, `lean.csv`, `time.txt`). Harness build `D:\Projects\claude\_qa-scratch\lc-sol\bin_linux`. The WAVs and the harness stay on sol in `~/lc-sol-check` (small, reusable for a later run).
