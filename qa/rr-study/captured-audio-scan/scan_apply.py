"""#194 scan: apply the FROZEN thresholds to one run and write scan_report.md (+ flagged_slots.csv).

    python scan_apply.py --run <name> --sidecars <dir from scan_run measure> --thresholds <frozen thresholds.json> \
        --audio <...-captured-audio dir> --out <results dir> [--calibration]

Counts, slot keys and hashes only (NFR-021). A WAV is recorded before either decoder runs, so no finding here
is ever a decoder defect (the section-1 paragraph is printed verbatim in every report).
"""
from __future__ import annotations

import argparse
import csv
import json
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import scan_core as sc  # noqa: E402
import scan_freeze as fz  # noqa: E402

GUARD = ("> A WAV is recorded **before** either decoder runs, so **no WAV anomaly is ever a decoder defect.** "
         "Comparing the two apps' WAVs for the same slot locates a fault in one of two places only. If it shows "
         "**in both**, it is in the **shared playback path** (render → PortAudio → Voicemeeter → both recorders). "
         "If it shows **in one**, it is in **that app's recording path**. A slot with no anomaly says nothing about "
         "how either decoder handled it.")
S1_GUARD = ("🛑 S1 `g_db` / `resid_db` below are descriptive chain gains. The +1.45 dB SNR-bias follow-up was dropped "
            "by the Captain on 2026-09-29; these numbers do not reopen it and are never cited as a build or chain effect.")


def family_set(fl: dict) -> set:
    return {sc.FAMILIES[m] for m, f in fl.items() if f}


def classify(flags_o: dict, flags_w: dict) -> list:
    """BOTH / OWSFZ-ONLY / WSJTX-ONLY by metric family, for one slot (a side with no entry = nothing flagged).
    Same family flagged on both sides of the same slot (the same 15 s cycle, i.e. within +-0.5 s) = BOTH."""
    fo, fw = family_set(flags_o), family_set(flags_w)
    return ([("BOTH", f) for f in sorted(fo & fw)] + [("OWSFZ-ONLY", f) for f in sorted(fo - fw)]
            + [("WSJTX-ONLY", f) for f in sorted(fw - fo)])


def run_centres(scanned: dict) -> dict:
    """A11: this run's own median tau_ms per (side, group); and the owsfz-minus-wsjtx tau difference per group."""
    cen, by = {}, {}
    for side, rows in scanned.items():
        for r in rows:
            if r["tau_ms"] == r["tau_ms"]:
                by.setdefault((side, r["group"]), []).append(r["tau_ms"])
    for (side, g), v in by.items():
        cen[(side, g, "tau_ms")] = statistics.median(v)
    return cen


def dtau_centres(by_slot: dict) -> dict:
    d = {}
    for k, o in by_slot["owsfz"].items():
        w = by_slot["wsjtx"].get(k)
        if w is not None and o["tau_ms"] == o["tau_ms"] and w["tau_ms"] == w["tau_ms"]:
            d.setdefault(o["group"], []).append(o["tau_ms"] - w["tau_ms"])
    return {g: statistics.median(v) for g, v in d.items()}


def run_level_deltas(th: dict, scanned: dict) -> list:
    """Run median g_db minus the calibration median per (side, group); RUN-LEVEL if |delta| > 0.5 dB."""
    out = []
    for side, rows in scanned.items():
        for g in sc.GROUPS:
            row = th["sides"][side][g].get("g_db")
            v = [r["g_db"] for r in rows if r["group"] == g and r["g_db"] == r["g_db"]]
            if row and v:
                d = statistics.median(v) - row["median"]
                out.append({"side": side, "group": g, "delta_db": d, "RUN-LEVEL": abs(d) > sc.RUN_LEVEL_DELTA_DB})
    return out


