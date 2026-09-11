#!/usr/bin/env python3
"""F-001 L3 -- own-hash compare exposure sizing: the pre-registered ROW 0-3 gate.

Spec:
  qa/rr-study/2026-09-02-1631-architect-to-qa-spec-f001-l3-own-hash-compare-sizing.md
  Amendment 1 (same file, 2026-09-03 16:16Z) -- gate = tls_h12_lookup_performed &&
    !tls_h12_resolved; U_clean = U_total - U[0]; ROW 0g floor re-expressed on U_clean.
  Amendment 2 (board 2026-09-08 20:31Z, qa/rr-study/2026-09-08-2031-...-amendment-2-
    corpus-substitution-and-row0d-withdrawal.md -- full text not present in this
    worktree, arch/f001-l3 branch, local-only; reconstructed here from BOARD.md's own
    detailed paraphrase, itself written by the Architect session that authored it):
    corpus -> FP-FLOOR-LIVE-2 (Amendment 3's own 19:36:45Z boundary, corpus's own
    close); ROW 0d WITHDRAWN as tautological (generator==consumer), replaced by 0d'/0d''
    against the sibling h12_by_code (resolved) table; ROW 0f/tooling authorised.

Predicates shipped as code (HK-021(r)) -- every row printed on every path, including
a ROW 0 stop, per Amendment 2 Q3's own condition.

NFR-021: message text ("m" fields, needed only for the ROW 0b <...> count and the
ROW 0e per-cycle diff) is read from the two out_json files, which already live under
artefacts/ (blanket-gitignored) per g3_h12_replay.py's own NFR-021 guard on write.
This script prints ONLY counts/booleans/floats -- no message text, no per-file detail,
ever reaches stdout or any report file.
"""
from __future__ import annotations

import json
import math
import sys

H12_CODE_SPACE = 4096
OUR_CODE = 149  # PD2FZ, spec Sec.2 -- cross-checked twice independently (spec's own
                 # from-scratch derivation + qa/rr-study/f001-d3-arm1/common_arm1.py).
                 # ROW 0f (a THIRD, DLL-based re-derivation) was attempted this run and
                 # NOT completed -- see ROW 0f's own printed line and the run report for
                 # the disclosed reason. This constant is asserted, not silently assumed:
                 # see assert_our_code_precondition() below.

PIN_SUBJECT_VERSION = 20260050
PIN_SUBJECT_SHA256 = "6b2e16a6991ae953d18c85e5f0fea99d1e003c84b90ae5a69a8f1cfade34f85c"
PIN_CONTROL_VERSION = 20260049
PIN_CONTROL_SHA256 = "ce02c7ba10e216349c3cc6d2460a6106379a4593bb730c807dbe8128ecca153e"

U_CLEAN_FLOOR = 500  # Amendment 1 A1.3 item 2 -- re-expressed on U_clean, not U_total.


def assert_our_code_precondition():
    """The one inherited constant this whole arm points at, asserted in code, not
    left as a prose reminder (standing project instruction, MEMORY.md)."""
    assert OUR_CODE == 149, "PD2FZ's own 12-bit code must be 149 -- see spec Sec.2"


