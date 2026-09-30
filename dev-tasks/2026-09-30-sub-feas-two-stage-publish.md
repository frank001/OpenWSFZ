# SUB-FEAS two-stage publish: pass-0 first, residual decodes as a second batch (Architect's Amendment 2)

**Date:** 2026-09-30
**Prepared by:** QA (HK-015: Architect → QA → Developer)
**Audience:** Developer (to execute); Captain (hand-over per HK-000, merge sign-off HK-010, push go-ahead HK-033)
**Status:** **DRAFT for hand-over (updated for the Architect's Amendment 3, `arch/subtraction-feasibility` `974a450e`: the P-5 correction, S2/S2b, the managed flag-OFF control, S1 method and S3 (g)-(j) are all accepted).** The Captain authorised the amendment ("yes, write the amendment for QA", via the Architect's §5b, `arch/subtraction-feasibility`). QA has not had a separate direct go for this hand-over; the Captain hands it over.
**Branch:** create `feat/sub-feas-two-stage-publish` **off** `feat/sub-feas-speed-redesign` (`ca0bcd9b`, Stage A). Do not branch off `main`: the base change is not merged.
**OpenSpec change:** `openspec/changes/sub-feas-speed-redesign/` on `qa/sub-feas`: spec requirements (five added), `design.md` **D9**, `tasks.md` **§13** (yours) and **§14** (QA's). `openspec validate --all --strict` is 62/62.
**No native change, no shim bump.** `libft8.dll` stays `ee00d118523ee2160750736225c67d8a056193908d168ed9a6ec3375ff990e4c`; confirm that at the end.

---

## 0. Why this exists

With the flag ON the residual pass runs **inside** `Ft8Decoder.DecodeAsync`, before the pump's single publish (`Ft8Decoder.cs` ~370-384; `Program.cs` ~858-906). So every decode, pass-0 included, reaches the operator only after the whole pass: about 15 s + 5.5 s = **20.5 s median** after the cycle starts, against the **17.36 s** deadline to answer a station heard in that cycle (#122). No speed-up reaches that (the pass would have to finish in under 1.8 s). Stage A made the pass fast enough for the cycle; it cannot make it fast enough for the operator. **Two-stage publish is required before any live use, whether or not Stage B is built.**

## 1. What you build (tasks §13)

| # | Requirement |
|---|---|
| **P-1** | Flag ON: map pass-0 and publish it as **batch 1** as soon as pass 0 returns, through exactly the pump path used today (panel, ALL.TXT, archive, filter admission, answerer, caller, external reporting). The residual pass starts **after** batch 1 is published. |
| **P-2** | Residual decodes are published as **batch 2** of the same cycle (same `cycleStart`) when the pass completes. **Nothing** is published for batch 2 if the pass is abandoned, fails, or yields no new decode. |
| **P-3** | Batch 2 is mapped exactly like batch 1 (TrimEnd, `IsPlausibleMessage`, region, worked-before, band). The text `seen` set is **per cycle**, spanning both batches. The SubtractionPass payload de-dup is unchanged. |
| **P-4** | Batch 2 goes to: the **panel** (appended, never replacing), **ALL.TXT** (appended after batch 1's lines, same stamp), **filter admission**, and the **external-reporting** channel. |
| **P-5** | 🛑 Batch 2 is **NOT** written to the QSO **answerer** or **caller** channels. The answerer keeps `_lastIdleDecodeBatch` on every idle batch (`QsoAnswererService.cs` ~657) and reads it in `TryEngageExternal` (~382): a residual-only second batch would overwrite the pass-0 snapshot and an external reply to a pass-0 station would then fail. The answerer and caller also treat every batch as a cycle. |
| **P-6** | The cycle-audio archive `TryEnqueue` runs **once**, at batch 1, with the pass-0 count. |
| **P-7** | The pump stays **serial**: no decode of the next window until batch 2 is published or the pass is abandoned. |
| **P-8** | The `Cycle {Time}: … elapsed=` line reports **time to batch 1** (flag OFF: identical to today, so the #122 series stays continuous). Record the semantic in `design.md`. The `Sub-feas residual pass:` line is unchanged (it is the R4 instrument). |
| **P-9** | **Flag OFF: exactly one batch per cycle, byte-identical** output, ALL.TXT, archive enqueue and consumer deliveries. |

## 2. What you do NOT build

- No change to `IModeDecoder.DecodeAsync` or to any current caller (tests, the §8.1 replay harness, other decoders).
- Residual decodes are **not** made available to the answerer or caller. Making them engageable is a separate change.
- No native change, no shim bump, no Stage B (that is the Captain's separate decision), no change to the fit, the deadline or the thread count.
- The flag stays OFF by default. **A first on-air flag-ON session is a new decision needing the Captain's explicit go.**

## 3. Order of work

1. **Record the API shape in `design.md` D9 before coding** (tasks 13.1): a publish callback for batch 1, or a return of both batches. The chosen entry **must be callable from a test or replay harness without the daemon pump**, or QA cannot measure acceptance rows S1 and S2.
2. Read the pump path and the consumers before changing them (see §4). Then P-1, P-2, P-3, then the consumer wiring (P-4, P-5, P-6), the serial guarantee (P-7), the elapsed semantic (P-8), and the flag-OFF proof (P-9).
3. Tests S3 (a)-(f) in code (tasks 13.10) and the four QA-proposed tests (g)-(j) (13.11). Full unfiltered `dotnet test`.

## 4. What QA verified in code at `ca0bcd9b`, and what it means for you

| Consumer | Verified | For you |
|---|---|---|
| Panel `handleDecodes` (`web/js/main.js` ~777) | **Prepends** each result as a row, never clears | Batch 2 rows appear above batch 1's rows of the same cycle; nothing is replaced. **No fix needed**; add the S3 (d) test. (The Architect's amendment said to verify and fix if needed: it is fine.) |
| ALL.TXT `AppendAsync(cycleStart, dialFreq, results)` | per publish | append after batch 1, same stamp |
| Archive `TryEnqueue(pcm, cycleStart, …, results.Count, …)` | per publish | once, at batch 1 |
| Answerer / caller | `_lastIdleDecodeBatch` overwritten each idle batch | do not send batch 2 (P-5) |
| **Manual engage (double-click)** | `POST /api/v1/tx/engage-decode` (`WebApp.cs` ~1633) takes callsign, frequency, cycle start, SNR and payload **from the browser row** and validates with `IEngagementTargetValidator`. **It does not read `_lastIdleDecodeBatch`.** | 🔴 **The Architect's stated consequence "residual decodes cannot be engaged" is true of an external (GridTracker) reply, not of a double-click.** A batch-2 row can probably be answered by double-click; but batch 2 arrives about 20.5 s after the cycle starts, after the 17.36 s slot, so what the answerer does with the pending target for the *next* window is **unverified**. **Write test (g) to characterise it**, whatever it does, and report it. Do not change the behaviour. |
| External reporting service | consumes `DecodeBatch` per batch | **Read it** and confirm it sends no cycle-level message (a clear, a status) twice for a two-batch cycle. Record the finding (13.4, test (j)). |

## 5. The pitfalls, in order of how much they will hurt

1. **The mapping state is stateful.** The `seen` text set, worked-before and region lookups are per cycle and shared by the two batches. If batch 2 is mapped with a fresh `seen`, a residual decode with the same text as a pass-0 one is published twice. Test (c) covers it.
2. **Do not overwrite the answerer's snapshot.** The simplest implementation (write the batch to every channel twice) breaks `TryEngageExternal` for pass-0 stations. P-5 exists for exactly this.
3. **The pump must stay serial and must not deadlock or drop.** The channels use `DropOldest` when full. Batch 2 must not push batch 1 (or the next cycle's batch) out of a channel it is not meant to reach; only the panel, ALL.TXT, admission and external reporting get batch 2. Test (i).
4. **The residual pass and the publish now overlap.** Batch 1's WebSocket delivery is fire-and-forget (`decodeEventBus.Publish`); the residual pass then runs 14 workers on 16 logical processors. Nothing tests delivery under that load (QA proposes a report-only row S2b), so **do not add work between "pass 0 returned" and "batch 1 handed to the pump"**. QA's acceptance row S2 will time exactly that gap: median ≤ 1.05 × the flag-OFF whole call, max ≤ 1 000 ms read per cycle against the same-session flag-OFF call (cycles where flag OFF itself exceeds 1 000 ms are excluded and counted; over 1 % excluded means "not evaluable"). A report-only row S2b times delivery of batch 1 to a WebSocket client while the residual pass runs.
5. **Flag OFF must be byte-identical.** The base change's flag-OFF control compared native DLLs only; the **managed** flag-OFF path was never exercised. This change edits exactly that path. The control (native and managed `DecodeAsync` outcome fields) is a merge gate QA runs once, at the merge (`tasks.md` 10.5/14.4); QA's S1 run records an interim managed flag-OFF comparison meanwhile. Make P-9 easy to prove: the flag-OFF code path should not go through the two-batch machinery at all if you can avoid it.
6. **The per-cycle `elapsed=` line** is the #122 series. With flag OFF it must not change by a character; with flag ON it reports time to batch 1 (P-8), which is what the operator experiences.
7. **`IModeDecoder` is a public contract** used by tests and the replay harness. Add an entry; do not change the existing one.

## 6. Tests (see `tasks.md` §13 for the full list)

S3: (a) answerer and caller receive exactly one batch per flag-ON cycle; (b) `_lastIdleDecodeBatch` after a flag-ON cycle equals batch 1; (c) ALL.TXT holds batch 1's lines then batch 2's, same stamp, no duplicate text in the cycle; (d) the panel receives two `decode` events and shows the union; (e) the archive enqueues once; (f) flag OFF gives one publish per cycle. QA-proposed: (g) manual engage on a batch-2 row, **characterised**; (h) an external reply naming a batch-2 station is ignored with the existing log line; (i) the pump starts no next window before batch 2 is published or abandoned; (j) external reporting sends no cycle-level message twice. **Full unfiltered `dotnet test OpenWSFZ.slnx`; quote the exact command and the total** (the known `CycleArchiveServiceTests` manifest flake is load-sensitive and passes alone).

## 7. Hygiene

- 🔒 **NFR-021 / HK-037:** tests and logs record counts, hashes and stamps only; no message text or callsigns in any log line you add.
- **HK-011:** you are the separate Developer session; QA and the Architect touch no `src/`.
- **Stage by path, never `git add -A` / `git add .`.** Check `git branch --show-current` before committing.
- Nothing is pushed or merged without the Captain's explicit go (HK-010, HK-033). `FR-077` (Stage A) already assumes the config-save change merges first; note any further `REQUIREMENTS.md` change and its numbering.

## 8. Done means

`tasks.md` §13 ticked; S3 (a)-(f) and (g)-(j) green in code; full suite green with the command quoted; `libft8.dll` SHA-256 unchanged (`ee00d118…990e4c`); a short report to QA that includes the two-batch API shape (13.1), the external-reporting finding (13.4) and the observed behaviour of test (g). **QA then runs §14**: S1 (fresh processes, same 161 cycles in the same order, union equals `ca0bcd9b`'s single-batch output and batch 1 equals flag OFF), S2 (batch-1 latency, WSJT-X closed), S2b (report only) and the extended flag-OFF control. **Blind spot:** one machine and no cycle above 31 real signals; two-stage publish says nothing about other hardware, and it does not make residual decodes actionable by the answerer or caller.
