"""Same-chain check, option (a) (COH-RES-CAND spec section 7 + A1.6/A1.7): chain-vs-offline under `frans`.

    python same_chain_compare.py --playlog <s6_playlog.jsonl> --all-txt <daemon ALL.TXT> --offline <R-OFF-1.decodes.tsv> [--offline2 <R-OFF-2.decodes.tsv>]
                                 --wavlist <offline_wavs.tsv> --out <result.json>

The CHAIN leg: s6_play plays the 24 quick-tier WAVs twice (trial 0, trial 1; a different shuffle each) into Voicemeeter AUX -> B1 -> the daemon, whose ALL.TXT
holds the decodes. The OFFLINE leg: the same WAVs through RefSet (the live decode call), twice. A play is matched to its WAV by the slot stamp in the play log.

PREDICATES, FIXED BEFORE ANY RESULT WAS READ (HK-021/038). Every tolerance is the chain's OWN repeatability, never an invented number. The only constant is the
reporting resolution of SNR (whole dB, so 1 dB is the floor below which a difference is quantisation, not signal).
  Signal key = the message text (hashed `<...>` texts are kept; the process-global hash table differs with play order, reported, not excluded).
  Per WAV w: S_c0(w), S_c1(w) = chain trial 0 / 1 text sets; S_o(w) = offline text set (first offline run).
  T_sig   = max over w of |S_c0 symmetric-difference S_c1|             (the chain against itself)
  T_count = max over w of | |S_c0| - |S_c1| |
  T_snr   = max(1 dB, 95th percentile of |snr_c0 - snr_c1| over texts in both trials)
  V-SIG   : share of (trial, w) pairs with |S_ct symmetric-difference S_o| <= T_sig  is  >= 0.95
  V-COUNT : share of (trial, w) pairs with | |S_ct| - |S_o| | <= T_count            is  >= 0.95
  V-SNR   : 95th percentile of |snr_c - snr_o| over texts in both (chain trial, offline)  <=  T_snr
  V-PLAY  : every one of the 48 plays has its slot in the daemon's ALL.TXT window (no play lost to the chain), and 24 WAVs matched. AMENDMENT 2: a WAV is exempt
            only if it has 0 decodes in the reference AND 0 in both chain trials.
  VERDICT : PASS iff V-PLAY, V-SIG, V-COUNT and V-SNR all hold. Anything else is FAIL, with the numbers. PASS means the frans chain delivers audio the decoder
            reads like the offline decode of the same WAVs, within the chain's own repeatability. It CANNOT show equality with Frank's chain: no Frank-era record
            of the same WAVs through the same chain exists (A1.6).
Offline repeatability (R-OFF-1 vs R-OFF-2) is reported as a control: it should be 0.

HK-037 / NFR-021: message text is read here, inside the reading functions, and never printed or written; the output is aggregates only.
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "rr-study"))

SHARE_BAR = 0.95
SNR_FLOOR_DB = 1.0       # whole-dB reporting resolution


def pctile(vals, p):
    v = sorted(vals)
    return v[min(len(v) - 1, int(round(p * (len(v) - 1))))] if v else 0.0


def read_chain(all_txt: Path):
    """slot stamp -> list of (text, snr)."""
    from harness.common import parse_all_txt
    recs, _ = parse_all_txt(all_txt)
    out: dict[str, list] = {}
    for r in recs:
        out.setdefault(r.utc.strftime("%y%m%d_%H%M%S"), []).append((r.message, r.snr_db))
    return out


def read_offline(tsv: Path, wavlist: Path):
    """WAV stamp -> list of (text, snr)."""
    idx_to_stamp = {}
    for ln in wavlist.read_text(encoding="utf-8").splitlines():
        i, _p, st = ln.split("\t")
        idx_to_stamp[int(i)] = st
    out: dict[str, list] = {st: [] for st in idx_to_stamp.values()}
    lines = tsv.read_text(encoding="utf-8").splitlines()[1:]
    for ln in lines:
        f = ln.split("\t")
        out[idx_to_stamp[int(f[0])]].append((f[5], float(f[2])))
    return out


def compare(playlog: Path, all_txt: Path, offline: Path, offline2: Path | None, wavlist: Path) -> dict:
    plays = [json.loads(x) for x in playlog.read_text(encoding="utf-8").splitlines()]
    plays = [p for p in plays if p["kind"] == "play"]
    chain = read_chain(all_txt)
    off = read_offline(offline, wavlist)
    off2 = read_offline(offline2, wavlist) if offline2 else None
    stamp_of = {p["wav_id"]: p["wav_id"].split(":")[1] for p in plays}
    # chain decodes per (wav, trial)
    c: dict[tuple, list] = {}
    missing_slots = []
    for p in plays:
        if p["slot_stamp"] not in chain:
            missing_slots.append(stamp_of[p["wav_id"]])
        c[(stamp_of[p["wav_id"]], p["trial"])] = chain.get(p["slot_stamp"], [])
    wavs = sorted({w for w, _t in c})
    # AMENDMENT 2 (spec section 10, Architect 2026-11-08): a play with no slot in the chain log counts as LOST unless its WAV has 0 decodes in the reference AND
    # 0 in both chain trials (a WAV with nothing decodable writes no line; that is not a lost play).
    lost = sum(1 for w in missing_slots
               if not (len(off[w]) == 0 and len(c[(w, 0)]) == 0 and len(c[(w, 1)]) == 0))
    S = lambda lst: {t for t, _s in lst}
    snr = lambda lst: {t: s for t, s in lst}

    t_sig = max(len(S(c[(w, 0)]) ^ S(c[(w, 1)])) for w in wavs)
    t_count = max(abs(len(S(c[(w, 0)])) - len(S(c[(w, 1)]))) for w in wavs)
    rep_snr = []
    for w in wavs:
        a, b = snr(c[(w, 0)]), snr(c[(w, 1)])
        rep_snr += [abs(a[t] - b[t]) for t in a.keys() & b.keys()]
    t_snr = max(SNR_FLOOR_DB, pctile(rep_snr, 0.95))

    pairs = [(w, t) for w in wavs for t in (0, 1)]
    sig_ok = sum(1 for w, t in pairs if len(S(c[(w, t)]) ^ S(off[w])) <= t_sig)
    cnt_ok = sum(1 for w, t in pairs if abs(len(S(c[(w, t)])) - len(S(off[w]))) <= t_count)
    cmp_snr = []
    for w, t in pairs:
        a, b = snr(c[(w, t)]), snr(off[w])
        cmp_snr += [abs(a[x] - b[x]) for x in a.keys() & b.keys()]
    p95_cmp = pctile(cmp_snr, 0.95)

    v_play = lost == 0 and len(wavs) == 24 and len(plays) == 48
    v_sig = sig_ok / len(pairs) >= SHARE_BAR
    v_cnt = cnt_ok / len(pairs) >= SHARE_BAR
    v_snr = p95_cmp <= t_snr

    off_rep = None
    if off2:
        off_rep = {"max_sig_symdiff": max(len(S(off[w]) ^ S(off2[w])) for w in wavs),
                   "max_count_diff": max(abs(len(S(off[w])) - len(S(off2[w]))) for w in wavs)}
    return {
        "plays": len(plays), "wavs": len(wavs), "plays_lost_from_chain_log": lost,
        "chain_decodes_total": sum(len(v) for v in c.values()), "offline_decodes_total": sum(len(v) for v in off.values()),
        "tolerances_from_chain_repeat": {"T_sig": t_sig, "T_count": t_count, "T_snr_db": t_snr, "snr_floor_db": SNR_FLOOR_DB, "repeat_snr_pairs": len(rep_snr)},
        "chain_vs_offline": {"pairs": len(pairs), "sig_within_T_sig": sig_ok, "count_within_T_count": cnt_ok, "snr_pairs": len(cmp_snr),
                             "snr_abs_diff_p95_db": p95_cmp, "snr_abs_diff_median_db": statistics.median(cmp_snr) if cmp_snr else None,
                             "mean_sig_symdiff": statistics.mean(len(S(c[k]) ^ S(off[k[0]])) for k in pairs),
                             "mean_sig_symdiff_chain_repeat": statistics.mean(len(S(c[(w, 0)]) ^ S(c[(w, 1)])) for w in wavs)},
        "offline_repeat_control": off_rep,
        "rows": {"V-PLAY": v_play, "V-SIG": v_sig, "V-COUNT": v_cnt, "V-SNR": v_snr},
        "verdict": "PASS" if (v_play and v_sig and v_cnt and v_snr) else "FAIL",
        "note": "cannot show equality with Frank's chain (no Frank-era record of the same WAVs through the same chain exists)",
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--playlog", required=True)
    ap.add_argument("--all-txt", required=True)
    ap.add_argument("--offline", required=True)
    ap.add_argument("--offline2", default=None)
    ap.add_argument("--wavlist", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    res = compare(Path(a.playlog), Path(a.all_txt), Path(a.offline), Path(a.offline2) if a.offline2 else None, Path(a.wavlist))
    txt = json.dumps(res, indent=1)
    Path(a.out).write_text(txt, encoding="utf-8")
    print(txt)


if __name__ == "__main__":
    main()