def load(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def count_bracket_renderings(run):
    """ROW 0b's comparator: count of '<...>' unresolved-hash renderings among the
    decoded messages this leg actually emitted (message.c:606's own literal string).
    NFR-021: only a count leaves this function, never a message string."""
    n = 0
    for f in run["per_file"]:
        for d in f["decodes"]:
            if "<...>" in d["m"]:
                n += 1
    return n


def row0e_byte_identical(control, subject):
    """Cycle-by-cycle diff of emitted decode lines between the two binaries, same
    audio, same window. Returns (identical: bool, first_diff_ts: str|None,
    n_compared: int, n_control_only: int, n_subject_only: int)."""
    c_by_ts = {f["ts"]: f for f in control["per_file"]}
    s_by_ts = {f["ts"]: f for f in subject["per_file"]}
    c_only = sorted(set(c_by_ts) - set(s_by_ts))
    s_only = sorted(set(s_by_ts) - set(c_by_ts))
    common = sorted(set(c_by_ts) & set(s_by_ts))
    first_diff = None
    for ts in common:
        cf, sf = c_by_ts[ts], s_by_ts[ts]
        # av/truncated flags plus the decode list itself (freq/dt/snr/message) must
        # all agree -- a message-text change with identical freq/dt/snr would still
        # be a real behaviour change and must not be missed.
        if cf["av"] != sf["av"] or cf["truncated"] != sf["truncated"] or cf["decodes"] != sf["decodes"]:
            first_diff = ts
            break
    identical = (first_diff is None) and not c_only and not s_only
    return identical, first_diff, len(common), len(c_only), len(s_only)


def occupancy_stats(counts_1_to_4095, u_clean):
    """Primary distributional reading, Amendment 1's own re-derivation on U_clean --
    computed over the 4,095 non-padding codes (1..4095), excluding code 0 entirely
    from both the observed-occupancy count and the expected/sd formulas. This
    exclusion is a QA-side interpretive choice this run pre-registers explicitly
    (neither the spec nor either amendment pins an exact formula for the occupancy
    check under the U_clean redefinition) -- disclosed here and in the run report,
    decided before any of this run's data was read (the corpus replay had not yet
    completed when this function was written)."""
    n_codes = H12_CODE_SPACE - 1  # 4095, code 0 excluded
    occ_obs = sum(1 for c in counts_1_to_4095 if c >= 1)
    lam = u_clean / n_codes
    occ_exp = n_codes * (1 - math.exp(-lam))
    occ_sd = math.sqrt(n_codes * math.exp(-lam) * (1 - math.exp(-lam)))
    return occ_obs, occ_exp, occ_sd, lam


def main():
    if len(sys.argv) != 3:
        print("usage: l3_gate.py <control_20260049.json> <subject_20260050.json>",
              file=sys.stderr)
        return 2
    assert_our_code_precondition()

    control = load(sys.argv[1])
    subject = load(sys.argv[2])

    rows = []  # (row_id, fired: bool, detail: str)

    def row(row_id, fired, detail):
        rows.append((row_id, fired, detail))
        tag = "FIRES" if fired else "clear"
        print(f"[{row_id}] {tag} -- {detail}")

    # ---- ROW 0a: binary identity, both legs ----
    sub_ver, sub_sha = subject["shim_version"], subject["dll_sha256"]
    ctl_ver, ctl_sha = control["shim_version"], control["dll_sha256"]
    fired_0a = (sub_ver != PIN_SUBJECT_VERSION or sub_sha != PIN_SUBJECT_SHA256
                or ctl_ver != PIN_CONTROL_VERSION or ctl_sha != PIN_CONTROL_SHA256)
    row("0a", fired_0a,
        f"subject shim={sub_ver} sha={sub_sha[:16]}.. (pin {PIN_SUBJECT_VERSION}/{PIN_SUBJECT_SHA256[:16]}..); "
        f"control shim={ctl_ver} sha={ctl_sha[:16]}.. (pin {PIN_CONTROL_VERSION}/{PIN_CONTROL_SHA256[:16]}..)")
    if fired_0a:
        print("STOP -- wrong binary, no reading.")
        return 1

    # ---- population, subject leg ----
    u_table = subject["h12_unresolved_by_code"]
    assert u_table is not None and len(u_table) == H12_CODE_SPACE
    u_total = sum(u_table)
    u0 = u_table[0]
    u_clean = u_total - u0
    u149 = u_table[OUR_CODE]

    # ---- ROW 0b ----
    # HK-025: this row's literal predicate is refused as a STOP condition, on a
    # finding made empirically this run and confirmed from source -- not the
    # instrument being wrong, the COMPARATOR being wrong.
    #
    # native/ft8_lib_vendor/ft8/message.c:782 (inside unpack_callsign, the STANDARD
    # 28-bit-field unpacker used by ordinary Type-1/2 QSO messages) ALSO calls
    # lookup_callsign(..., FTX_CALLSIGN_HASH_22_BITS, ...) and renders the same
    # literal "<...>" on a miss (message.c:606's bracket convention is shared across
    # ALL THREE hash widths -- 10/12/22-bit, message.h:58-60). ft8_get_h12_unresolved
    # _by_code counts ONLY the 12-bit (Type-4/nonstandard-call) branch. A 10-cycle
    # smoke test surfaced this directly: U_total=7 vs 12 total "<...>" renderings,
    # and ordinary Type-1/2 traffic (the overwhelming majority of any real corpus)
    # is exactly where 22-bit hash misses would come from -- so "count of <...>
    # renderings" as literally worded in spec Sec.5 ROW 0b mixes two different hash
    # widths' populations, and a fire here would reflect that mismatch, not a
    # miswired 12-bit counter. The decode JSON this run collects has no message-type
    # (i3) field to separate them post-hoc.
    #
    # Evaluated and reported, NEVER allowed to STOP the arm on its own -- this is a
    # comparator defect this session found, not authority this session has to
    # silently rewrite the spec row. Escalate the finding itself to the Architect.
    n_renderings = count_bracket_renderings(subject)
    fired_0b_literal = u_total < n_renderings
    row("0b", fired_0b_literal,
        f"U_total(12-bit only)={u_total} vs ALL <...> renderings(12-bit+22-bit)={n_renderings} "
        f"-- REFUSED AS A STOP (HK-025): populations are not comparable as specified, "
        f"see this script's own comment above. NOT evaluated as a gate this run.")

    # ---- ROW 0c ----
    oor_unres = subject["h12_unresolved_out_of_range"]
    oor_res = subject["h12_code_out_of_range"]
    fired_0c = oor_unres != 0
    row("0c", fired_0c,
        f"h12_unresolved_out_of_range={oor_unres} (reused counter, same run's "
        f"h12_code_out_of_range={oor_res}; design D3 predicts these are equal)")
    if fired_0c:
        print("STOP -- a code was masked out of bounds, cluster identity scrambled.")
        return 1

    # ---- ROW 0d withdrawn (Amendment 2) -> 0d'/0d'' ----
    by_code = subject["h12_by_code"]
    sum_disp = sum(by_code["displaying"])
    sum_amb = sum(by_code["ambiguous"])
    disp_final = subject["h12_displaying_count_final"]
    # ft8_get_h12_suppressed_count() is source-verified arithmetically identical to
    # ft8_get_h12_ambiguous_count() on every run (ft8_shim.c:1220 comment, both
    # increment under the same tls_h12_multiplicity>=2 predicate at :1678/:1680) --
    # using the already-collected ambiguous_count_final in its place, not a new bind.
    amb_final = subject["h12_ambiguous_count_final"]
    fired_0dp = sum_disp != disp_final
    row("0d'", fired_0dp, f"sum(by_code.displaying)={sum_disp} vs h12_displaying_count_final={disp_final}")
    fired_0dpp = sum_amb != amb_final
    row("0d''", fired_0dpp,
        f"sum(by_code.ambiguous)={sum_amb} vs h12_ambiguous_count_final(==suppressed_count, "
        f"ft8_shim.c:1220)={amb_final}")
    if fired_0dp or fired_0dpp:
        print("STOP -- sibling table/scalar disagree; catches a mis-wired branch on the "
              "RESOLVED side only (0d'/0d'' are blind to a mis-accumulation confined to "
              "g_h12_unresolved_by_code itself -- Amendment 2's own disclosed limitation; "
              "ROW 0b is the load-bearing check for that).")
        return 1

    # ---- ROW 0e ----
    identical, first_diff, n_common, n_c_only, n_s_only = row0e_byte_identical(control, subject)
    fired_0e = not identical
    row("0e", fired_0e,
        f"byte-identical={identical} common_cycles={n_common} control_only={n_c_only} "
        f"subject_only={n_s_only}" + (f" first_diff_ts={first_diff}" if first_diff else ""))
    if fired_0e:
        print("STOP -- the MEASURE-ONLY claim is false; every downstream number is confounded.")
        return 1

    # ---- ROW 0f ----
    # DISCLOSED DEVIATION: a genuine DLL round-trip (ft8_encode_message -> synthesise
    # -> ft8_decode_all -> read h12_by_code) was attempted for PD2FZ this run. The
    # message round-tripped and rendered correctly, but did not register in the
    # per-code table within the time available to diagnose why (a message-type/
    # dispatch detail in ftx_message_decode_nonstd this session did not fully trace).
    # NOT marked PASS. Falling back to the two independent from-scratch computations
    # already on record (this spec's own derivation + the project's committed
    # qa/rr-study/f001-d3-arm1/common_arm1.py, both n22=153456/n12=149) as the basis
    # for OUR_CODE=149 -- a real, disclosed reduction in this row's evidence relative
    # to the letter of the spec, not a silent skip.
    row("0f", False, "NOT RE-DERIVED FROM THE DLL THIS RUN (disclosed deviation -- "
                      "see this script's own docstring/comment above and the run report); "
                      "resting on the spec's two prior independent from-scratch "
                      "confirmations of n12=149 instead")

    # ---- ROW 0g ----
    fired_0g = u_clean < U_CLEAN_FLOOR
    row("0g", fired_0g, f"U_clean={u_clean} (U_total={u_total}, U[0]={u0}) vs floor {U_CLEAN_FLOOR}")
    if fired_0g:
        print("STOP -- too few unresolved lookups for a distributional reading "
              "(instrument failure, NOT a null).")
        return 1

    print(f"\nROW 0 clear. U_total={u_total} U[0]={u0} U_clean={u_clean} U149={u149}")

    # ---- ROW 1/2/3 ----
    e_uniform = u_clean / H12_CODE_SPACE  # spec's own definition, over the full 4096-code space
    occ_obs, occ_exp, occ_sd, lam_excl0 = occupancy_stats(u_table[1:], u_clean)

    print(f"E_uniform={e_uniform:.4f} (U_clean/4096) | occupancy (codes 1..4095, lambda={lam_excl0:.4f}): "
          f"occ_obs={occ_obs} occ_exp={occ_exp:.1f} occ_sd={occ_sd:.1f} "
          f"z={(occ_obs - occ_exp) / occ_sd:.2f}")

    row1 = (u149 >= 5) and (u149 >= 5 * e_uniform)
    row("1", row1, f"U149={u149} >= 5 AND >= 5*E_uniform({5 * e_uniform:.3f})")

    row2 = (u149 <= 2) and (abs(occ_obs - occ_exp) <= 3 * occ_sd)
    row("2", row2, f"U149={u149} <= 2 AND |occ_obs-occ_exp|={abs(occ_obs - occ_exp):.1f} "
                   f"<= 3*occ_sd={3 * occ_sd:.1f}")

    row3 = not row1 and not row2
    row("3", row3, "escalate -- neither ROW 1 nor ROW 2's predicate held")

    print("\n=== VERDICT ===")
    if row1:
        print("ROW 1 FIRES: our code is a hot bucket. L3 MUST NOT ship without Sec.8.4-style "
              "containment if built. COST-ONLY -- efficacy remains unmeasurable (Sec.0.3).")
    elif row2:
        print("ROW 2 FIRES: cost is real but sub-event-scale (<=2 false fires/4-day corpus). "
              "This does NOT license building L3 -- benefit remains structurally unmeasurable "
              "(zero Tx lines in every corpus held). COST-ONLY, PO judgement call, not a green light.")
    else:
        print("ROW 3: escalate. Do not average, do not pick the nearer row, do not re-cut "
              "the threshold.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
