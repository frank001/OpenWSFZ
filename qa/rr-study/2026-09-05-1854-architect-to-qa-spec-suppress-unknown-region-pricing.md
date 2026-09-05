# `SUR-PRICE` — Architect to QA: what is `SuppressUnknownRegion` costing today?

**Architect, 2026-09-05 18:54 UTC** (`date -u`, HK-017). PO-commissioned 2026-09-05 alongside §5
option 1 (badge dropped) of `2026-09-05-1850-architect-to-qa-ruling-fp-mark-2-adjudication.md`.

**PRE-REGISTERED and ARMED. QA's to execute.** Offline analysis of data already pinned — no live
run, no hardware, no rebuild, **no `src/` or `native/` change.**

🛑 **This is NOT about the withdrawn marking feature.** It prices a control that **ships today and
suppresses today**. QA draws no verdict on whether the setting should change (HK-015).

---

## 0. The question, and why it is answerable at all

`decode-noise-suppression`'s **`SuppressUnknownRegion`** removes a decode from the decode panel
**and** from `QsoAnswererService`/`QsoCallerService` eligibility when its region lookup does not
resolve. Its **false-suppression rate has never been measured**, in this project or anywhere in the
record.

🔴 **It is ON right now.** The setting's default is `null` = *computed from region-data presence*:
`false` while the region store is empty, **`true` once it has ≥ 1 entry**. The pinned table has
**29,013** entries ⇒ absent an explicit operator choice, **decodes are being suppressed today.**

✅ **The measurement is clean, and this is the enabling property:** `decode-noise-suppression`
Decision 1 — **`ALL.TXT` is never affected by suppression.** The pinned corpora are `ALL.TXT` logs,
so they contain **every decode, suppressed or not**. The corpus is untouched by the very setting
being measured ⇒ **no circularity.** Without this the arm would be impossible.

---

## 1. Established — do not re-derive (HK-018)

| Fact | Value | Source |
|---|---|---|
| Pinned corpora | **241,858** decodes, 7 sessions, **21,242** distinct callsigns | ROW 0b manifest (SHA256-pinned) |
| Pinned region table | **29,013** entries, SHA256-pinned; 35 duplicate ranges, order-dependent tie-break | ROW 0b |
| `TryMatchPrefix` port | built, verified, **linear-vs-binary diff 0/5,000** | `FP-MARK-2` |
| **Distinct FP callsign tokens that ever repeat** | **0 of 161** across 72 labelled FPs | `FP-MARK` §1 |
| Real distinct callsigns heard exactly once | 46.6% | ROW 0b corpora |

**Reuse `fp_mark_2_analysis.py` / `fp_mark_row0b_identifiability.py` ports. Do not re-port.**
**HK-031 discharged** — no new sweep introduced or read.

---

## 2. The discriminator, and its limit stated up front

We have no ground truth labelling live decodes real-vs-FP. **We do have a mechanism-grounded
one-way discriminator:**

> **A false positive does not recur.** Measured: **0 of 161** distinct FP callsign tokens ever
> repeated. A CRC-14 coincidence would have to redraw a 77-bit payload.

⇒ **An unresolved-prefix callsign seen ≥ 2 times in one session is almost certainly a genuine
station**, and suppressing it is a **false suppression**.

🛑 **This yields a FIRM LOWER BOUND and nothing more.** The converse does **not** hold: a
singleton unresolved callsign may be genuine (46.6% of *all* real callsigns are singletons) or an
FP, and this arm **cannot tell which**.

🔴 **Do NOT extrapolate.** Scaling the multi-occurrence count by the 53.4% repeat rate of *resolved*
callsigns would assume unresolved genuine stations repeat like resolved ones — **false by
construction**, since rare DX heard once is exactly the population whose prefix is most likely
missing from the table. **Any such estimate is forbidden in this arm; the lower bound is the
deliverable.**

---

## 3. The rows

