"""REFERENCE-SET frozen corpus: plan / copy / scan / freeze (QA). Spec: REFERENCE-SET 2b-2j on arch/reference-set.

    python -s -E build_corpus.py plan      # reproduce the draw, strata, assert the Architect's numbers; writes plan.json (no copy)
    python -s -E build_corpus.py copy      # copy the WAVs and ALL.TXT files into the corpus folder, verify every SHA-256
    python -s -E build_corpus.py scan      # the 3c(a) corpus scan on the COPIED folder; marks flagged cycles / excluded blocks
    python -s -E build_corpus.py freeze    # write manifest.json (+ MANIFEST.sha256), set the tree read-only, verify once

Inputs (desk work, `D:\\Projects\\claude\\_qa-scratch\\refset-inventory\\`): valid.jsonl (per-cycle verdicts), feed_all.jsonl (SAME-FEED
and framing lag), wavs.jsonl (SHA-256 of every candidate WAV), frozen_bar.json. Aggregates and file names only: no message text is read
here (the WSJT-X ALL.TXT is read for line counts per cycle stamp, nothing else).
"""
import collections
import hashlib
import json
import os
import random
import re
import shutil
import sys

SCR = r"D:\Projects\claude\_qa-scratch\refset-inventory"
OUT = r"D:\Projects\claude\_qa-scratch\refset-corpus-build"
ART = r"D:\Projects\claude\OpenWSFZ\artefacts"
CORPUS = os.path.join(ART, "rr-s6-refset-corpus")
sys.path.insert(0, SCR)
import common as C  # noqa: E402  (RUNS map, epoch helpers)

W, L = 8, 32
N = W + L
CAP_CYCLES = 11_520
SEED = 20261011
# The Architect's frozen figures (2j): the plan is refused unless it reproduces them.
EXPECT = {"blocks": 196, "cycles": 7840, "bands": ["17m", "20m", "40m", "80m"], "cell_quota": 24}
EXPECT_CELLS = {"17m|day": 24, "17m|twilight": 3, "17m|night": 0, "20m|day": 24, "20m|twilight": 22, "20m|night": 24,
                "40m|day": 24, "40m|twilight": 24, "40m|night": 24, "80m|day": 15, "80m|twilight": 5, "80m|night": 7}
LAG_BAND_S = None                 # 2j, frozen: [P0.1, P99.9] of the 1004 + 1009 lags (spec prints them rounded: [-0.040, +0.009] s); computed exactly below
SAMEFEED_BAR = 0.5984             # 2h, frozen before any other run was scored
ATTESTATION = ("Captain, QA window, 2026-10-10: \"wsjt-x has been 2.70 all the time.\" and \"I'm quite sure I had the audio devices for wsjt-x and "
               "openwsfz the same all the time. An exception may be when the SDR-UNO and a 2nd openwsfz was used.\" "
               "Architect 2g (a): the version is accepted; the device and 'no mid-run change' are NOT accepted on the attestation alone and are "
               "measured per cycle (SAME-FEED, FRAMING); the attestation is supporting evidence.")
LOGGED_RUNS = ("20261004_1634", "20261009_1752")      # the only runs with an audio-setup log


def jl(path):
    with open(path, encoding="utf8") as fh:
        return [json.loads(l) for l in fh if l.strip()]


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def src_all_txt(run):
    base = os.path.join(ART, run)
    for ows, wsj in (("owsfz", "wsjt-x"), ("openwsfz", "wsjtx-1-ft991a")):
        o, w = os.path.join(base, ows, "ALL.TXT"), os.path.join(base, wsj, "ALL.TXT")
        if os.path.isfile(o) and os.path.isfile(w):
            return o, w
    raise FileNotFoundError("no ALL.TXT pair for " + run)


def stamp_plus(stamp, k):
    return C.stamp_of(C.epoch(stamp) + 15 * k)


