#!/usr/bin/env python3
"""COH-GATE-G: exact TRAIN figures for named rules (same exact-evaluation path as the ceiling: offline product publication, one-to-one match,
frozen U' instrument). Rules: ceiling (admit all), residual_run (f4 alone: admit G rows of the residual run, the original run keeps T1).
Counts only."""
import collections
import importlib.util
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gr_common as C
import gg_lib as L

CF = r"D:\Projects\claude\OpenWSFZ\worktrees\qa\qa\rr-study\coh-fallback"
DLL = r"D:\Projects\claude\_qa-scratch\coh-gate-g\bin\libft8.dll"
WAV_ROOT = r"D:\Projects\claude\OpenWSFZ\artefacts"
RUN = "20260925_2010"
CLASSES = r"D:\Projects\claude\_qa-scratch\coh-gate-g\u\uprime_orig_classes.json"


def main():
    spec = importlib.util.spec_from_file_location("cf_uprime_mod", CF + "\\cf_uprime.py")
    U = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(U)
    F, _ = U.load_instrument()
    enc = F.encoder(DLL)
    frozen = json.load(open(CLASSES))
    c_off = float(frozen["start_minus_dt_median_s"])
    testable = set(frozen["testable_classes"])
    stamps = C.selection_stamps()
    ref = C.load_ref(set(stamps))
    n_ref = sum(len(v) for v in ref.values())
    n_cyc = sum(1 for s in stamps if ref[s])
    arm = L.load_arm("both")
    pcms = {}

    def pcm_of(st):
        if st not in pcms:
            pcms[st] = F.wavio.load_cycle_pcm(os.path.join(WAV_ROOT, f"{RUN}_endurance_run-gathered", "owsfz", "wav", st + ".wav"))
        return pcms[st]

    def status(stamp, text, freq, dt):
        tones = enc(text)
        if any(x.startswith("<") for x in text.split()) or tones is None:
            return "hashed_or_unencodable"
        if F.shape_class(text) not in testable:
            return "untestable_class"
        sh, outs = F.locate_and_score({}, pcm_of(stamp), freq, dt + c_off, F.DT_HALF_WINDOW_S, [tones[i] for i in F.SYNC_IDX], [tones])
        return "tested_present" if outs[0] >= U.T_FROZEN else "tested_absent"

    NONE = lambda r: False
    out = {"n_ref": n_ref, "cycles": n_cyc}
    for name in ("ceiling_admit_all", "residual_run_only"):
        matched_base = matched = 0
        cls = collections.Counter()
        outputs = confirmed = hashed = 0
        by_type = collections.Counter()
        by_type_conf = collections.Counter()
        for s in stamps:
            two = arm["runs"].get(s, 0) == 2
            admit = (lambda r: True) if name == "ceiling_admit_all" else (lambda r, two=two: two and r["run"] == 0)
            base13 = [(x[0], x[2], x[6]) for x in arm["nc"].get(s, []) if x[0] in (1, 2, 3)]
            none = L.publish(arm, s, NONE)
            fb = L.publish(arm, s, admit)
            mn, _ = L.match(ref[s], base13 + [(4, f, t) for f, t, _ in none])
            ma, mo = L.match(ref[s], base13 + [(4, f, t) for f, t, _ in fb])
            matched_base += len(mn)
            matched += len(ma)
            none_texts = {t for _, t, _ in none}
            nb = len(base13)
            for k, (f, t, r) in enumerate(fb):
                if t in none_texts or r["state"] != "G":
                    continue                      # text-new additions only (no moved-frequency relabels)
                outputs += 1
                by_type[r["i3"]] += 1
                if "<" in t:
                    hashed += 1
                if (nb + k) in mo:
                    confirmed += 1
                    by_type_conf[r["i3"]] += 1
                else:
                    cls[status(s, t, f, r["dt"] + r["ddt"])] += 1
        out[name] = {"NET_pp": 100.0 * (matched - matched_base) / n_ref, "newly_corroborated": matched - matched_base,
                     "added_outputs_new_text": outputs, "added_confirmed": confirmed,
                     "unconfirmed_by_class": dict(cls),
                     "dU_per_cycle": {k: cls[k] / n_cyc for k in ("tested_absent", "hashed_or_unencodable", "untestable_class", "tested_present")},
                     "hashed_share_of_added": hashed / max(1, outputs),
                     "type_added": dict(by_type), "type_confirmed": dict(by_type_conf)}
    json.dump(out, open(L.S + "\\rules.json", "w"), indent=1)
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
