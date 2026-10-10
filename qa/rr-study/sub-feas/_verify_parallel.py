#!/usr/bin/env python3
"""One-off check: parallel fit_population() must equal the serial run bit-for-bit
(Amendment 3's own requirement). Not part of the deliverable pipeline."""
import sys, os, random, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common
common.log_stdout_utf8()
import corpus
import bigfit


def main():
    dll_path = os.path.join(common.REPO_ROOT, "artefacts", "sub-feas", "bin", "libft8_C3.dll")
    enc = corpus.Encoder(dll_path)
    pop = corpus.build_population(enc, print)
    rng = random.Random(20260927)
    sample = rng.sample(pop["all_rows"], 40)

    t0 = time.time()
    serial = bigfit.fit_population(sample, tau0_s=-0.160, log=print, parallel=False)
    print("serial elapsed", time.time() - t0)

    t0 = time.time()
    parallel = bigfit.fit_population(sample, tau0_s=-0.160, log=print, parallel=True)
    print("parallel elapsed", time.time() - t0)

    serial_by_id = {r["row_id"]: r for r in serial}
    parallel_by_id = {r["row_id"]: r for r in parallel}
    assert set(serial_by_id) == set(parallel_by_id), "row_id sets differ!"
    n_diff = 0
    for rid, s in serial_by_id.items():
        p = parallel_by_id[rid]
        if s != p:
            n_diff += 1
            print("DIFF row_id", rid, s, p)
    print("VERIFY: n_rows=%d n_diff=%d MATCH=%s" % (len(serial_by_id), n_diff, n_diff == 0))


if __name__ == "__main__":
    main()