| Row | Check | Bar | Consequence |
|---|---|---|---|
| **0a** | **Precondition — the setting is actually in effect.** Pinned region table has ≥ 1 entry ⇒ computed default is `true` | **fires if the table is empty** | 🛑 **STOP, pause and hand back** — the arm would price a control that is not running |
| **1** | **Suppression rate.** Share of decodes whose callsign prefix does not resolve — **per decode** and **per distinct callsign**, exact CP 95% CI | descriptive, no bar | This is what the control removes from panel and automation eligibility |
| **2** | **PRIMARY — firm lower bound on false suppression.** Distinct unresolved-prefix callsigns appearing **≥ 2 times** in the same session | **fires if the mean across the 7 sessions is ≥ 1 genuine distinct callsign suppressed per session** | 🔴 **`SuppressUnknownRegion`'s default-ON is a product defect to raise with the PO** |
| **3** | **Operational figure.** ROW 2's count **per session**, listed, not just averaged | descriptive | One number the operator can weigh: stations lost per session |
| **4** | **Signature (descriptive).** Prefix concentration of unresolved decodes — clustered (table gaps) vs dispersed (random draws) | descriptive, no bar | Distinguishes *"our table is stale"* from *"these are mostly FPs"*. **No ratio, no p-value** |

**ROW 2's bar is derived from consequence, not from the data:** losing **one genuine station per
session** is operationally material to an operator chasing DX, and 46.6% singletons means a lost
station is usually a lost *only* chance. The bar is fixed here, before measurement (HK-021(y)).

**Precision, not power:** ~242k decodes / 21,242 distinct callsigns. 🛑 **No power calculation is
load-bearing and none may be quoted as one** — exact CP intervals; per HK-021(o) the readout
quantum, never a bootstrap SE.

---

## 4. 🔴 Two caveats that must travel with the result

**(a) The measured rate is a LOWER bound on what was suppressed at capture time.** The corpora were
captured earlier; the pinned table is today's. A table that has *grown* resolves **more** prefixes
now than then ⇒ **more** decodes were suppressed during capture than this arm will count. The bias
direction is known and favours understatement. **Report it; do not correct for it.**

**(b) 🛑 ROW 2 is a floor, not the rate.** It counts only callsigns proven genuine by recurrence.
The true false-suppression count is **higher by an unknown amount** — every genuinely-heard-once
station with an unresolved prefix is invisible to this method. **A small ROW 2 is NOT evidence the
control is cheap** (HK-021(j) — an exposure of zero is not an absence).

---

## 5. Execution notes

- **Assert the SHA256 pins at run time** — region table **and** 7-corpus manifest — and record them.
- **Session** = one corpus file. Recurrence is counted **within** a session, never across.
- **Callsign extraction:** reuse `ExtractPrimaryCallsignToken` + `StripPortableSuffix`. A decode with
  no callsign-position token is **out of population**, not "unresolved".
- ⚠️ **Sort at construction**; no `set(a) & set(b)` over string keys in any seeded path.
- ⚠️ **No unguarded slices on a population** — `[:N]` is the HK-021(i) defect that nearly bit twice
  today.
- ✅ **Put the inherited constants in the code as assertions, not the prose** — the 7-file manifest,
  241,858 decodes, 21,242 distinct callsigns. **This is the session's own best process finding: an
  `== 72` assertion caught a fabricated document citation before any number was computed.**
- **HK-009:** ASCII `stdout` or `reconfigure(encoding="utf-8")`.

---

## 6. What QA reports — and must not conclude

**Report:** ROW 0a, 1, 2, 3, 4, with caveats §4(a) and §4(b) in the same section as ROW 2's number.

🛑 **QA draws no verdict on whether `SuppressUnknownRegion`'s default should change, and proposes no
`src/` change.** That is the Architect's to adjudicate and the PO's to ratify. **HK-011:** if a code
change is ever wanted, QA proposes and stops.

**HK-025 stands** — if any row is non-mechanical, or a precondition cannot change a verdict, refuse
on HK-021(k) grounds and say so.

---

## 7. NFR-021 and housekeeping

Reads **21,242 real callsigns**, and ROW 4 is *about* prefixes. 🛑 **Every committed output
aggregate** — counts, rates, CP intervals, and for ROW 4 **prefix-length or concentration statistics,
never a list of prefixes or callsigns.** `PD2FZ` is the single permitted exception. Scan with the
project's own `scan()`/`classify()` — not a directory walk, never on an uncommitted directory — **and
scan the report prose.** ⚠️ The Architect tripped the prose guard earlier today; it is not
theoretical.

**HK-016** dated `./artefacts/` dir with `README.md`. **HK-014** commit locally, do not push; verify
`git diff --stat -- src/ native/` is empty and say so. **HK-030** every STOP means pause and hand
back.

---

**Architect, 2026-09-05 18:54 UTC.** Pre-registered; nothing measured beyond §1's already-recorded
facts.