def evaluate(th: dict, desc: set, scanned: dict, by_slot: dict, mode: str) -> dict:
    centres = run_centres(scanned) if mode == "a11" else None
    dcen = dtau_centres(by_slot) if mode == "a11" else {}
    flags = {s: {} for s in fz.SIDES}
    for s in fz.SIDES:
        for r in scanned[s]:
            fl = fz.slot_flags(th, s, r, centres)
            flags[s][r["slot"]] = {m: bool(f and f"{s}:{r['group']}:{m}" not in desc) for m, f in fl.items()}
    classes = defaultdict(list)
    for k in set(flags["owsfz"]) | set(flags["wsjtx"]):
        for c in classify(flags["owsfz"].get(k, {}), flags["wsjtx"].get(k, {})):
            classes[k].append(c)
    for k, o in by_slot["owsfz"].items():
        w = by_slot["wsjtx"].get(k)
        if w is None:
            continue
        g = o["group"]
        for m, val in (("dg_db", o["g_db"] - w["g_db"]),
                       ("dtau_ms", (o["tau_ms"] - w["tau_ms"]) if o["tau_ms"] == o["tau_ms"] and w["tau_ms"] == w["tau_ms"] else float("nan"))):
            row = th["cross"].get(g, {}).get(m)
            if row and f"cross:{g}:{m}" not in desc and sc.flagged(val, row, dcen.get(g) if m == "dtau_ms" and mode == "a11" else None):
                classes[k].append(("CROSS", m))
    return {"flags": flags, "classes": classes, "mode": mode}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--sidecars", required=True)
    ap.add_argument("--thresholds", required=True)
    ap.add_argument("--audio", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--calibration", action="store_true")
    ap.add_argument("--registered", choices=("a11", "freeze3"), default="a11",
                    help="which centring rule is the registered result of this report (09-29 stays freeze3; the other is shown beside it)")
    a = ap.parse_args()
    thp = Path(a.thresholds)
    th = json.loads(thp.read_text(encoding="utf-8"))
    frozen = [ln for ln in (thp.parent / "FREEZE.sha256").read_text().splitlines() if ln.startswith("thresholds.json")][0].split()[1]
    assert fz.sha_lf(thp) == frozen and th["scan_core_py_sha256"] == fz.sha_lf(Path(sc.__file__)), "frozen files changed"
    desc = set(th["descriptive"])
    sd = Path(a.sidecars)
    r0c = json.loads((sd / "r0c.json").read_text())
    data = {s: [r for r in fz.load(sd / f"sidecar_{s}.csv")] for s in fz.SIDES}
    scanned = {s: [r for r in data[s] if not r["ref_mismatch"]] for s in fz.SIDES}
    files = list(csv.DictReader(open(sd / "files.csv", newline="", encoding="utf-8")))

    # ---- flags (non-DESCRIPTIVE only), BOTH / one-sided / CROSS, under two centring modes:
    #   "freeze3": every dev metric on the calibration median (the REGISTERED rule for 09-29)
    #   "a11":     tau_ms / dtau_ms on this run's own median (forward rule, ruling 2026-10-02 2055)
    by_slot = {s: {r["slot"]: r for r in scanned[s]} for s in fz.SIDES}
    ev = {mode: evaluate(th, desc, scanned, by_slot, mode) for mode in ("freeze3", "a11")}
    main_mode = "freeze3" if a.registered == "freeze3" else "a11"
    flags, classes = ev[main_mode]["flags"], ev[main_mode]["classes"]
    n_cls = Counter(c for v in classes.values() for c, _ in v)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    with open(out / "flagged_slots.csv", "w", newline="", encoding="utf-8") as fh:
        wr = csv.writer(fh, lineterminator="\n")
        wr.writerow(["slot", "cycle_utc", "scenario", "group", "class", "family", "owsfz_metrics", "wsjtx_metrics"])
        for k in sorted(classes):
            rr = (by_slot["owsfz"].get(k) or by_slot["wsjtx"].get(k))
            for c, f in classes[k]:
                wr.writerow([k, rr["cycle_utc"], rr["scenario"], rr["group"], c, f,
                             "+".join(m for m, v in flags["owsfz"].get(k, {}).items() if v and sc.FAMILIES[m] == f),
                             "+".join(m for m, v in flags["wsjtx"].get(k, {}).items() if v and sc.FAMILIES[m] == f)])

    # ---- V1 / V2 / V3
    per_side_cls = {s: Counter() for s in ("owsfz", "wsjt-x")}
    for f in files:
        if f["side"] in per_side_cls:
            per_side_cls[f["side"]][f["class"]] += 1
    v1, v2 = {}, {}
    for s, dirname in (("owsfz", "owsfz"), ("wsjt-x", "wsjt-x")):
        n_files = len(list((Path(a.audio) / dirname / "wav").glob("*.wav")))
        v1[s] = {"files": n_files, "classified": sum(per_side_cls[s].values()), "by_class": dict(per_side_cls[s]),
                 "PASS": n_files == sum(per_side_cls[s].values())}
        bad, n = 0, 0
        for f in files:
            if f["side"] == s and f["sha256"]:
                n += 1
                if sc.sha256_file(Path(a.audio) / dirname / "wav" / f["filename"]) != f["sha256"]:
                    bad += 1
        v2[s] = {"rehashed": n, "mismatch": bad, "PASS": bad == 0}
    missing = sum(1 for f in files if f["class"] == "MISSING")

    # ---- reporting tables
    def grp_counts(key):
        c = Counter()
        for s in fz.SIDES:
            for r in scanned[s]:
                c[(s, r["group"])] += 1 if key(r) else 0
        return c

    group_n = {s: Counter(r["group"] for r in scanned[s]) for s in fz.SIDES}
    amb = {s: Counter(r["group"] for r in scanned[s] if r["lag_ambiguous"]) for s in fz.SIDES}
    unver = {s: Counter(r["group"] for r in scanned[s] if r["nondiscriminating"]) for s in fz.SIDES}
    n_unver = sum(sum(c.values()) for c in unver.values())
    n_all = sum(sum(c.values()) for c in group_n.values())
    ref_unver_frac = {s: sum(unver[s].values()) / max(1, sum(group_n[s].values())) for s in fz.SIDES}
    s1 = {s: [r for r in scanned[s] if r["scenario"] == "S1"] for s in fz.SIDES}
    flagged_counts = Counter()
    for s in fz.SIDES:
        for k, fl in flags[s].items():
            for m, f in fl.items():
                if f:
                    flagged_counts[(s, m)] += 1
    lost = {s: sum(1 for r in scanned[s] if r["lag_lost"] == 1.0) for s in fz.SIDES}
    L = []
    w = L.append
    w(f"# Captured-audio scan report: {a.run}" + (" (CALIBRATION RUN)" if a.calibration else ""))
    w("")
    w(f"- Frozen `thresholds.json` SHA-256 (LF): `{frozen}`; `scan_core.py` `{th['scan_core_py_sha256']}`; calibration run `{th['calibration_run']}`.")
    w(f"- Tool: `qa/rr-study/captured-audio-scan/` (`scan_run.py measure`, `scan_apply.py`). Measure wall time: **{r0c.get('wall_seconds')} s** (V3, one core).")
    w("- Audio only. No decoder, `ALL.TXT` or message text was read; counts, slot keys and hashes only (NFR-021).")
    w("")
    w("## What a finding can and cannot mean")
    w("")
    w(GUARD)
    w("")
    w("## Headline (plain words)")
    w("")
    w(f"- **{n_cls.get('BOTH', 0)}** slot-family findings are **BOTH** (shared playback path), **{n_cls.get('OWSFZ-ONLY', 0)}** OpenWSFZ-only, **{n_cls.get('WSJTX-ONLY', 0)}** WSJT-X-only, **{n_cls.get('CROSS', 0)}** cross-side, over {len(classes)} flagged slots of {len(by_slot['owsfz'])} owsfz / {len(by_slot['wsjtx'])} wsjt-x scanned.")
    ab = th["descriptive_above_range"]
    w(f"- 🔴 **Holes.** {len(th['descriptive'])} (side, group, metric) cells are DESCRIPTIVE and never flag ({len(ab)} of them DESCRIPTIVE-ABOVE-RANGE). **With these thresholds the scan cannot detect a short added sound (a Windows notification, a beep) or a click in the groups where `tile_excess_db` / `click_max` are above range** (owsfz: single, multi, tone2, tone3 tiles; wsjt-x: single, multi, tone3 tiles and multi, noise, tone3 clicks).")
    w("- **Blind spots stated:** WSJT-X's last 600 ms (it writes 14.4 s then zeros) cannot show a dropout; slots whose **reference** is lag-ambiguous (steady carriers) have no timing check: " + ", ".join(f"{s}: {dict(amb[s])}" for s in fz.SIDES) + ".")
    w(f"- **REF-UNVERIFIABLE** (mapping rests on the file name ↔ `cycle_utc` identity alone): " + ", ".join(f"{s}: {sum(unver[s].values())}/{sum(group_n[s].values())} ({100*ref_unver_frac[s]:.0f} %)" for s in fz.SIDES) + (" — 🛑 OVER 50 %: STOP" if any(v > 0.5 for v in ref_unver_frac.values()) else " (limit 50 %)") + ".")
    w("")
    w("## Validation rows")
    w("")
    w("| Row | Result |")
    w("|---|---|")
    w(f"| R0c literal (rule as written, run-wide neighbour max) | owsfz fails {r0c['sides']['owsfz']['spec_literal_fail_all_slots']}/{r0c['sides']['owsfz']['paired_slots']} ({100*r0c['sides']['owsfz']['spec_literal_fail_fraction_all']:.1f} %), wsjt-x {r0c['sides']['wsjt-x']['spec_literal_fail_all_slots']}/{r0c['sides']['wsjt-x']['paired_slots']} ({100*r0c['sides']['wsjt-x']['spec_literal_fail_fraction_all']:.1f} %): **FAIL as written** (kept per ruling A1) |")
    w(f"| R0c per slot (A1), discriminating slots | owsfz {r0c['sides']['owsfz']['A1_fail_fraction']*100:.1f} % fail of {r0c['sides']['owsfz']['discriminating']}; wsjt-x {r0c['sides']['wsjt-x']['A1_fail_fraction']*100:.1f} % of {r0c['sides']['wsjt-x']['discriminating']}: " + ("PASS" if r0c['sides']['owsfz']['A1_PASS'] and r0c['sides']['wsjt-x']['A1_PASS'] else "**FAIL**") + " |")
    for s in ("owsfz", "wsjt-x"):
        w(f"| V1 coverage, {s} | {v1[s]['files']} WAV files = {v1[s]['classified']} classified {v1[s]['by_class']}: " + ("PASS" if v1[s]["PASS"] else "**FAIL**") + " |")
    w(f"| V1 truth slots with no WAV on either side (MISSING) | {missing} |")
    for s in ("owsfz", "wsjt-x"):
        w(f"| V2 sidecar integrity, {s} | {v2[s]['rehashed']} files re-hashed fresh, {v2[s]['mismatch']} mismatch: " + ("PASS" if v2[s]["PASS"] else "**FAIL**") + " |")
    w(f"| V3 runtime | {r0c.get('wall_seconds')} s to measure {r0c['n_paired']} paired slots (reference renders ≈ 30 s per run extra) |")
    w("")
    w("## Flagged slots by class and family")
    w("")
    w("| class | family | slots |")
    w("|---|---|---:|")
    cf = Counter((c, f) for v in classes.values() for c, f in v)
    for (c, f), n in sorted(cf.items()):
        w(f"| {c} | {f} | {n} |")
    w("")
    w("Per-metric flag counts (non-DESCRIPTIVE only), side × metric: " + ", ".join(f"{s}:{m}={n}" for (s, m), n in sorted(flagged_counts.items())) + ". `lag_lost` slots: " + ", ".join(f"{s}={n}" for s, n in lost.items()) + ".")
    w("")
    w("The full list (slot key, cycle, class, family, metrics) is `flagged_slots.csv`; message text never appears.")
    w("")
    w("## Descriptive: S1 chain gain")
    w("")
    w(S1_GUARD)
    for s in fz.SIDES:
        if s1[s]:
            w(f"- {s}: median `g_db` {statistics.median(r['g_db'] for r in s1[s]):.2f}, median `resid_db` {statistics.median(r['resid_db'] for r in s1[s]):.2f} (n = {len(s1[s])}).")
    other = "a11" if main_mode == "freeze3" else "freeze3"
    w("")
    w(f"## Registered result: `{main_mode}` centring" + ("; the A11 reclassification below is 'applied after reading; forward rule'" if main_mode == "freeze3" else " (A11 forward rule)"))
    w("")
    def cnt(e):
        c = Counter((cl, f) for v in e["classes"].values() for cl, f in v)
        return c
    c_main, c_oth = cnt(ev[main_mode]), cnt(ev[other])
    w(f"| class | family | slots (`{main_mode}`, registered) | slots (`{other}`, " + ("A11, applied after reading; forward rule" if other == "a11" else "freeze 3 rule") + ") |")
    w("|---|---|---:|---:|")
    for key in sorted(set(c_main) | set(c_oth)):
        w(f"| {key[0]} | {key[1]} | {c_main.get(key, 0)} | {c_oth.get(key, 0)} |")
    w("")
    w("**Cite as shared-path events only** the BOTH findings that survive A11 plus the level, drift and `lag_lost` families.")
    w("")
    w("### Run-level lines (A11)")
    w("")
    w("(a) run median `g_db` minus the calibration median, per (side, group); `RUN-LEVEL` if |Δ| > 0.5 dB:")
    for d in run_level_deltas(th, scanned):
        w(f"- {d['side']} {d['group']}: {d['delta_db']:+.2f} dB" + (" **RUN-LEVEL**" if d["RUN-LEVEL"] else ""))
    w("(b) the run's own median `tau_ms` offset per (side, group) and `dtau_ms` offset: descriptive only, in the table below.")
    # ---- descriptive preview, NOT frozen (an "A11" question for the Architect): the frozen dev rule centres
    # g_db / tau_ms / dg_db / dtau_ms on the CALIBRATION run's median; a per-run shift of the chain's timing
    # offset then flags most slots. Here: the median of this run per (side, group) and the same frozen T.
    w("")
    w("## Descriptive, NOT frozen: run-level offset of the dev metrics (question for the Architect)")
    w("")
    w("The frozen `tau_ms` / `dtau_ms` / `g_db` / `dg_db` rule is two-sided around the **calibration run's** median. Medians per run (ms for tau, dB for g):")
    w("")
    w("| side | group | cal median tau | this run median tau | cal median g | this run median g | slots beyond frozen T (tau) | beyond T if re-centred on this run |")
    w("|---|---|---:|---:|---:|---:|---:|---:|")
    for s_ in fz.SIDES:
        for g_ in sc.GROUPS:
            rows_ = [r for r in scanned[s_] if r["group"] == g_]
            rowt = th["sides"][s_][g_].get("tau_ms")
            rowg = th["sides"][s_][g_].get("g_db")
            if not rows_ or rowt is None:
                continue
            taus = [r["tau_ms"] for r in rows_ if r["tau_ms"] == r["tau_ms"]]
            if not taus:
                continue
            mt = statistics.median(taus)
            mg = statistics.median(r["g_db"] for r in rows_)
            fro = sum(1 for v in taus if abs(v - rowt["median"]) > rowt["T"])
            rec = sum(1 for v in taus if abs(v - mt) > rowt["T"])
            w(f"| {s_} | {g_} | {rowt['median']:.1f} | {mt:.1f} | {rowg['median']:.2f} | {mg:.2f} | {fro} | {rec} |")
    dts = []
    for k, o in by_slot["owsfz"].items():
        wv = by_slot["wsjtx"].get(k)
        if wv is not None and o["tau_ms"] == o["tau_ms"] and wv["tau_ms"] == wv["tau_ms"]:
            dts.append((o["group"], o["tau_ms"] - wv["tau_ms"]))
    for g_ in sc.GROUPS:
        row = th["cross"].get(g_, {}).get("dtau_ms")
        v = [d for gg, d in dts if gg == g_]
        if row and v:
            m_ = statistics.median(v)
            w(f"- dtau_ms, {g_}: calibration median {row['median']:.1f} ms, this run {m_:.1f} ms; beyond frozen T ({row['T']:.1f}): {sum(1 for d in v if abs(d - row['median']) > row['T'])} of {len(v)}; if re-centred: {sum(1 for d in v if abs(d - m_) > row['T'])}.")
    (out / "scan_report.md").write_text("\n".join(L) + "\n", encoding="utf-8", newline="\n")
    print("\n".join(L[:14]))
    print(json.dumps({"V1": v1, "V2": v2, "classes": dict(n_cls)}))


if __name__ == "__main__":
    main()
