# D-001: the `libft8.dll` +97 KB — QA's attribution confirmed, cost is worse than stated, and it does block the native binaries

**Author:** Architect, 2026-07-27 (16:22 UTC, `date -u`, per HK-017). **For:** QA, and the Captain (§4, §6).
**Answers:** `2026-07-27-1600-qa-to-architect-dll-size-notification.md` §4 first bullet — "whether an
unused 97 KB TLS template is an acceptable permanent cost… that is a design call." It is mine, it has
been owed for four notes, and it is here.
**Ruling: it blocks. The native binaries do not merge to `main` in their current form.** The branch's
docs/QA content is unaffected.

---

## 1. QA's attribution is correct — and a control QA did not use confirms it exactly

The section-level work is right and the arithmetic closes to 0.2%: `.rdata` +97,648 bytes against a
`tls_diag_llr174[140][174]` float array of 97,440, residue explained by the new TLS directory and
export-table growth. My 20:30 §9 candidates (optimisation level, CRT linkage, debug/RTTI metadata)
are ruled out.

**There is a stronger confirmation available than the argument QA made for it.** QA compared two
*Windows* binaries and then reasoned about why a TLS template must occupy on-disk bytes. The same
source built for Linux is in the same commit:

| binary | main | working tree | delta |
|---|---:|---:|---:|
| `win-x64/libft8.dll` | 55,808 | 158,208 | **+102,400 (+183%)** |
| `linux-x64/libft8.so` | 67,232 | 67,928 | **+696 (+1.0%)** |

**Same source, same array, same 97,440 bytes of thread-local storage — and the ELF build grew by
696 bytes.** That is the mechanism proved rather than argued: on ELF an uninitialised thread-local
lands in `.tbss`, which is `NOBITS` and occupies no file space exactly as `.bss` does; PE/COFF has no
`.tbss`, so the loader needs a real template and the zeroes must be materialised on disk. QA's
explanation is not just plausible, it is demonstrated by a cross-toolchain control that was sitting
in the same diff.

**Accepted without reservation.** Note also that the delta against `main` is +102,400, not the
+97,792 QA measured against branch `HEAD` — QA's baseline was an intermediate shim-20260033 commit
on this branch. Immaterial to the conclusion; worth pinning since a merge decision is measured
against `main`.

## 2. The cost is materially worse than "not zero-cost on disk"

QA's §3 characterises the finding as "it is not zero-cost *on disk*." **Disk is the least of it.**

A static TLS template is not a file-layout curiosity. It is copied into **every thread's TLS block**,
by the loader, for every thread in the process once the module is loaded — not only threads that
call the diagnostic, and not only when `tls_diag_capture_enabled` is set. The flag gates *writes into*
the buffer; it does not gate the buffer's existence.

So the real cost profile is:

| cost | magnitude |
|---|---|
| Disk, Windows | +97 KB (one-off) |
| Disk, Linux | +0 (`.tbss`) |
| **Committed memory** | **+97 KB × every thread in the process, zeroed, always** |
| Thread-creation latency | one 97 KB zero-fill per thread |

A .NET daemon with a thread pool carries tens of threads without trying. That is several megabytes of
permanently committed, never-read memory, paid by the shipped product for a diagnostic no production
code path uses. On a constrained target it is worse than the disk number suggests, and the disk number
is what the discussion has been anchored on.

**One further risk, stated with its uncertainty intact.** Windows satisfies static TLS for
dynamically-loaded modules from a limited per-process slack, and a DLL with large static TLS loaded
via `LoadLibrary` — which is how .NET P/Invoke resolves `libft8` — is the classic way to hit it.
Modern Windows 10+ expands TLS dynamically and I would **not** predict a failure on the Captain's
machine. **I have not tested this and I am not asserting it.** What I am saying is that 97 KB of
static TLS in a `LoadLibrary`'d DLL puts a shipped artefact adjacent to a known load-failure class,
for no benefit, and I would rather remove the exposure than characterise it.

## 3. The ruling

**The size delta and the branch disposition are the same question**, which is why answering it in
isolation kept stalling across four notes. The 97 KB only matters if the native binary is on the
merge path.

And once framed that way it answers itself: **`tls_diag_llr174` is study scaffolding.** It exists for
C.2 Phase 2c's raw-LLR capture. No product code path reads it. The question is not "is 97 KB an
acceptable permanent cost" — it is "why would a diagnostic-only buffer ship at all."

**Ruling:**

- **The native binaries (`win-x64/libft8.dll`, `linux-x64/libft8.so`) do not merge to `main` in their
  current form.** This is a merge blocker and I am naming it one.
- **The branch's docs, QA tooling and study material are not blocked** by this and can merge on their
  own timeline, subject to the usual HK-010 sign-off.
- **Nothing about this blocks the D-001 study**, which runs against diagnostic builds and always has.

## 4. Three ways to unblock, with a recommendation

| option | cost when disabled | keeps runtime opt-in | verdict |
|---|---|---|---|
| (a) accept as-is | 97 KB disk + 97 KB/thread | yes | **No.** |
| (b) shrink the cap | reduced, not removed; still per-thread | yes | Half a fix. |
| (c) heap-allocate on first enable, free on disable/detach | **zero** | yes | Good if the switch must survive into shipped builds. |
| (d) `#ifdef` it out, off in the shipped build | **zero** | no | **Recommended.** |

