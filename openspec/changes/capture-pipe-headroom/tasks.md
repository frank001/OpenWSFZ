## 1. Tests first (each must be able to fail)

- [ ] 1.1 `DefaultStartInfo`: the argument list is exactly `-D <device> -f FLOAT_LE -r 12000 -c 1 -t raw --period-time=20000 -`, with `LC_ALL=C` in the environment and both redirects on. (Compare with the list in `ArecordStderrTests` for the base commit: only `--period-time=20000` is new.)
- [ ] 1.2 Refusing seam: the pipe call fails with an errno; a Warning containing the errno is logged, capture completes, and **the chunks yielded are byte-identical** to those of a run whose seam accepts.
- [ ] 1.3 Accepting seam: an Information line with the requested (1,048,576) and granted sizes is logged once; no other effect.
- [ ] 1.4 Real pipe, Linux only (skipped elsewhere): with the real P/Invoke on a real pipe the granted size is at least 1,048,576 or a Warning is logged; the test must not hang when `/proc/sys/fs/pipe-max-size` is lower.
- [ ] 1.5 A stream that is not a pipe (for example a `MemoryStream`-backed fake process): the call is not attempted, a Warning is logged, capture is unaffected.
- [ ] 1.6 The existing `ArecordStderrTests`, `CaptureLossCounterTests` and the framer tests pass **unchanged** (show the unchanged files in the diff stat).

## 2. Implementation

- [ ] 2.1 `ArecordAudioSource`: the pipe call after `process.Start()` (Linux only, Decisions 1-5), behind the seam of Decision 6.
- [ ] 2.2 A small internal interop type for `fcntl` with the two named constants (Decision 2).
- [ ] 2.3 `DefaultStartInfo`: add `--period-time=20000` (Decision 7); nothing else.
- [ ] 2.4 Nothing in `CaptureManager`, `CycleFramer`, the web layer, `native/`, Windows (WASAPI) or macOS (`sox`); `git diff --stat` confirms.

## 3. Verification

- [ ] 3.1 `dotnet build`, `dotnet test` green; `openspec validate --all --strict`.
- [ ] 3.2 The Developer does not push, merge or run `pre_merge_check.py` on its own initiative. QA reviews against section 1 (including byte identity with the call refused), runs the mutation checks and the full suite on a clean worktree; the Captain signs off the merge (HK-010).
- [ ] 3.3 After the merge: QA builds the series' fresh B2 + `main` merge with provenance, runs one sweep and reports the capture counters and the residual-pass timing (median <= 4 s, none abandoned) before the series goes on.
