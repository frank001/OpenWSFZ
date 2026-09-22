# Endurance-supervisor dry runs, 2026-09-22 — provenance note

Two short supervised dry runs validated `run_endurance.py`/`endurance_supervisor.py`'s
mechanics (PRECHECK, forced-kill-and-restart, TEARDOWN, orphan check, the standard gatherer,
an ANOVA smoke test) against the real daemon and WSJT-X. Captain's go confirmed directly each
time (HK-033); station touched for ~2.5–10 minutes total.

**Build used: `qa/live-gap-map` HEAD, NOT `decoding_improvement`.** At the time of these runs
the Captain had not yet ruled on which branch is the standard build source (raised by the
Architect reading commit `85c43a77`). Built via `tools/publish_selfcontained.py --rid win-x64`
from this worktree's then-current HEAD:

| field | value |
|---|---|
| Branch | `qa/live-gap-map` |
| Commit | `85c43a77` (run 1) / `c1a27a67` (run 2) |
| `libft8.dll` SHA-256 | `91997e38038d9328edcb49cd1e8661706d0092ed2c73e808094c96c3980ad2c6` |
| Shim | **`20260051`** |
| Daemon version | `0.49` |
| `src`/`native` | unchanged since `433925b0` (confirmed via `git log`), so both runs' commits carry the identical compiled decoder despite differing QA-doc commits |

**Captain's ruling (2026-09-22, relayed via Architect, after these runs):** standard endurance
runs build from **`decoding_improvement`** (currently shim `20260054`, with the Stage 1
suppression), not `main`/`qa/live-gap-map`. `endurance_supervisor.py`'s PRECHECK now asserts
`build_provenance.json`'s recorded branch equals `decoding_improvement` by default (commit
`<next commit after this note>`) and refuses to arm otherwise — these two dry runs would **not**
pass that check today, which is correct: they were never claiming to be a standard run.

**Consequence for these two runs, unchanged from when they happened:** both are test runs, not
endurance sessions. Neither was added to `anova_common.py`'s Section 4 historical table
(`--no-historical` was passed both times), and neither should be, regardless of which branch
policy is current — that exclusion was never about which branch, only about run purpose.

Gathered artefacts (gitignored, under `artefacts/`): `20260922_1924_endurance_run-gathered/`
(run 1, TEARDOWN/gatherer failed, fixed and re-validated in run 2) and
`20260922_1937_endurance_run-gathered/` (run 2, full lifecycle passed automatically).