**I recommend (d).** The study has always rebuilt the shim to change decode parameters — C.1 rebuilt
three times for a single cap sweep — so there is no workflow that needs this buffer switchable in a
*shipped* artefact. A compile-time gate is simpler than heap management, has no free/detach lifecycle
to get wrong, and is genuinely zero rather than nearly zero. Take (c) only if someone identifies a
real need to toggle raw-LLR capture in a binary they cannot rebuild.

**Scope the fix to the one array.** The other `tls_diag_*` statics (`freq_hz`, `dt`, `score`,
`decoded` — 140 elements each, ~1.4 KB total) are not the problem and should not be disturbed.
`tls_diag_llr174` at 97,440 bytes is the whole of it.

**Routing, per HK-011/HK-015:** this is native `src/` work. QA authors the `dev-tasks/` item, a
Developer session applies it, and the Captain reviews the diff before push. **I am not issuing that
task**, and nothing here authorises the change — it defines what "unblocked" would mean.

## 5. Carried over: the band-floor stance, revised

Folding this in as flagged rather than spending a separate note. In the 15:55 note §2.2 I called the
sub-200 Hz band floor "worth measuring, not worth assuming." QA's cycle-set correction
(`2026-07-27-1611-...`) came back at **0.76% / 1.96% of the miss population**, at the low end of my
bound.

**Revised: it is a logged, quantified non-priority.** The benefit landed low while the cost side is
unchanged — NFR-018 false-positive exposure in soundcard-rumble spectrum, the `MaxPass0Candidates`
interaction, and a native change carrying the same HK-011 overhead as §4's. Sub-2% does not buy that.
Record it as a known opportunity to bundle into some future native change; do not chase it.

**One durable note from that correction:** our frequency estimate is *clamped* at `f_min`, not merely
binned — verified independently, our decode set has exactly four rows at 200.0 Hz, nothing below, and
a minimum of exactly 200.0. **A decode reported at exactly 200.0 or 3000.0 Hz is a censored value, not
a measurement.** Immaterial at four messages; worth knowing before anyone builds a matcher near the
band edges.

## 6. What the Captain should take from this

- **The +97 KB is fully explained** and is one diagnostic array, confirmed two independent ways.
- **It blocks the native binaries from merging to `main`** — but only those. Docs and QA material are
  free.
- **The real cost is per-thread memory, not disk**, which is why I am ruling against it rather than
  waving it through as "97 KB, who cares."
- **The fix is small** — a compile-time gate on one array — and is a Developer-session item whenever
  you want it, not a study dependency.
- **This ruling was four notes overdue.** It should not have taken that long, and the reason it did is
  that I kept treating it as separable from the branch disposition when it is the same question.

## 7. What this does not authorise or settle

- **No native or `src/` change** (HK-011). §4 defines the target; it does not commission it.
- **No push, no merge** (HK-014). **No `pre_merge_check.py`** (HK-006 — Captain's trigger).
- **Branch disposition** is now answerable — split the merge, native excluded — but the decision to
  merge anything at all remains the Captain's under HK-010, and I am not proposing a timeline.
- **The R.3 replacement design** remains owed and is next.
- **Per HK-015 this is a design, not a task.**

## 8. Honest caveats

- **I have not tested the static-TLS load-slack risk** (§2, final paragraph) and have deliberately not
  claimed it will bite. If anyone wants it settled rather than avoided, it is a load test on the
  oldest supported Windows build — but the recommended fix removes the exposure more cheaply than
  measuring it would.
- **§1's Linux control is a file-size comparison, not a section dump.** The `.tbss` mechanism is the
  standard explanation and the 696-byte delta fits it precisely, but if QA wants it nailed rather than
  inferred, `readelf -S` on both `.so` builds closes it in a minute. I did not run it.
- **The per-thread memory figure in §2 is architectural, not measured on this daemon.** Exact
  allocation timing differs between load-time and `LoadLibrary`'d modules. The per-thread cost is the
  substance; the total depends on the thread count, which I have not counted.

## 9. Cross-references

- `2026-07-27-1600-qa-to-architect-dll-size-notification.md` — the notification this rules on;
  §2's attribution accepted, §3's cost characterisation revised by §2 above.
- `2026-07-26-2030-architect-c2-phase2c-ruling.md` §9 — where I first asked the question.
- `src/OpenWSFZ.Ft8/Native/ft8_shim.c:568–572` and the `tls_diag_llr174` declaration — the array §4 is
  about, and the small `tls_diag_*` neighbours it should not disturb.
- `src/OpenWSFZ.Ft8/Native/win-x64/libft8.version.txt` — shim 20260035's own documentation of the
  buffer.
- `2026-07-27-1611-qa-band-floor-cycle-set-correction.md`,
  `2026-07-27-1555-architect-r4b-ruling-and-band-limits.md` §2.2 — the stance §5 revises.

---

*Per HK-015 Architect → QA: §4's fix is for QA to author as a dev-task, not a task issued here. Per
HK-014 committed locally and goes no further. Per HK-011 nothing here touches `src/` or native code.
Merge decisions remain the Captain's under HK-010.*
