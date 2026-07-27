# D-001: audit of QA's Q1–Q4 report — no defects found, two residuals noted

**Author:** Architect, 2026-07-27 (18:16 UTC, `date -u`, per HK-017). **For:** QA, and the Captain (§4).
**Audits:** `2026-07-27-1812-qa-to-architect-q1-q4-actioned.md`.
**Verdict: all four actioned correctly. Both dev-tasks are cleared for a Developer session.**
Two residuals in §3, neither blocking.

---

## 1. What I verified, and how

Per HK-018 I checked the load-bearing claims against the code rather than reading the report. Every
claim below was traced to a file and line, not accepted.

| claim | check | result |
|---|---|---|
| Q3: commit exists, tree clean | `git log`, `git status` | `7c90638` present; **working tree clean**. The 679 uncommitted insertions are gone. |
| Q1: dev-task exists | `ls dev-tasks/` | Both Q1 and Q2 dev-tasks present |
| Q2: three of five getters are sized to the *exact* expected count | `Ft8LibInterop.cs:304, 323` | **Confirmed.** `MaxPass0Candidates = 600`, `MaxDecodePasses = 2`. A blanket "throw when `n == capacity`" would fire on **every production cycle** for the three pass-sized getters |
| Q2: an independent, non-`MaxPass0Candidates`-bounded pass-0 count exists | `ft8_shim.c:1532–1534` | **Confirmed.** `ncands = ftx_find_candidates(&mon.wf, pass_max_cands, …)` then `tls_candidate_counts[pass] = ncands` — set from the native return **before** any managed copy-out |
| Q1: the throw must guard `enable == true` only | `Ft8Decoder.cs:160, 402` | **Confirmed.** `private volatile bool _candidateDiagLlrCaptureEnabled` (no initialiser → `false`), and `:402` calls unconditionally every cycle. A blanket throw would have broken **every decode on every shipped binary** |
| Q1: the throw propagates uncaught | `Ft8Decoder.cs:425` | **Confirmed.** The decode path's only catch is `catch (NativeAccessViolationException)`; the `catch (Exception ex)` at `:486/:507` are post-decode advisory bycatch, not in the path |

### 1.1 The Q2 guard design — traced through both regimes

This was the claim most worth checking, because a cross-check counter that is itself capped would
make the guard silently inert. It is not:

| build | `tls_candidate_counts[0]` | diag capture returns | guard |
|---|---|---|---|
| Shipped (native `K_MAX_CANDIDATES` = 140) | ≤ 140 | ≤ 140 | never `== 600` → **correctly silent** |
| Study build (native cap 2000) | **2000** | **600** (managed cap) | `600 == capacity` **and** `2000 > 600` → **correctly fires** |

The counter is bounded by the *native* cap and the capture by the *managed* one, which is exactly the
asymmetry the guard needs. The design is sound.

### 1.2 Two things QA caught that I would otherwise have raised

Worth naming, because both would have failed late and confusingly:

- **`/EXPORT:ft8_get_shim_capabilities` added to `rebuild_shim.bat:41–44`.** A new export missing from
  the Windows link list produces a DLL where the function silently isn't there — discovered at
  runtime, on one platform only.
- **"Rebuild both shipped binaries" is in the task body and the acceptance criteria.** Bumping the
  header without rebuilding the committed Windows DLL would make the ABI check reject it and break
  every decode. The dev-task even turns this into a deliberate test (verify the mismatch throws
  first, *then* rebuild).

### 1.3 The mock observation closed properly

My 17:31 note flagged that all eight test files touching `GetLastCandidateLlr174` use **mocks** of
`IFt8NativeInterop`, so a green suite proves nothing about the native surface. Q1's acceptance
criteria now carry it as a requirement — *"New tests added against the real (non-mock) interop, not
just the eight mock-based files"* — pointed at `Ft8LibInteropTests.cs:168–210` as the pattern. That is
the right way for an audit finding to land: as a criterion, not a comment.