def pool_blocks():
    """Every valid block (greedy tiling per unbroken valid same-band stretch), with the FRAMING disqualifier applied."""
    global LAG_BAND_S
    feed_lag = {(r["run"], r["stamp"]): r["lag"] / 12000.0 for r in jl(os.path.join(SCR, "feed_all.jsonl")) if "lag" in r}
    import numpy as np
    cal = np.array([v for (run, st), v in feed_lag.items() if run.startswith(("20261004", "20261009"))])
    assert len(cal) == 6736, "calibration n %d != 6,736 (2j)" % len(cal)
    LAG_BAND_S = tuple(float(x) for x in np.percentile(cal, [0.1, 99.9]))
    rows = jl(os.path.join(SCR, "valid.jsonl"))
    by_run = collections.defaultdict(list)
    for r in rows:
        lg = feed_lag.get((r["run"], r["stamp"]))
        if r["valid"] and (lg is None or lg < LAG_BAND_S[0] or lg > LAG_BAND_S[1]):
            r["valid"] = False
            r.setdefault("why", []).append("framing")
        by_run[r["run"]].append(r)
    blocks, exclusions = [], collections.Counter()
    for run in sorted(by_run):
        cyc = sorted(by_run[run], key=lambda r: r["epoch"])
        cur, sid = [], 0

        def flush():
            nonlocal sid, cur
            for k in range(len(cur) // N):
                blk = cur[k * N:(k + 1) * N]
                states = {b["sun"] for b in blk}
                sun = blk[W]["sun"] if len(states) == 1 else "twilight"
                blocks.append({"run": run, "stretch": sid, "band": blk[0]["wsjtx_band"], "sun": sun,
                               "first_stamp": blk[0]["stamp"], "scored_first": blk[W]["stamp"], "last_stamp": blk[-1]["stamp"],
                               "stamps": [b["stamp"] for b in blk], "sun_elev_first_scored": blk[W]["sun_elev"]})
            sid += 1
            cur = []
        for r in cyc:
            ok = r["valid"] and r["wsjtx_band"]
            if ok and cur and (r["epoch"] - cur[-1]["epoch"] != 15 or r["wsjtx_band"] != cur[-1]["wsjtx_band"]):
                flush()
            if ok:
                cur.append(r)
            elif cur:
                flush()
            if not ok:
                for w_ in (r.get("why") or ["unknown"]):
                    exclusions[w_] += 1
        if cur:
            flush()
    for b in blocks:
        b["id"] = hashlib.sha256(("%s|%s" % (b["run"], b["first_stamp"])).encode()).hexdigest()[:12]
    return blocks, exclusions


def draw(blocks):
    bands = sorted({b["band"] for b in blocks})
    cell_quota = int((CAP_CYCLES / len(bands) / 3) // N)
    cells = collections.defaultdict(list)
    for b in blocks:
        cells[(b["band"], b["sun"])].append(b)
    rng = random.Random(SEED)
    chosen, per_cell = [], {}
    for band in bands:
        for sun in ("day", "twilight", "night"):
            pool = cells.get((band, sun), [])
            by_stretch = collections.defaultdict(list)
            for b in pool:
                by_stretch[(b["run"], b["stretch"])].append(b)
            for lst in by_stretch.values():
                rng.shuffle(lst)
            taken = []
            while len(taken) < cell_quota and any(by_stretch.values()):
                keys = [k for k, v in by_stretch.items() if v]
                rng.shuffle(keys)
                for k in keys:
                    if len(taken) >= cell_quota:
                        break
                    taken.append(by_stretch[k].pop())
            for i, b in enumerate(taken):
                b["take_order"] = i + 1                      # the within-cell seeded random order = the round number
            per_cell["%s|%s" % (band, sun)] = {"available": len(pool), "quota": cell_quota, "taken": len(taken)}
            chosen += taken
    chosen.sort(key=lambda b: (b["take_order"], b["band"], {"day": 0, "twilight": 1, "night": 2}[b["sun"]]))
    for g, b in enumerate(chosen):
        b["global_order"] = g + 1
    return bands, cell_quota, per_cell, chosen


def wsjt_decode_counts(path, wanted_stamps):
    """Decodes per cycle stamp in a WSJT-X ALL.TXT: line counts only (the first token of each line)."""
    cnt = collections.Counter()
    rx = re.compile(r"^(\d{6}_\d{6})")
    with open(path, "r", errors="replace") as fh:
        for line in fh:
            m = rx.match(line)
            if m and m.group(1) in wanted_stamps:
                cnt[m.group(1)] += 1
    return cnt


def run_facts(run):
    """Source build, devices and route label of a run, from its own records (contents.md, anova meta, ini copy)."""
    base = os.path.join(ART, run)
    facts = {"route_label": "logged (audio-setup log)" if run.startswith(LOGGED_RUNS) else "attested, mid-run unverified",
             "wsjtx_version": "2.7.0 (attested by the Captain, 2026-10-10)", "ows_device": None, "wsjtx_device": None, "build": None}
    cm = os.path.join(base, "contents.md")
    if os.path.isfile(cm):
        txt = open(cm, encoding="utf8", errors="replace").read()
        m = re.search(r"^Audio device:\s*(.+?)\.\s", txt, re.M)
        if m:
            facts["ows_device"] = m.group(1).strip("* ")[:120]
        m = re.search(r"`([^`\n]+)` at `([0-9a-f]{7,40})`", txt)
        if m:
            facts["build"] = {"branch": m.group(1), "commit": m.group(2), "source": "contents.md (uncommitted changes noted)" if "uncommitted changes present" in txt else "contents.md"}
    meta = os.path.join(base, "anova_report.meta.json")
    if os.path.isfile(meta):
        d = json.load(open(meta, encoding="utf8"))
        facts["build"] = {"branch": d.get("build_branch"), "commit": d.get("build_commit"), "dll_sha256": d.get("dll_sha256"),
                          "shim": d.get("shim"), "nhard": d.get("nhard"), "radio_chain": d.get("radio_chain"), "source": "anova_report.meta.json"}
    for ini in [os.path.join(dp, f) for dp, _d, fs in os.walk(base) for f in fs if f.endswith(".ini")]:
        for line in open(ini, encoding="utf8", errors="replace"):
            if line.startswith("SoundInName="):
                facts["wsjtx_device"] = line.split("=", 1)[1].strip()
    if run.startswith(LOGGED_RUNS):
        jf = os.path.join(base, "audio_setup.jsonl")
        if os.path.isfile(jf):
            first = next(json.loads(l) for l in open(jf, encoding="utf8") if '"snapshot"' in l)
            facts["wsjtx_device"] = (first.get("state", {}).get("wsjtx") or {}).get("SoundInName")
    if facts["wsjtx_device"] is None:
        facts["wsjtx_device"] = "same as OpenWSFZ's (attested)" if facts["ows_device"] else None
    return facts


def stage_plan():
    os.makedirs(OUT, exist_ok=True)
    blocks, excl = pool_blocks()
    bands, cell_quota, per_cell, chosen = draw(blocks)
    # ---- assert the Architect's frozen figures
    problems = []
    if bands != EXPECT["bands"]:
        problems.append("bands %r" % (bands,))
    if cell_quota != EXPECT["cell_quota"]:
        problems.append("cell quota %d" % cell_quota)
    if len(chosen) != EXPECT["blocks"] or len(chosen) * N != EXPECT["cycles"]:
        problems.append("blocks %d cycles %d" % (len(chosen), len(chosen) * N))
    for k, v in EXPECT_CELLS.items():
        if per_cell.get(k, {}).get("taken") != v:
            problems.append("cell %s taken %s expected %d" % (k, per_cell.get(k, {}).get("taken"), v))
    if problems:
        print("PLAN REFUSED, differs from the Architect's frozen figures:", problems)
        return 2
    # ---- strata: activity (WSJT-X decodes in the scored cycles; tertiles over the whole valid pool), route, build
    needed = collections.defaultdict(set)
    for b in blocks:
        needed[b["run"]].update(b["stamps"][W:])
    counts = {}
    for run in needed:
        counts[run] = wsjt_decode_counts(src_all_txt(run)[1], needed[run])
    for b in blocks:
        b["activity_decodes"] = sum(counts[b["run"]].get(s, 0) for s in b["stamps"][W:])
    acts = sorted(b["activity_decodes"] for b in blocks)
    t1, t2 = acts[len(acts) // 3], acts[2 * len(acts) // 3]
    for b in chosen:
        b["activity_tertile"] = "low" if b["activity_decodes"] < t1 else ("mid" if b["activity_decodes"] < t2 else "high")
    facts = {run: run_facts(run) for run in sorted({b["run"] for b in chosen})}
    dry = json.load(open(os.path.join(SCR, "draw_dryrun_framing.json")))
    if {b["id"] for b in dry["blocks"]} != {b["id"] for b in chosen}:
        print("PLAN REFUSED: the block set differs from the dry run the Architect accepted (draw_dryrun_framing.json)")
        return 2
    print("draw identical to the accepted dry run: %d block ids equal" % len(chosen))
    plan = {"framing_band_s": list(LAG_BAND_S), "samefeed_bar": SAMEFEED_BAR, "W": W, "L": L, "n": N, "seed": SEED, "bands": bands, "cell_quota_blocks": cell_quota, "per_cell": per_cell,
            "pool_blocks": len(blocks), "activity_tertile_cuts_decodes_per_32_scored_cycles": [t1, t2],
            "valid_cycle_exclusions_by_reason_in_pool_build": dict(excl), "run_facts": facts,
            "blocks": [{k: v for k, v in b.items()} for b in chosen]}
    json.dump(plan, open(os.path.join(OUT, "plan.json"), "w"), indent=1)
    print("PLAN OK: %d blocks = %d cycles = %.2f h; bands %s; cell quota %d; pool %d blocks; activity cuts %s" %
          (len(chosen), len(chosen) * N, len(chosen) * N * 15 / 3600, bands, cell_quota, len(blocks), (t1, t2)))
    for k, v in per_cell.items():
        print("  %-14s available %3d  taken %2d" % (k, v["available"], v["taken"]))
    print("by run:", dict(collections.Counter(b["run"][:13] for b in chosen)))
    print("tertiles:", dict(collections.Counter(b["activity_tertile"] for b in chosen)))
    return 0


def stage_copy():
    plan = json.load(open(os.path.join(OUT, "plan.json")))
    if os.path.exists(CORPUS) and os.listdir(CORPUS):
        print("REFUSED: %s exists and is not empty (a changed corpus is a NEW folder, 2b item 5)" % CORPUS)
        return 2
    inv = {}
    by_sha_stamp = collections.defaultdict(list)
    for w in jl(os.path.join(SCR, "wavs.jsonl")):
        pth = w["path"].replace("\\", "/")
        inv[pth] = w["sha"]
        by_sha_stamp[(w["sha"], w.get("stamp"))].append(pth)
    os.makedirs(CORPUS, exist_ok=True)
    seen_key, seen_sha, files, dup_elsewhere = set(), {}, [], 0
    n_files = 0
    for bi, b in enumerate(plan["blocks"]):
        run = b["run"]
        ows_sub, wsj_sub = C.RUNS[run]
        for stamp in b["stamps"]:
            for side, sub, dname in (("OWS", ows_sub, "owsfz"), ("WSJTX", wsj_sub, "wsjt-x")):
                rel = "%s/%s/%s.wav" % (run, sub, stamp)
                src = os.path.join(ART, *rel.split("/"))
                key = (side, stamp)
                if key in seen_key:
                    print("REFUSED: (side, stamp) copied twice:", key)
                    return 2
                seen_key.add(key)
                want = inv.get(rel)
                if want is None:
                    print("REFUSED: not in the inventory:", rel)
                    return 2
                dst = os.path.join(CORPUS, dname, run, stamp + ".wav")
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.copyfile(src, dst)
                got = sha256_file(dst)
                if got != want or sha256_file(src) != want:
                    print("REFUSED: SHA-256 mismatch for", rel)
                    return 2
                if got in seen_sha:
                    print("REFUSED: identical audio under two stamps (anomaly, 2f item 3):", rel, seen_sha[got])
                    return 2
                seen_sha[got] = rel
                dup_elsewhere += max(0, len(by_sha_stamp[(want, stamp)]) - 1)
                files.append({"path": "%s/%s/%s.wav" % (dname, run, stamp), "sha256": got, "size": os.path.getsize(dst), "source": rel})
                n_files += 1
        if (bi + 1) % 20 == 0:
            print("  blocks copied: %d / %d (%d files)" % (bi + 1, len(plan["blocks"]), n_files), flush=True)
    logs = []
    for run in sorted({b["run"] for b in plan["blocks"]}):
        o, w_ = src_all_txt(run)
        for side, srcp, dname in (("OWS", o, "owsfz"), ("WSJTX", w_, "wsjt-x")):
            dst = os.path.join(CORPUS, dname, run, "ALL.TXT")
            shutil.copyfile(srcp, dst)
            got = sha256_file(dst)
            if got != sha256_file(srcp):
                print("REFUSED: ALL.TXT copy mismatch", srcp)
                return 2
            logs.append({"path": "%s/%s/ALL.TXT" % (dname, run), "sha256": got, "size": os.path.getsize(dst),
                         "source": os.path.relpath(srcp, ART).replace("\\", "/")})
    res = {"wav_files": n_files, "wav_bytes": sum(f["size"] for f in files), "all_txt_files": len(logs),
           "duplicate_copies_of_these_cycles_found_elsewhere_on_disk_and_not_used": dup_elsewhere,
           "unique_audio_sha256": len(seen_sha), "files": files, "all_txt": logs}
    json.dump(res, open(os.path.join(OUT, "copy_result.json"), "w"), indent=1)
    print("COPY OK: %d WAVs (%.2f GB), %d ALL.TXT, every SHA-256 equal to source and inventory; %d unique audio hashes; %d on-disk duplicates of these cycles not used" %
          (n_files, res["wav_bytes"] / 1e9, len(logs), len(seen_sha), dup_elsewhere))
    return 0


def stage_scan():
    """3c (a): the standing spectrum scan (qa/endurance/spectrum_scan.py, its own thresholds, per-run-per-side medians) on the COPIED folder."""
    import numpy as np
    sys.path.insert(0, r"D:\Projects\claude\OpenWSFZ\worktrees\qa\qa\endurance")
    import spectrum_scan as SS
    plan = json.load(open(os.path.join(OUT, "plan.json")))
    rows = []
    for dname in ("owsfz", "wsjt-x"):
        for run in sorted({b["run"] for b in plan["blocks"]}):
            d = os.path.join(CORPUS, dname, run)
            fns = sorted(f for f in os.listdir(d) if f.lower().endswith(".wav"))
            grp = []
            for fn in fns:
                try:
                    r = SS.analyse_file(os.path.join(d, fn))
                except Exception as e:  # noqa: BLE001
                    r = {"error": "%s: %s" % (type(e).__name__, e)}
                r.update(side=dname, run=run, stamp=fn[:-4])
                grp.append(r)
            good = [r for r in grp if "error" not in r]
            med = float(np.median([r["dbfs"] for r in good])) if good else float("nan")
            for r in grp:
                fl = []
                if "error" in r:
                    fl.append("error")
                else:
                    if r["fs"] != SS.FS_EXPECT or r["nframes"] != 180000:
                        fl.append("format")
                    if r["clip_frac"] > 0:
                        fl.append("clipping")
                    if r["dbfs"] < med - SS.SILENCE_BELOW_MEDIAN_DB:
                        fl.append("silent")
                    if r["dbfs"] > med + SS.HOT_ABOVE_MEDIAN_DB and r["clip_frac"] == 0:
                        fl.append("hot")
                    if r["hum1_over_floor_db"] > SS.HUM_OVER_FLOOR_FLAG_DB or r["hum2_over_floor_db"] > SS.HUM_OVER_FLOOR_FLAG_DB:
                        fl.append("hum")
                    if r["peak_to_med_db"] > SS.SPUR_OVER_LOCAL_MEDIAN_DB:
                        fl.append("spur")
                r["flags"] = fl
                r["run_side_median_dbfs"] = med
            rows += grp
            print("  scanned %s/%s: %d files, median %.1f dBFS" % (dname, run[:13], len(grp), med), flush=True)
    DISQ = {"error", "format", "clipping", "silent", "hot"}          # classes that mean bad audio; hum/spur are descriptive (see README)
    flagged = {}
    for r in rows:
        bad = sorted(set(r["flags"]) & DISQ)
        if bad:
            flagged[(r["side"], r["run"], r["stamp"])] = bad
    excluded = []
    for b in plan["blocks"]:
        why = {}
        for stamp in b["stamps"]:
            for side in ("owsfz", "wsjt-x"):
                for f in flagged.get((side, b["run"], stamp), []):
                    why[f] = why.get(f, 0) + 1
        if why:
            excluded.append({"id": b["id"], "run": b["run"], "band": b["band"], "sun": b["sun"], "flagged_cycles_by_class": why})
    counts = collections.Counter(f for r in rows for f in r["flags"])
    per_run = collections.defaultdict(collections.Counter)
    for r in rows:
        for f in r["flags"]:
            per_run[r["run"][:13] + "/" + r["side"]][f] += 1
    out = {"thresholds": {"silent_below_median_db": SS.SILENCE_BELOW_MEDIAN_DB, "hot_above_median_db": SS.HOT_ABOVE_MEDIAN_DB,
                          "hum_over_floor_db": SS.HUM_OVER_FLOOR_FLAG_DB, "spur_over_local_median_db": SS.SPUR_OVER_LOCAL_MEDIAN_DB,
                          "source": "qa/endurance/spectrum_scan.py (standing routine, Captain 2026-09-24); medians per run and side over the copied cycles"},
           "disqualifying_classes": sorted(DISQ), "descriptive_classes": ["hum", "spur"],
           "cycles_scanned": len(rows), "flag_counts": dict(counts), "per_run_side": {k: dict(v) for k, v in per_run.items()},
           "cycles_flagged_disqualifying": len(flagged), "blocks_excluded": excluded,
           "rows": [{"side": r["side"], "run": r["run"], "stamp": r["stamp"], "dbfs": round(r.get("dbfs", float("nan")), 2),
                     "hum1": round(r.get("hum1_over_floor_db", float("nan")), 1), "hum2": round(r.get("hum2_over_floor_db", float("nan")), 1),
                     "peak_to_med": round(r.get("peak_to_med_db", float("nan")), 1), "flags": r["flags"]} for r in rows]}
    json.dump(out, open(os.path.join(OUT, "scan.json"), "w"))
    print("SCAN OK: %d cycles; flag counts %s; cycles flagged with a disqualifying class: %d; blocks excluded: %d of %d" %
          (len(rows), dict(counts), len(flagged), len(excluded), len(plan["blocks"])))
    return 0


def stage_freeze():
    import csv
    import datetime as dt
    import subprocess
    plan = json.load(open(os.path.join(OUT, "plan.json")))
    scan = json.load(open(os.path.join(OUT, "scan.json")))
    cp = json.load(open(os.path.join(OUT, "copy_result.json")))
    for f in ("manifest.json", "MANIFEST.sha256"):
        if os.path.exists(os.path.join(CORPUS, f)):
            print("REFUSED: %s already exists (already frozen?)" % f)
            return 2
    # 1. per-cycle scan file
    scp = os.path.join(CORPUS, "scan_cycles.csv")
    with open(scp, "w", newline="", encoding="utf8") as fh:
        wr = csv.writer(fh)
        wr.writerow(["side", "run", "stamp", "dbfs", "hum1_over_floor_db", "hum2_over_floor_db", "peak_to_median_db", "flags"])
        for r in scan["rows"]:
            wr.writerow([r["side"], r["run"], r["stamp"], r["dbfs"], r["hum1"], r["hum2"], r["peak_to_med"], "+".join(r["flags"])])
    # 2. gain / volume events per block (only the two runs that have an audio-setup log)
    gv = {}
    for run in plan["run_facts"]:
        if run.startswith(LOGGED_RUNS):
            ev = [e for e in jl(os.path.join(ART, run, "audio_setup.jsonl")) if e.get("type") == "change"
                  and any(k in e.get("field", "") for k in (".gain", ".volume"))]
            gv[run] = sorted(dt.datetime.fromisoformat((e.get("detected_utc") or e["utc"]).replace("Z", "+00:00")).timestamp() for e in ev)
    excl = {e["id"]: e for e in scan["blocks_excluded"]}
    blocks = []
    for b in plan["blocks"]:
        t0 = C.epoch(b["stamps"][0])
        t1 = C.epoch(b["stamps"][-1]) + 15
        e = excl.get(b["id"])
        reason = None
        if e:
            reason = "corpus scan: " + ", ".join("%s x%d" % kv for kv in sorted(e["flagged_cycles_by_class"].items()))
        blocks.append({
            "id": b["id"], "run": b["run"], "band": b["band"], "sun": b["sun"], "sun_elevation_first_scored_deg": b["sun_elev_first_scored"],
            "stretch": b["stretch"], "round": b["take_order"], "global_order": b["global_order"],
            "activity_decodes_in_scored_cycles": b["activity_decodes"], "activity_tertile": b["activity_tertile"],
            "route": plan["run_facts"][b["run"]]["route_label"],
            "gain_volume_events_in_block": (sum(1 for t in gv[b["run"]] if t0 <= t < t1) if b["run"] in gv else "no audio-setup log for this run"),
            "first_stamp": b["first_stamp"], "scored_first": b["scored_first"], "last_stamp": b["last_stamp"],
            "warmup_cycles": W, "scored_cycles": L, "cycles": b["stamps"],
            "excluded": bool(e), "excluded_reason": reason})
    usable = [b for b in blocks if not b["excluded"]]
    cells = collections.defaultdict(lambda: {"drawn": 0, "usable": 0})
    for b in blocks:
        key = "%s|%s" % (b["band"], b["sun"])
        cells[key]["drawn"] += 1
        cells[key]["usable"] += 0 if b["excluded"] else 1
    # 3. file list (every file except the manifest and its hash file)
    files = {f["path"]: f for f in cp["files"] + cp["all_txt"]}
    for rel in ("README.md", "scan_cycles.csv"):
        pth = os.path.join(CORPUS, rel)
        files[rel] = {"path": rel, "sha256": sha256_file(pth), "size": os.path.getsize(pth)}
    on_disk = {os.path.relpath(os.path.join(dp, fn), CORPUS).replace(chr(92), "/") for dp, _d, fns in os.walk(CORPUS) for fn in fns}
    on_disk -= {"manifest.json", "MANIFEST.sha256"}
    if on_disk != set(files):
        print("REFUSED: the folder and the file list differ: extra %s missing %s" % (sorted(on_disk - set(files))[:3], sorted(set(files) - on_disk)[:3]))
        return 2
    prov = {}
    for name, pth in (("valid.jsonl", os.path.join(SCR, "valid.jsonl")), ("feed_all.jsonl", os.path.join(SCR, "feed_all.jsonl")),
                      ("wavs.jsonl", os.path.join(SCR, "wavs.jsonl")), ("frozen_bar.json", os.path.join(SCR, "frozen_bar.json")),
                      ("draw_dryrun_framing.json", os.path.join(SCR, "draw_dryrun_framing.json")), ("plan.json", os.path.join(OUT, "plan.json")),
                      ("scan.json", os.path.join(OUT, "scan.json")), ("copy_result.json", os.path.join(OUT, "copy_result.json")),
                      ("build_corpus.py", os.path.abspath(__file__))):
        prov[name] = sha256_file(pth)
    head = subprocess.run(["git", "-C", os.path.dirname(os.path.abspath(__file__)), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    manifest = {
        "corpus": "rr-s6-refset-corpus", "frozen_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "spec": "REFERENCE-SET 2b-2j (arch/reference-set); W pilot ruling 2i; framing 2j",
        "go": "the Captain, QA window, 2026-10-11: do the REFERENCE-SET corpus build and freeze",
        "W": W, "L": L, "block_cycles": N, "cap_cycles": CAP_CYCLES, "seed": SEED, "bands": plan["bands"], "cell_quota_blocks": plan["cell_quota_blocks"],
        "pins": {"same_feed_bar": SAMEFEED_BAR, "framing_lag_band_s_exact": plan["framing_band_s"], "framing_lag_band_s_as_printed_in_spec": [-0.040, 0.009],
                 "calibration_runs": ["20261004_1634", "20261009_1752"], "calibration_cycles": 6736},
        "attestation": ATTESTATION, "wsjtx_version_all_runs": "2.7.0 (attested; accepted by the Architect, 2g (a))",
        "totals": {"blocks_drawn": len(blocks), "blocks_excluded_by_scan": len(blocks) - len(usable), "blocks_usable": len(usable),
                   "cycles_drawn": len(blocks) * N, "cycles_usable": len(usable) * N, "hours_usable": round(len(usable) * N * 15 / 3600, 2),
                   "shortfall_to_48h_hours": round(48 - len(usable) * N * 15 / 3600, 2), "wav_files": cp["wav_files"], "wav_bytes": cp["wav_bytes"]},
        "cells": dict(sorted(cells.items())), "cell_availability_in_pool": plan["per_cell"],
        "absent_or_thin": {"10m": "ABSENT: no correctly framed 10 m recording on disk", "17m_night": "EMPTY", "17m_twilight": "thin (3 blocks)",
                           "17m": "single run", "80m": "thin (27 blocks) and single run"},
        "pool": {"valid_blocks_before_quota": plan["pool_blocks"],
                 "activity_tertile_cuts_decodes_per_32_scored_cycles": plan["activity_tertile_cuts_decodes_per_32_scored_cycles"],
                 "cycle_exclusions_by_reason_in_pool_build": plan["valid_cycle_exclusions_by_reason_in_pool_build"]},
        "duplicates": {"audio_sha256_unique_in_corpus": cp["unique_audio_sha256"],
                       "other_files_with_the_same_stamp_and_identical_audio_found_elsewhere_and_not_used": cp["duplicate_copies_of_these_cycles_found_elsewhere_on_disk_and_not_used"],
                       "rule": "one copy per (stamp, side) and per SHA-256, from the primary source named per file; the -8081 twin instances are excluded"},
        "scan": {"thresholds": scan["thresholds"], "disqualifying_classes": scan["disqualifying_classes"], "descriptive_classes": scan["descriptive_classes"],
                 "cycles_scanned": scan["cycles_scanned"], "flag_counts": scan["flag_counts"], "per_run_side": scan["per_run_side"],
                 "blocks_excluded": scan["blocks_excluded"],
                 "decision_for_review": "hum and spur are recorded per cycle but do not disqualify (they fire on 67 % and 60 % of all cycles on every run); QA decision, not yet reviewed by the Architect"},
        "capture_session_mutes": "none found in the two audio-setup logs (application-session mutes are reported only)",
        "runs": plan["run_facts"], "provenance_sha256": prov, "harness_git_head_at_build": head,
        "blocks": blocks, "files": [files[k] for k in sorted(files)]}
    mp = os.path.join(CORPUS, "manifest.json")
    json.dump(manifest, open(mp, "w", encoding="utf8"), indent=1)
    open(os.path.join(CORPUS, "MANIFEST.sha256"), "w", encoding="utf8").write(sha256_file(mp) + "  manifest.json" + chr(10))
    # 4. read-only, then verify once
    r = subprocess.run(["attrib", "+R", os.path.join(CORPUS, "*"), "/S", "/D"], capture_output=True, text=True)
    print("attrib +R rc", r.returncode, (r.stderr or "").strip()[:100])
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import verify_corpus as V
    ok, problems, n = V.verify(CORPUS)
    print("FREEZE %s: %d files verified; %s" % ("OK" if ok else "PROBLEM", n, problems[:3]))
    return 0 if ok else 1


if __name__ == "__main__":
    stage = sys.argv[1] if len(sys.argv) > 1 else ""
    if stage == "plan":
        sys.exit(stage_plan())
    if stage == "copy":
        sys.exit(stage_copy())
    if stage == "scan":
        sys.exit(stage_scan())
    if stage == "freeze":
        sys.exit(stage_freeze())
    print(__doc__)
    sys.exit(1)
