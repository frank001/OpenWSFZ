"""Same-chain Amendment 2: convert Replay81's --nc-dump working file (stamp, kind, matched, freq, dt, snr, same_any, min_df, wcount, path, text) into the
`index<TAB>batch<TAB>snr<TAB>dt<TAB>freq_hz<TAB>text` file that same_chain_compare.py reads. The index comes from the wavlist (index<TAB>path<TAB>stamp).
Tooling only; message text stays in the scratch files (HK-037) and is never printed.

    python same_chain_nc_to_tsv.py --nc-dump <nc_dump.tsv> --wavlist <offline_wavs.tsv> --out <ref.decodes.tsv>
"""
import argparse
from pathlib import Path


def convert(nc_dump: Path, wavlist: Path, out: Path) -> int:
    idx = {}
    for ln in wavlist.read_text(encoding="utf-8").splitlines():
        i, _p, st = ln.split("\t")
        idx[st] = int(i)
    rows = ["index\tbatch\tsnr\tdt\tfreq_hz\ttext"]
    n = 0
    for ln in nc_dump.read_text(encoding="utf-8").splitlines():
        f = ln.split("\t")
        stamp, kind, freq, dt, snr, text = f[0], f[1], f[3], f[4], f[5], f[10]
        rows.append("\t".join((str(idx[stamp]), kind, snr, dt, freq, text)))
        n += 1
    out.write_text("\n".join(rows) + "\n", encoding="utf-8", newline="\n")
    return n


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--nc-dump", required=True)
    ap.add_argument("--wavlist", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    print("rows", convert(Path(a.nc_dump), Path(a.wavlist), Path(a.out)))


if __name__ == "__main__":
    main()
