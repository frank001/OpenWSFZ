using OpenWSFZ.Abstractions;

namespace OpenWSFZ.Daemon;

/// <summary>
/// Compiled-in default callsign-region seed data (<c>callsign-regions.json</c>),
/// modelled on the ham-radio-community "country file" (<c>cty.dat</c>-style)
/// convention at continent+entity granularity (CQ/ITU zone columns left <c>null</c>
/// — not yet sourced; acceptable per the <c>region-lookup</c> capability's partial-
/// coverage non-goal). Used when <c>callsign-regions.json</c> is absent on first run.
///
/// <para>
/// This is public-domain ITU/DXCC prefix-block reference data (which administration
/// a prefix series belongs to), not real third-party callsigns — NFR-021 (no real
/// callsigns in committed files) does not apply to country/entity reference tables.
/// </para>
///
/// <para>
/// Coverage is intentionally partial (a representative sample of well-known prefix
/// blocks per continent); an unmatched prefix resolves to <c>"Unknown"</c>, which is
/// a correct, honest answer for an unlisted prefix, not a defect. The mandatory
/// synthetic <c>Q</c>-series entry (NFR-021) is always present.
/// </para>
/// </summary>
public static class CallsignRegionDefaults
{
    /// <summary>The default region seed list, including the mandatory synthetic <c>Q</c>-series entry.</summary>
    public static readonly IReadOnlyList<CallsignRegionEntry> Entries =
    [
        // ── North America ──────────────────────────────────────────────────
        new("K",   "K",   "United States", "NA", null, null),
        new("N",   "N",   "United States", "NA", null, null),
        new("W",   "W",   "United States", "NA", null, null),
        new("VE",  "VE",  "Canada",        "NA", null, null),
        new("XE",  "XE",  "Mexico",        "NA", null, null),

        // ── South America ──────────────────────────────────────────────────
        new("PY",  "PY",  "Brazil",        "SA", null, null),
        new("LU",  "LU",  "Argentina",     "SA", null, null),
        new("CE",  "CE",  "Chile",         "SA", null, null),

        // ── Europe ──────────────────────────────────────────────────────────
        new("G",   "G",   "England",       "EU", null, null),
        new("GM",  "GM",  "Scotland",      "EU", null, null),
        new("GW",  "GW",  "Wales",         "EU", null, null),
        new("EI",  "EI",  "Ireland",       "EU", null, null),
        new("F",   "F",   "France",        "EU", null, null),
        new("DL",  "DL",  "Germany",       "EU", null, null),
        new("I",   "I",   "Italy",         "EU", null, null),
        new("EA",  "EA",  "Spain",         "EU", null, null),
        new("CT",  "CT",  "Portugal",      "EU", null, null),
        new("PA",  "PA",  "Netherlands",   "EU", null, null),
        new("ON",  "ON",  "Belgium",       "EU", null, null),
        new("HB9", "HB9", "Switzerland",   "EU", null, null),
        new("OE",  "OE",  "Austria",       "EU", null, null),
        new("SM",  "SM",  "Sweden",        "EU", null, null),
        new("LA",  "LA",  "Norway",        "EU", null, null),
        new("OZ",  "OZ",  "Denmark",       "EU", null, null),
        new("OH",  "OH",  "Finland",       "EU", null, null),
        new("SP",  "SP",  "Poland",        "EU", null, null),
        new("3A",  "3A",  "Monaco",        "EU", null, null),
        new("9A",  "9A",  "Croatia",       "EU", null, null),

        // ── Asia ────────────────────────────────────────────────────────────
        new("JA",  "JA",  "Japan",         "AS", null, null),
        new("HL",  "HL",  "South Korea",   "AS", null, null),
        new("BY",  "BY",  "China",         "AS", null, null),
        new("VU",  "VU",  "India",         "AS", null, null),
        new("4X",  "4X",  "Israel",        "AS", null, null),
        new("UA",  "UA",  "Russia",        "AS", null, null),

        // ── Oceania ─────────────────────────────────────────────────────────
        new("VK",  "VK",  "Australia",     "OC", null, null),
        new("ZL",  "ZL",  "New Zealand",   "OC", null, null),

        // ── Africa ──────────────────────────────────────────────────────────
        new("ZS",  "ZS",  "South Africa",  "AF", null, null),

        // ── Synthetic (NFR-021, R&R Study) ─────────────────────────────────
        // Mandatory entry per design.md Decision 3: the Q-series is reserved for
        // Q-codes and never allocated as a real callsign prefix — this project's
        // own synthetic test-callsign convention uses it, and must resolve to a
        // region distinct from both a real entity and the generic "Unknown" miss.
        new("Q",   "Q",   "Synthetic (R&R Study)", null, null, null, Synthetic: true),
    ];
}
