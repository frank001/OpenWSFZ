#!/usr/bin/env python3
"""GAP-RELOCATE item 1 (A1-A4) + ROW 0b / 0e / 0f from the BOTH and OFF replay arms.

Reads (all under D:\\Projects\\claude\\_qa-scratch\\gap-relocate): raw/<arm>/{coh.csv,stage.csv,abandon.csv,testb.csv,matchedbatch.csv},
scratch/<arm>/{impl_dump.tsv,nc_dump.tsv,stage_dump.tsv}. Message text is read and compared in memory only; the output JSON and the
printed lines carry counts (HK-037 / NFR-021).

Chain per arm (the unit of every count is stated):
  S1  NEW_GATED candidate-run ROWS, per run (Both: run 0 = residual audio, run 1 = original audio) [rows]
  S1d distinct NEW_GATED payloads per run, and merged (union) [payloads]
  S2  payloads after CoherentFallbackSelector.Select  = text-unpack calls          [payloads]  (asserted == merged distinct)
  S3  unpacked to non-empty text                                                   [payloads]
  S4  after per-cycle text de-duplication  = S5 + implausible drops of the fallback [messages]
  S5  published batch 4 (IsPlausibleMessage passed)                                [messages]
"""
from __future__ import annotations

import collections
import json
import sys

import gr_common as C


def load_arm(name: str):
    raw = f"{C.S}\\raw\\{name}"
    scr = f"{C.S}\\scratch\\{name}"
    arm = {"name": name}
    arm["coh"] = {r["stamp"]: r for r in C.load_csv(raw + "\\coh.csv")}
    arm["stage"] = {}
    try:
        for r in C.load_csv(raw + "\\stage.csv"):
            k = list(r.keys())
            arm["stage"][r[k[0]]] = r
    except FileNotFoundError:
        pass
    arm["abandon"] = C.load_csv_noheader(raw + "\\abandon.csv") if hasattr(C, "load_csv_noheader") else None
    arm["mb"] = C.load_matched_batch(raw + "\\matchedbatch.csv")
    arm["nc"] = collections.defaultdict(list)       # stamp -> [(kind, matched, freq, dt, snr, path, text)]
    for r in C.load_tsv(scr + "\\nc_dump.tsv"):
        if len(r) < 11:
            continue
        arm["nc"][r[0]].append((int(r[1]), int(r[2]), int(r[3]), float(r[4]), int(r[5]), int(r[9]), r[10]))
    arm["ev"] = collections.defaultdict(list)       # stamp -> [(event, args...)]
    for r in C.load_tsv(scr + "\\impl_dump.tsv"):
        if len(r) >= 2 and r[0]:
            arm["ev"][r[0]].append(tuple(r[1:]))
    arm["R"] = collections.defaultdict(list)        # stamp -> [(run, payload, freq, snr, edge)]
    arm["U"] = collections.defaultdict(list)        # stamp -> [(payload, text)]
    try:
        for r in C.load_tsv(scr + "\\stage_dump.tsv"):
            if len(r) >= 7 and r[1] == "R":
                arm["R"][r[0]].append((int(r[2]), r[3], int(r[4]), int(r[5]), int(r[6])))
            elif len(r) >= 4 and r[1] == "U":
                arm["U"][r[0]].append((r[2], r[3]))
    except FileNotFoundError:
        pass
    return arm


def drops_position(events):
    """Method P: implausible drops logged after the last of {third-pass info marker, batch-3 hand-off}, before the fallback line."""
    last = -1
    for i, e in enumerate(events):
        if (e[0] == "M" and len(e) > 1 and e[1] == "T") or (e[0] == "H" and len(e) > 1 and e[1] == "3"):
            last = i
    out = []
    for e in events[last + 1:]:
        if e[0] == "D":
            out.append(e[1] if len(e) > 1 else "")
    return out


def drops_all(events):
    return [(e[1] if len(e) > 1 else "") for e in events if e[0] == "D"]


