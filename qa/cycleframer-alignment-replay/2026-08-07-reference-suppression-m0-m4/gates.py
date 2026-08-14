"""Pre-registered gates for the reference-suppression investigation (M1-M4).

Every function here is copied VERBATIM (only renamed for import hygiene) from the code
blocks in `2026-08-06-2144-architect-to-qa-spec-reference-suppression-m0-m4.md`. Per
HK-021 a pre-registered check must be mechanical -- these are kept in one small,
dependency-free module specifically so a diff against the spec's own code blocks is trivial
and nobody has to trust a paraphrase. Do not "simplify" these against the spec without
re-quoting the spec section.

No I/O, no printing, no NFR-021-sensitive data ever touches this module -- every argument is
a scalar (float/bool/int).
"""
from __future__ import annotations


# ---------------------------------------------------------------------------
# M1 -- SS3.3. Rows mutually exclusive by construction (see spec's own note).
# ---------------------------------------------------------------------------
def m1_row(delta_db: float, p: float) -> str:
    if delta_db <= -2.0 and p < 0.001:
        return "ROW 1"
    if abs(delta_db) < 1.0 and p >= 0.001:
        return "ROW 2"
    if delta_db >= 2.0 and p < 0.001:
        return "ROW 3"
    return "ROW 4"


M1_CONSEQUENCE = {
    "ROW 1": "TRUNCATION SUPPORTED. M4 is authorised to proceed (subject to Captain sign-off).",
    "ROW 2": "TRUNCATION NOT SUPPORTED; log-incompleteness becomes the lead hypothesis. "
             "M4 MUST NOT RUN. Escalate to Architect.",
    "ROW 3": "ANOMALY -- tonight-only decodes are stronger, fits neither hypothesis. "
             "HALT M1-M4. Escalate immediately.",
    "ROW 4": "INCONCLUSIVE. M4 MUST NOT RUN. Report delta, p, both medians, both n, escalate.",
}


# ---------------------------------------------------------------------------
# M2 -- SS4.3 validity gate, then SS4.4 pre-registered gate.
# ---------------------------------------------------------------------------
def m2_validity(r_wsjtx_self: float) -> str | None:
    """Returns 'VOID' if the replay cannot be trusted for set-membership claims, else None."""
    if r_wsjtx_self < 0.80:
        return "VOID"
    return None


def m2_row(r: float) -> str:
    if r >= 0.90:
        return "ROW 1"
    if r >= 0.50:
        return "ROW 2"
    return "ROW 3"


M2_CONSEQUENCE = {
    "ROW 1": "CONFIRMED -- 'OpenWSFZ finds decodes WSJT-X cannot' is false on this window; "
             "that population is a reference-suppression artifact. Arm R.D's reciprocity "
             "premise is undermined on this window; R.D remains unauthorised pending M3.",
    "ROW 2": "PARTIAL -- majority artifact, residual genuinely-exclusive population = "
             "(1 - R_owsfz) x 279. Report the residual count. No verdict on its cause.",
    "ROW 3": "NOT SUPPORTED -- SS3's aggregate-rate reading is masking set churn. SS3's "
             "'absorption' reading must be withdrawn and the Architect notified.",
}


# ---------------------------------------------------------------------------
# M3 -- SS5.2 step 5 pre-flight, SS5.3 validity gate, SS5.4 pre-registered gate.
# ---------------------------------------------------------------------------
def m3_density_leverage_ok(contrast: float) -> bool:
    """SS5.2 step 5: if contrast < 3.0, do not run M3 at all."""
    return contrast >= 3.0


def m3_validity(counts: list[float]) -> str | None:
    """SS5.3: returns 'INSTRUMENT NOISE HIGH' if the 3 runs' WSJT-X counts span more than
    10% of their mean, else None. `counts` = [run1_wsjtx, run2_wsjtx, run3_wsjtx]."""
    if (max(counts) - min(counts)) > 0.10 * (sum(counts) / 3):
        return "INSTRUMENT NOISE HIGH"
    return None


def m3_row(s_low: float) -> str:
    if s_low < 1.00:
        return "ROW 4"
    if s_low < 1.25:
        return "ROW 3"
    if s_low < 2.00:
        return "ROW 2"
    return "ROW 1"


M3_CONSEQUENCE = {
    "ROW 1": "SUPPRESSION GENERALISES, not density-dependent. The corpus's live WSJT-X "
             "ALL.TXT is unsafe as a reference corpus-wide. Arm R.D stays unauthorised.",
    "ROW 2": "SUPPRESSION PRESENT BUT DENSITY-DEPENDENT -- consistent with a load/deadline "
             "mechanism. The density penalty specifically is confounded and must be "
             "re-derived before it is cited again.",
    "ROW 3": "WINDOW/DENSITY-SPECIFIC -- the busy-window result does not generalise. "
             "Corpus-wide scouting figures survive at low density but not at high.",
    "ROW 4": "ANOMALY -- replay yields fewer decodes than the original at low density. "
             "HALT. The replay instrument itself is suspect. Escalate.",
}


# ---------------------------------------------------------------------------
# M4 -- SS6.2. GATED: only ever evaluated if M1 fired ROW 1.
# ---------------------------------------------------------------------------
def m4_row(w1: float, w2: float, w3: float) -> str:
    monotone = w1 >= w2 >= w3
    if w3 <= 400 and monotone:
        return "ROW 1"
    if w3 <= 400:
        return "ROW 2"
    if w3 <= 600:
        return "ROW 3"
    return "ROW 4"


M4_CONSEQUENCE = {
    "ROW 1": "MECHANISM DEMONSTRATED -- CPU contention is sufficient to reproduce the "
             "original suppression, with a clean dose-response.",
    "ROW 2": "SUPPRESSION REPRODUCED, DOSE-RESPONSE UNCLEAN -- sufficient, mechanism not "
             "cleanly characterised. Report all three counts.",
    "ROW 3": "PARTIAL -- load suppresses yield but cannot reach the original 328. "
             "Contention alone is not sufficient; a second factor is required. Escalate.",
    "ROW 4": "NOT SUPPORTED -- 2x oversubscription does not materially suppress WSJT-X "
             "yield. The original suppression has another cause entirely. Escalate.",
}