## 2. QA's one deviation from my spec — accepted, with the reasoning corrected slightly

My 17:38 ruling said the throw should fire *"at the moment the workflow asks."* QA placed it in
`Ft8LibInterop.SetCandidateDiagLlrCapture`, so it fires on the **first decode cycle after** a harness
calls `Ft8Decoder.SetCandidateDiagLlrCapture(true)`, not at the call itself.

**Accepted.** Firing at the ask would mean putting the capability query on `IFt8NativeInterop`, which
means updating all eight mocks for a guard none of them exercise — churn for no coverage. And the
intent is met regardless: `:402` runs **before** `:419`'s `GetLastCandidateLlr174()`, so **no cycle of
zeros is ever collected.** That was the actual harm; it is prevented.

QA flagged this for a second look and was right to. The reasoning holds.

## 3. Two residuals — neither blocking

**3.1 A harness that enables the flag and never decodes gets no error.** The throw is on the decode
path, so a setup-only workflow that enables capture and then exits sees nothing. Trivial in practice
— any workflow wanting LLR data decodes — and not worth interface churn to close. Noted so it is not
rediscovered as a surprise.

**3.2 The committed macOS `.dylib` is a stale placeholder, and this bump makes it staler.**
`libft8.version.txt` records that CI rebuilds Linux and macOS from `ft8_shim.c` on every push, but
that **the macOS staleness check is `continue-on-error`** — a stale placeholder produces a warning,
not a failure. In the normal flow CI auto-commits a 20260036 dylib and this is a non-issue. If that
job ever fails quietly, a macOS consumer gets a hard `InvalidOperationException` from `LoadAndVerify`.

This hazard **already exists at 20260035** and is not introduced by Q1 — but it is precisely the
class of silent, one-platform, warning-not-error failure this project keeps getting caught by. **Watch
item, not a task:** confirm the macOS dylib actually lands at 20260036 after the Developer session
pushes, rather than assuming the warning was benign. No macOS consumer exists today, which is why
this is a note and not a blocker.

## 4. Status

- **Q1 and Q2 dev-tasks are cleared for a Developer session.** I found nothing to change in either.
- **Q3 is closed** — tree clean, work in history at `7c90638`.
- **Q4 stands** — R.3 held.
- **No push, no merge** (HK-010/HK-014); **no `pre_merge_check.py`** (HK-006, Captain's trigger).
- **Still owed by me: only the R.3 replacement design.**

One observation for the record. This is the first document in today's thread where I audited a
substantive piece of work and found nothing to correct. Given the day's rate — six self-corrections,
five of them mine — that is worth stating plainly rather than hunting for a finding to justify the
audit. QA's own HK-018-style check in §3 of its report (reading all five getters *before* applying a
blanket rule, and finding it would have thrown on every production cycle) is the same discipline the
rule was written for, applied a couple of hours after it was written.

## 5. Cross-references

- `2026-07-27-1812-qa-to-architect-q1-q4-actioned.md` — the report audited here.
- `2026-07-27-1752-architect-to-qa-consolidated-handoff.md` §4 — the four tasks.
- `2026-07-27-1738-architect-version-correction.md` — the design Q1 implements; §2 above notes the one
  accepted deviation.
- `dev-tasks/2026-07-27-d001-shim-version-correction-and-capabilities.md` — Q1, cleared.
- `dev-tasks/2026-07-27-d001-max-pass0-candidates-truncation-guard.md` — Q2, cleared.
- `src/OpenWSFZ.Ft8/Native/ft8_shim.c:1532–1534` — the independent counter §1.1 rests on.
- `src/OpenWSFZ.Ft8/Interop/Ft8LibInterop.cs:304, 323` — the two capacities §1 checks.

---

*Per HK-015 Architect → QA. Per HK-014 committed locally, no push. Per HK-011 this audit made no
`src/` or native edits — reads only.*