def main():
    stamps = C.selection_stamps()
    assert len(stamps) == C.N_CYCLES, len(stamps)
    ref = C.load_ref(set(stamps))
    n_ref = sum(len(v) for v in ref.values())
    both = load_arm("both")
    off = load_arm("off")
    res = {"n_ref": n_ref, "cycles": len(stamps)}

    # ---- ROW 0b: replay = B2's Both arm --------------------------------------------------------------------------------
    b4 = sum(int(both["coh"][s]["published"]) for s in stamps if s in both["coh"])
    b4_nc = sum(1 for s in stamps for x in both["nc"].get(s, []) if x[0] == 4)
    matched_all = sum(len(both["mb"].get(s, {})) for s in stamps)
    pct = round(100.0 * matched_all / n_ref, 2)
    res["row0b"] = {"batch4_published_coh_csv": b4, "batch4_outcomes_nc": b4_nc, "b2_expected": C.B2_BOTH_BATCH4,
                    "matched_ref": matched_all, "pct_of_ref": pct, "b2_pct": C.B2_BOTH_PCT, "n_ref_is_b2_W": n_ref == C.B2_W,
                    "PASS": (b4 == C.B2_BOTH_BATCH4 and b4_nc == b4 and pct == C.B2_BOTH_PCT and n_ref == C.B2_W)}

    # ---- stage chain, Both ---------------------------------------------------------------------------------------------
    tot = collections.Counter()
    mism_s2 = 0
    for s in stamps:
        st = both["stage"].get(s)
        if st is None:
            tot["cycles_missing_stage"] += 1
            continue
        k = list(st.keys())
        runs_s = st[k[1]]
        runs = [] if runs_s == "-" else [x.split(":") for x in runs_s.split("|")]
        for ri, r in enumerate(runs):
            tot[f"s1_rows_run{ri}"] += int(r[2])
            tot[f"s1_distinct_run{ri}"] += int(r[3])
        unp, nonempty, threw = int(st[k[2]]), int(st[k[3]]), int(st[k[4]])
        union = {p for (_, p, *_x) in both["R"].get(s, [])}
        tot["s1d_merged"] += len(union)
        tot["s2"] += unp
        tot["s3"] += nonempty
        tot["unpack_threw"] += threw
        if unp != len(union):
            mism_s2 += 1
        pub = int(both["coh"][s]["published"])
        tot["s5"] += pub
        evs = both["ev"].get(s, [])
        fb_pos = drops_position(evs)
        # method X: multiset difference of the implausible-drop texts, Both minus Off
        d_both = collections.Counter(drops_all(evs))
        d_off = collections.Counter(drops_all(off["ev"].get(s, [])))
        diff = d_both - d_off
        neg = d_off - d_both
        fb_x = list(diff.elements())
        tot["impl_all_both"] += sum(d_both.values())
        tot["impl_all_off"] += sum(d_off.values())
        tot["impl_pos"] += len(fb_pos)
        tot["impl_x"] += len(fb_x)
        tot["impl_off_not_in_both"] += sum(neg.values())
        # A3 (text match to WSJT-X in the same cycle) on method X
        reftexts = {t for (_, _, _, t) in ref.get(s, [])}
        a3 = [t for t in fb_x if t in reftexts]
        tot["a3"] += len(a3)
        matched_idx = set(both["mb"].get(s, {}).keys())
        for t in a3:
            idxs = [i for i, (_, _, _, tt) in enumerate(ref[s]) if tt == t]
            if all(i in matched_idx for i in idxs):
                tot["a3_ref_already_published"] += 1
        # dedup classification (S3 - S4), independent of subtraction
        pub_texts4 = collections.Counter(x[6] for x in both["nc"].get(s, []) if x[0] == 4)
        earlier = {k2: {x[6] for x in both["nc"].get(s, []) if x[0] == k2} for k2 in (1, 2, 3)}
        fbdrop = collections.Counter(fb_x)
        for (p, t) in both["U"].get(s, []):
            if not t:
                tot["s3_empty"] += 1
                continue
            if pub_texts4[t] > 0:
                pub_texts4[t] -= 1
                continue
            if fbdrop[t] > 0:
                fbdrop[t] -= 1
                continue
            holders = [k2 for k2 in (1, 2, 3) if t in earlier[k2]]
            if holders:
                tot[f"dedup_vs_batch{min(holders)}"] += 1
            else:
                tot["dedup_vs_fallback_internal_or_unknown"] += 1
    res["chain_both"] = dict(tot)
    res["s2_mismatch_cycles"] = mism_s2
    s4 = tot["s5"] + tot["impl_x"]
    res["row0e_both"] = {"S3": tot["s3"], "S4_from_S5_plus_implausible": s4,
                         "dedup_by_subtraction": tot["s3"] - s4,
                         "dedup_classified": sum(v for k, v in tot.items() if k.startswith("dedup_vs_")),
                         "S2_equals_merged_distinct_all_cycles": mism_s2 == 0,
                         "PASS": (mism_s2 == 0 and tot["s3"] - s4 == sum(v for k, v in tot.items() if k.startswith("dedup_vs_")))}
    # method agreement (spec: if P and X disagree by more than 5 % of the BOTH count, report both and pick none)
    base = max(1, tot["impl_x"])
    res["method_agreement"] = {"position": tot["impl_pos"], "off_difference": tot["impl_x"],
                               "rel_diff_of_x": abs(tot["impl_pos"] - tot["impl_x"]) / base,
                               "agree_within_5pct": abs(tot["impl_pos"] - tot["impl_x"]) <= 0.05 * base}
    json.dump(res, open(C.S + "\\item1.json", "w"), indent=1, sort_keys=True)
    print(json.dumps(res, indent=1, sort_keys=True))


if __name__ == "__main__":
    sys.exit(main())
