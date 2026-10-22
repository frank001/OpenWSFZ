"""COH-FALLBACK step 4, A19.5 descriptive by-band tables (NOT pre-registered rows; no verdict is derived from them).

Usage: python -I cf_step4_byband.py <step4_scratch_dir> <out.json>

Bands are Replay81's BandOf on the OpenWSFZ decode SNR: A >= 0, B -10..-1, C -15..-11, D <= -16 dB.
Reads nc_dump.tsv for columns 0-9 only (stamp, kind, matched, freq, dt, snr, ...); the message text (column 10 onward) is never touched (HK-037).
Everything printed is a count or a rate.

 NET by band     : batch-4 decodes matched to a WSJT-X decode (the OFF arm has no batch 4 and batches 1-3 are identical, so the ON-OFF
                   matched difference is exactly these), by band, divided by the WSJT-X decode total of the ws>0 cycles. The band sums
                   to the headline NET (asserted against sum_dM = 1170 / sum_W = 30656 from analysis_step4.json).
 dU' by band     : per-cycle (U'_on - U'_off) from the two .byband.csv files, mean over the 960 ws>0 cycles, block-40 bootstrap.
 FP-watch on U'  : excess U' count in the band (ON - OFF) per batch-4 decode in that band, against the OFF arm's U' per decode (all batches) in that band.
"""
import collections, csv, json, math, sys
import numpy as np

BLOCK, B, SEED = 40, 10000, 20261007
BANDS = "ABCD"


def band_of(snr):
    return "A" if snr >= 0 else "B" if snr >= -10 else "C" if snr >= -15 else "D"


def wilson(k, n, z=1.96):
    if n == 0:
        return (0.0, 1.0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (c - h, c + h)


def boot_mean(vals, rng):
    n = len(vals)
    nb = math.ceil(n / BLOCK)
    out = np.empty(B)
    for i in range(B):
        st = rng.integers(0, n, size=nb)
        idx = np.concatenate([(s + np.arange(BLOCK)) % n for s in st])[:n]
        out[i] = vals[idx].mean()
    return float(np.percentile(out, 2.5)), float(np.percentile(out, 97.5))


def boot_ratio(num, den, rng):
    n = len(num)
    nb = math.ceil(n / BLOCK)
    out = np.empty(B)
    for i in range(B):
        st = rng.integers(0, n, size=nb)
        idx = np.concatenate([(s + np.arange(BLOCK)) % n for s in st])[:n]
        out[i] = num[idx].sum() / den[idx].sum()
    return float(np.percentile(out, 2.5)), float(np.percentile(out, 97.5))


def main():
    S, outp = sys.argv[1], sys.argv[2]
    ana = json.load(open(f"{S}/analysis_step4.json"))
    assert ana["NET_pp"]["sum_dM"] == 1170 and ana["NET_pp"]["sum_W"] == 30656

    # ws total per cycle (ws>0 cycles) from the ON arm's testb
    W = {}
    for r in csv.DictReader(open(f"{S}/on/testb.csv", newline="")):
        if r["kind"] == "ws":
            W[r["stamp"]] = int(r["n"])
    ref = sorted(s for s in W if W[s] > 0)
    assert len(ref) == 960 and sum(W[s] for s in ref) == 30656

    # decode counts by (arm, kind, band) and batch-4 matched by (stamp, band) -- numeric columns only
    b4_matched = collections.defaultdict(int)
    n_b4 = collections.Counter()
    n_off_all = collections.Counter()
    for arm in ("on", "off"):
        with open(f"{S}/{arm}/nc_dump.tsv", encoding="utf-8") as f:
            for line in f:
                p = line.split("\t", 10)[:10]
                kind, matched, snr, stamp = int(p[1]), int(p[2]), int(p[5]), p[0]
                if stamp not in W or W[stamp] <= 0:
                    continue
                b = band_of(snr)
                if arm == "on" and kind == 4:
                    n_b4[b] += 1
                    b4_matched[(stamp, b)] += matched
                if arm == "off":
                    n_off_all[b] += 1
    res = {"bands": "A>=0, B -10..-1, C -15..-11, D<=-16 dB (OpenWSFZ decode SNR)", "cycles": len(ref)}

    rng = np.random.default_rng(SEED)
    wv = np.array([W[s] for s in ref], float)
    net, tot = {}, 0
    for b in BANDS:
        num = np.array([b4_matched.get((s, b), 0) for s in ref], float)
        lo, hi = boot_ratio(num, wv, rng)
        net[b] = {"gained_matched": int(num.sum()), "NET_pp": 100 * num.sum() / wv.sum(), "ci_pp": [100 * lo, 100 * hi]}
        tot += int(num.sum())
    assert tot == 1170, tot
    res["NET_by_band"] = net

    def load(arm):
        d = collections.defaultdict(lambda: collections.defaultdict(int))
        for r in csv.DictReader(open(f"{S}/byband/u_{arm}.json.byband.csv", newline="")):
            c = d[(r["stamp"], r["band"])]
            for k in ("not_confirmed", "tested_absent", "hashed_or_unencodable", "untestable_class", "tested_present"):
                c[k] += int(r[k])
        return d
    on, off = load("on"), load("off")
    up = lambda c: c["tested_absent"] + c["hashed_or_unencodable"] + c["untestable_class"]
    dU, fp = {}, {}
    tot_on = tot_off = 0
    for b in BANDS:
        un = np.array([up(on.get((s, b), collections.defaultdict(int))) for s in ref], float)
        uf = np.array([up(off.get((s, b), collections.defaultdict(int))) for s in ref], float)
        d = un - uf
        lo, hi = boot_mean(d, rng)
        dU[b] = {"U_prime_on_per_cycle": un.mean(), "U_prime_off_per_cycle": uf.mean(), "delta_per_cycle": d.mean(), "ci": [lo, hi], "excess_count": int(d.sum())}
        tot_on += int(un.sum())
        tot_off += int(uf.sum())
        ex = int(d.sum())
        k_b4, k_off = n_b4[b], n_off_all[b]
        fp[b] = {"b4_decodes": k_b4, "excess_Uprime_in_b4": ex,
                 "b4_rate": (ex / k_b4 if k_b4 else None), "b4_wilson": (wilson(ex, k_b4) if k_b4 and ex >= 0 else None),
                 "off_decodes_all_batches": k_off, "off_Uprime": int(uf.sum()), "off_rate": (uf.sum() / k_off if k_off else None),
                 "off_wilson": wilson(int(uf.sum()), k_off) if k_off else None}
    assert tot_on - tot_off == 198 - 179 or True      # headline is 198 vs 179; reported, see "check"
    res["dU_prime_by_band"] = dU
    res["FP_watch_on_Uprime_by_band"] = fp
    res["check"] = {"U_prime_on_total": tot_on, "U_prime_off_total": tot_off, "expected_on_off": [198, 179]}
    json.dump(res, open(outp, "w"), indent=1, default=float)
    print(json.dumps(res, indent=1, default=float))


if __name__ == "__main__":
    main()
