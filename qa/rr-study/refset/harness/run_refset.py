"""REFERENCE-SET block runner and gate driver, legs A and D (QA). Platform-neutral: runs on this PC and on sol.

    python -s -E run_refset.py --corpus <frozen corpus> --bin <dir with RefSet.dll + the native library under test> \
        --scratch <job dir OUTSIDE git> --pass <name> --run <corpus run name> --legs A,D --expect-native-sha <sha256> [--label "..."]

Spec: REFERENCE-SET 2c, 2l (arch/reference-set). The rules this driver enforces:
  * verify_corpus first (MANIFEST + every file's size and SHA-256), unless --skip-verify, which is recorded in the pins;
  * ONE decode process at a time, a fresh process per block and leg (the callsign hash table is process-global);
  * the native library's SHA-256 must equal --expect-native-sha at the start and at the end of every block;
  * a block with any residual-pass abandonment is re-run ONCE alone; if it abandons again the driver STOPS (exit 10): never relax the
    deadline, never skip silently (2l item 2: "STOP and ask");
  * blocks are checkpointed (a finished block's summary json is the checkpoint); a stopped run resumes;
  * excluded blocks are skipped, never replaced (2l item 4);
  * the working files (message text) live under --scratch and nowhere else; aggregates only on stdout and in the aggregate json files.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "corpus"))
import refset_score as rs  # noqa: E402

NHARD, SIGN_FIX, THREADS = 24, 1, 8          # the live readback of the station's settings (shim 20260060/61, OSD sign fix on, 8 threads)
EXIT_ABANDON = 10
QUICK_ROUNDS, STANDARD_ROUNDS, DEEP_BLOCKS = 1, 3, 96
RERUN_LIMIT = 1                                # an abandoning block is re-run once, alone (2l item 2)
RSV2_REPRO_BAR, RSV2_EXTRA_BAR = 0.99, 0.01   # RS-V2's own frozen bar, unchanged (spec 6)


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def native_name() -> str:
    return "libft8.dll" if os.name == "nt" else ("libft8.dylib" if sys.platform == "darwin" else "libft8.so")


def load1() -> float | None:
    try:
        return os.getloadavg()[0]
    except (AttributeError, OSError):
        return None


def select_blocks(manifest: dict, tier: str | None, run: str | None) -> list[dict]:
    usable = [b for b in manifest["blocks"] if not b["excluded"]]
    usable.sort(key=lambda b: (b["round"], b["global_order"]))
    if run:
        return [b for b in usable if b["run"] == run]
    if tier == "quick":
        return [b for b in usable if b["round"] <= QUICK_ROUNDS]
    if tier == "standard":
        return [b for b in usable if b["round"] <= STANDARD_ROUNDS]
    if tier == "deep":
        return usable[:DEEP_BLOCKS]
    if tier == "full":
        return usable
    raise SystemExit("give --tier quick|standard|deep|full or --run <corpus run name>")


def run_block(args, blk: dict, leg: str, pass_name: str, pass_dir: str, pins_path: str) -> dict:
    """Decode one block on one leg; returns the summary dict. Resumes from the summary json if it exists."""
    legdir = os.path.join(pass_dir, leg)
    sumpath = os.path.join(legdir, blk["id"] + ".json")
    if os.path.exists(sumpath) and os.path.exists(os.path.join(legdir, blk["id"] + ".decodes.tsv")):
        s = rs.load_json(sumpath)
        s["_resumed"] = True
        return s
    audio_leg = "A" if leg in ("A", "D") else "B"             # D re-decodes A's audio in a second process
    for attempt in range(1 + RERUN_LIMIT):
        cmd = ["dotnet", os.path.join(args.bin, "RefSet.dll"), "--manifest", os.path.join(args.corpus, "manifest.json"), "--corpus", args.corpus,
               "--block", blk["id"], "--leg", audio_leg, "--out-dir", args.scratch, "--pass", pass_name + "-" + leg if leg == "D" else pass_name,
               "--jit-wav", args.jit_wav, "--nhard", str(NHARD), "--osd-sign-fix", str(SIGN_FIX), "--threads", str(THREADS), "--label", args.label]
        lo = load1()
        t0 = time.time()
        p = subprocess.run(cmd, capture_output=True, text=True)
        if p.returncode != 0:
            raise SystemExit("HARNESS FAILED rc=%d %s" % (p.returncode, p.stderr.strip()[:200]))
        # for leg D the harness wrote under pass "<name>-D"/A; move it into this pass's D folder
        if leg == "D":
            src = os.path.join(args.scratch, pass_name + "-D", "A")
            os.makedirs(legdir, exist_ok=True)
            for ext in (".decodes.tsv", ".json"):
                os.replace(os.path.join(src, blk["id"] + ext), os.path.join(legdir, blk["id"] + ext))
        s = rs.load_json(sumpath)
        s["_load1_before"], s["_attempt"], s["_driver_wall_s"] = lo, attempt + 1, round(time.time() - t0, 1)
        with open(pins_path, "a") as pf:
            pf.write(json.dumps({"utc": now(), "block": blk["id"], "leg": leg, "attempt": attempt + 1, "native_sha256_start": s["native_sha256_start"],
                                 "native_sha256_end": s["native_sha256_end"], "abandoned": s["residual_pass"]["abandoned"], "ran": s["residual_pass"]["ran"],
                                 "wall_s": s["wall_s"], "cpu_s": s["cpu_s"], "load1_before": lo}) + "\n")
        if s["native_sha256_start"] != args.expect_native_sha or s["native_sha256_end"] != args.expect_native_sha:
            raise SystemExit("PIN FAILED: native library SHA differs from --expect-native-sha")
        if s["residual_pass"]["abandoned"] == 0:
            return s
        print(f"{now()} ABANDONMENT block {blk['id']} leg {leg} attempt {attempt + 1}: {s['residual_pass']['abandoned']} of {s['residual_pass']['ran']}", flush=True)
        for ext in (".decodes.tsv", ".json"):                    # discard the abandoning attempt's outputs; the re-run starts clean
            os.replace(os.path.join(legdir, blk["id"] + ext), os.path.join(legdir, blk["id"] + ".abandoned-attempt%d%s" % (attempt + 1, ext)))
    print(f"{now()} STOP AND ASK: block {blk['id']} abandoned a residual pass at one process on a re-run. The deadline is NOT relaxed.", flush=True)
    sys.exit(EXIT_ABANDON)


def score_a(args, blk: dict, a_work: str) -> dict:
    live_path = os.path.join(args.corpus, "owsfz", blk["run"], "ALL.TXT")
    scored = rs.block_scored_stamps(blk)
    live = rs.read_all_txt(live_path, scored)
    own = rs.read_work(a_work)
    r = rs.score_block(live, own, scored)
    pc = r.pop("_per_cycle")
    r["rsv2"] = rs.rsv2_shares(r["counts"])
    r["_num_nonhashed_repro"] = [c.repro_non_hashed for _, c in pc]
    r["_den_nonhashed_live"] = [c.live_non_hashed for _, c in pc]
    r["_num_nonhashed_extra"] = [c.extra_non_hashed for _, c in pc]
    return r


def score_d(a_work: str, d_work: str, blk: dict) -> dict:
    scored = rs.block_scored_stamps(blk)
    a, d = rs.read_work(a_work), rs.read_work(d_work)
    r = rs.score_block(a, d, scored)           # 'live' = leg A rows, 'own' = leg D rows: lost = A rows missing in D, extra = D rows not in A
    pc = r.pop("_per_cycle")
    r["rsv2"] = rs.rsv2_shares(r["counts"])
    r["_num_nonhashed_repro"] = [c.repro_non_hashed for _, c in pc]
    r["_den_nonhashed_live"] = [c.live_non_hashed for _, c in pc]
    r["_num_nonhashed_extra"] = [c.extra_non_hashed for _, c in pc]
    return r


def pool(blocks_scores: list[dict]) -> dict:
    tot = rs.Counts()
    num, den, ext, equal, sabs, cyc = [], [], [], 0, 0, 0
    for s in blocks_scores:
        c = rs.Counts(**s["counts"])
        tot.add(c)
        num += s["_num_nonhashed_repro"]; den += s["_den_nonhashed_live"]; ext += s["_num_nonhashed_extra"]
        equal += s["cycles_equal_rowcount"]; sabs += s["sum_abs_rowdiff"]; cyc += s["cycles"]
    counts = {f: getattr(tot, f) for f in tot.__dataclass_fields__}
    sh = rs.rsv2_shares(counts)
    return {"counts": counts, "cycles": cyc, "cycles_equal_rowcount": equal, "sum_abs_rowdiff": sabs, "shares": sh,
            "repro_nonhashed_ci95_cycle_clustered": rs.cluster_bootstrap_share(num, den),
            "extra_nonhashed_ci95_cycle_clustered": rs.cluster_bootstrap_share(ext, den)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", required=True)
    ap.add_argument("--bin", required=True, help="folder with RefSet.dll and the native library under test")
    ap.add_argument("--scratch", required=True, help="job folder OUTSIDE git: working files (message text) and aggregates")
    ap.add_argument("--pass", dest="pass_name", required=True)
    ap.add_argument("--tier", choices=["quick", "standard", "deep", "full"])
    ap.add_argument("--run", help="gate mode: all usable blocks of one corpus run (the anchor night)")
    ap.add_argument("--legs", default="A,D")
    ap.add_argument("--d-scope", choices=["all", "quick"], default="all")
    ap.add_argument("--expect-native-sha", required=True)
    ap.add_argument("--jit-wav", required=True)
    ap.add_argument("--label", default="unlabelled")
    ap.add_argument("--skip-verify", action="store_true")
    ap.add_argument("--max-blocks", type=int, default=0, help="stop after this many blocks (0 = all); for timing probes")
    args = ap.parse_args()

    legs = args.legs.split(",")
    pass_dir = os.path.join(args.scratch, args.pass_name)
    os.makedirs(pass_dir, exist_ok=True)
    pins_path = os.path.join(pass_dir, "pins.jsonl")

    # --- pins before any decode
    got = sha256(os.path.join(args.bin, native_name()))
    assert got == args.expect_native_sha, f"native library SHA {got} != pinned {args.expect_native_sha}"
    if not args.skip_verify:
        import verify_corpus
        ok, problems, nfiles = verify_corpus.verify(args.corpus)
        assert ok, "corpus verification failed: %d problems" % len(problems)
        print(f"{now()} corpus verified: {nfiles} files intact", flush=True)
    manifest = rs.load_json(os.path.join(args.corpus, "manifest.json"))
    blocks = select_blocks(manifest, args.tier, args.run)
    if args.max_blocks:
        blocks = blocks[:args.max_blocks]
    with open(pins_path, "a") as pf:
        pf.write(json.dumps({"utc": now(), "event": "start", "native": got, "corpus_manifest_sha256": sha256(os.path.join(args.corpus, "MANIFEST.sha256")),
                             "verify_skipped": args.skip_verify, "blocks": len(blocks), "legs": legs, "label": args.label,
                             "settings": {"nhard": NHARD, "osd_sign_fix": SIGN_FIX, "threads": THREADS}}) + "\n")
    print(f"{now()} start pass {args.pass_name}: {len(blocks)} blocks, legs {legs}, native {got[:12]}", flush=True)

    a_scores, d_scores, timing = [], [], {"A": [], "D": []}
    ab_total = {"A": 0, "D": 0}
    for i, blk in enumerate(blocks, 1):
        sa = run_block(args, blk, "A", args.pass_name, pass_dir, pins_path)
        a_work = os.path.join(pass_dir, "A", blk["id"] + ".decodes.tsv")
        sc = score_a(args, blk, a_work)
        a_scores.append(sc)
        timing["A"].append((sa["wall_s"], sa["cpu_s"]))
        ab_total["A"] += sa["residual_pass"]["abandoned"]
        line = f"{now()} [{i}/{len(blocks)}] block {blk['id']} {blk['band']} {blk['sun']}: A wall {sa['wall_s']}s cpu {sa['cpu_s']}s repro_nonhashed {sc['rsv2']['repro_nonhashed_share']:.4f} extra {sc['rsv2']['extra_nonhashed_share']:.4f}"
        if "D" in legs and (args.d_scope == "all" or blk["round"] <= QUICK_ROUNDS):
            sd = run_block(args, blk, "D", args.pass_name, pass_dir, pins_path)
            d_work = os.path.join(pass_dir, "D", blk["id"] + ".decodes.tsv")
            dsc = score_d(a_work, d_work, blk)
            d_scores.append(dsc)
            timing["D"].append((sd["wall_s"], sd["cpu_s"]))
            ab_total["D"] += sd["residual_pass"]["abandoned"]
            line += f" | D wall {sd['wall_s']}s lost {1 - dsc['rsv2']['repro_nonhashed_share']:.4f} extra {dsc['rsv2']['extra_nonhashed_share']:.4f}"
        print(line, flush=True)
        rs.dump_json(os.path.join(pass_dir, "status.json"), {"utc": now(), "done": i, "of": len(blocks), "abandonments": ab_total})

    # --- aggregate
    out = {"pass": args.pass_name, "label": args.label, "utc": now(), "native_sha256": got, "blocks": len(blocks), "legs": legs,
           "abandonments_first": ab_total, "timing_seconds_per_block": {}}
    for leg in ("A", "D"):
        if timing[leg]:
            w = sorted(t[0] for t in timing[leg]); c = sorted(t[1] for t in timing[leg])
            out["timing_seconds_per_block"][leg] = {"n": len(w), "median_wall": w[len(w) // 2], "max_wall": w[-1], "median_cpu": c[len(c) // 2]}
    if a_scores:
        out["leg_A_vs_live_ows"] = pool(a_scores)
        sh = out["leg_A_vs_live_ows"]["shares"]
        out["rsv2_pass"] = bool(sh["repro_nonhashed_share"] >= RSV2_REPRO_BAR and sh["extra_nonhashed_share"] <= RSV2_EXTRA_BAR)
        out["rsv2p_pass"] = bool(out["rsv2_pass"] and ab_total["A"] == 0 and ab_total["D"] == 0)
    if d_scores:
        out["leg_D_vs_A"] = pool(d_scores)
    with open(pins_path, "a") as pf:
        end_sha = sha256(os.path.join(args.bin, native_name()))
        pf.write(json.dumps({"utc": now(), "event": "end", "native": end_sha}) + "\n")
        assert end_sha == got, "native library changed during the run"
    rs.dump_json(os.path.join(pass_dir, "aggregate.json"), out)
    print(json.dumps({k: v for k, v in out.items() if k in ("abandonments_first", "timing_seconds_per_block", "rsv2_pass", "rsv2p_pass")}, indent=1), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
