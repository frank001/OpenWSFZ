// FP-vs-engagement-validator survival diagnostic (2026-07-18).
//
// Question: of the false-positive callsign tokens the OSD decode path has actually
// manufactured from noise in prior R&R-study S5 runs, what fraction would now be
// stopped by IEngagementTargetValidator (engagement-target-validation, PR #81) before
// reaching a TX-engagement decision (manual engage / auto-answer arming / responder
// matching)? This reuses the real production EngagementTargetValidator, CallsignRegionStore,
// and CallsignGrammarStore classes verbatim (see .csproj ProjectReferences) against the
// real, live, operator-refreshed 29,013-entry callsign-regions.json — no reimplementation
// of the grammar-check algorithm.
//
// See report.md in this directory for the full write-up.

using OpenWSFZ.Abstractions;
using OpenWSFZ.Daemon;

var here = AppContext.BaseDirectory;

// Live, real (non-seed) data — the operator's actual %APPDATA%\OpenWSFZ store, refreshed
// from country-files.com per F-006. Read-only: LoadAsync only ever *writes* when the file
// is absent, and both files already exist, so this run cannot modify the operator's live data.
var appData        = Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData);
var regionPath     = Path.Combine(appData, "OpenWSFZ", "callsign-regions.json");
var grammarPath    = Path.Combine(appData, "OpenWSFZ", "callsign-grammar.json");

if (!File.Exists(regionPath))
{
    Console.Error.WriteLine($"FATAL: live region file not found at '{regionPath}'.");
    return 1;
}

var regionStore  = new CallsignRegionStore(regionPath);
var grammarStore = new CallsignGrammarStore(grammarPath);
await regionStore.LoadAsync();
await grammarStore.LoadAsync();

Console.WriteLine($"Region store: {regionStore.Entries.Count} entries, IsSeedData={regionStore.IsSeedData}");
Console.WriteLine($"Grammar: DigitRunMax={grammarStore.Current.DigitRunMax}, " +
                   $"SuffixLengthMax={grammarStore.Current.SuffixLengthMax}, " +
                   $"TotalLengthMax={grammarStore.Current.TotalLengthMax}");

if (regionStore.IsSeedData)
{
    Console.Error.WriteLine("FATAL: region store reports IsSeedData=true — the gate would be " +
                             "inactive (everything Allowed) and this diagnostic would be meaningless. " +
                             "Expected the live, refreshed 29,013-entry table.");
    return 1;
}

var validator = new EngagementTargetValidator(regionStore, grammarStore);

// ── FP token corpus ──────────────────────────────────────────────────────────────
// Extracted by inspection from the committed S5 "false_positive=True" rows of three prior
// R&R-study runs (S5_matched.csv in each results/ directory) — every candidate callsign-shaped
// token from every OSD-manufactured noise-floor false positive on record in this repo.
// Excludes: report/control tokens (R, RR73, RRR, 73, signal reports), grid-square tokens
// (Maidenhead 4-char), and the "<...>" unresolved-hash placeholder (not a callsign token —
// nothing for the validator to evaluate).
var samples = new[]
{
    // ── Source A: 2026-06-20-8eea3c4 — D-009 trigger run, PRE-gating baseline
    //   (shim 20260025, K_MIN_SCORE_PASS2=1, no corr/nhard gates). 9 FP messages, 18 tokens.
    new Sample("A-pregating", "X20KEB ZQ8LRC DE15",        "X20KEB"),
    new Sample("A-pregating", "X20KEB ZQ8LRC DE15",        "ZQ8LRC"),
    new Sample("A-pregating", "HR4VDR A27DFI NG38",        "HR4VDR"),
    new Sample("A-pregating", "HR4VDR A27DFI NG38",        "A27DFI"),
    new Sample("A-pregating", "KR9NHK/P MR1I O/P QG94",    "KR9NHK/P"),
    new Sample("A-pregating", "KR9NHK/P MR1I O/P QG94",    "MR1I"),
    new Sample("A-pregating", "0N4KV 7F4VSB JK98",         "0N4KV"),
    new Sample("A-pregating", "0N4KV 7F4VSB JK98",         "7F4VSB"),
    new Sample("A-pregating", "JT6KU EH2AOE/R R OH76",     "JT6KU"),
    new Sample("A-pregating", "JT6KU EH2AOE/R R OH76",     "EH2AOE/R"),
    new Sample("A-pregating", "8H2LOJ JL0NTD/R JI99",      "8H2LOJ"),
    new Sample("A-pregating", "8H2LOJ JL0NTD/R JI99",      "JL0NTD/R"),
    new Sample("A-pregating", "WH8EYF/P LC8WMR R EQ48",    "WH8EYF/P"),
    new Sample("A-pregating", "WH8EYF/P LC8WMR R EQ48",    "LC8WMR"),
    new Sample("A-pregating", "K60IFO/R 9O5GEL/R R CH00",  "K60IFO/R"),
    new Sample("A-pregating", "K60IFO/R 9O5GEL/R R CH00",  "9O5GEL/R"),
    new Sample("A-pregating", "H34INX SZ9DTT/P LB12",      "H34INX"),
    new Sample("A-pregating", "H34INX SZ9DTT/P LB12",      "SZ9DTT/P"),
    new Sample("A-pregating", "IU7WEX/P 6N8XOX R EO10",    "IU7WEX/P"),
    new Sample("A-pregating", "IU7WEX/P 6N8XOX R EO10",    "6N8XOX"),

    // ── Source B: 2026-07-04-a3738fc-f002-s5-n300 — CURRENT shipped config
    //   (K_MIN_SCORE_PASS2=10, gates ON), N=300 slots, confirmatory FP-rate run. 8 FP
    //   messages, 12 evaluable tokens (4 rows lead with the "<...>" unresolved-hash
    //   placeholder, contributing only 1 token each).
    new Sample("B-shipped-n300", "<...> KOWQ8MGEQVT RR73",   "KOWQ8MGEQVT"),
    new Sample("B-shipped-n300", "VN6NY/R K69IGM/R CA05",    "VN6NY/R"),
    new Sample("B-shipped-n300", "VN6NY/R K69IGM/R CA05",    "K69IGM/R"),
    new Sample("B-shipped-n300", "<...> 3W3ZAJ/R RM02",      "3W3ZAJ/R"),
    new Sample("B-shipped-n300", "<...> HL5QRM/R ML60",      "HL5QRM/R"),
    new Sample("B-shipped-n300", "HA3YSR 1D2QID/R EB40",     "HA3YSR"),
    new Sample("B-shipped-n300", "HA3YSR 1D2QID/R EB40",     "1D2QID/R"),
    new Sample("B-shipped-n300", "C4QM 2F1SJJ/R HK20",       "C4QM"),
    new Sample("B-shipped-n300", "C4QM 2F1SJJ/R HK20",       "2F1SJJ/R"),
    new Sample("B-shipped-n300", "N0LMJ/R WO9TMN GK96",      "N0LMJ/R"),
    new Sample("B-shipped-n300", "N0LMJ/R WO9TMN GK96",      "WO9TMN"),
    new Sample("B-shipped-n300", "<...> RHLI8VWMXMG RRR",    "RHLI8VWMXMG"),

    // ── Source C: d011-fp-recheck-2026-07-04 — CURRENT shipped config, N=120,
    //   D-011 AC-4 re-check run. 7 FP messages, 11 tokens. Row 5 is the one and only
    //   literal "CQ <callsign>" FP on record — the exact shape the auto-answer-arming
    //   path (QsoAnswererService.TryParseCq) gates, not just the manual-engage path.
    new Sample("C-shipped-n120", "GI1HYT/P IU7FFH AO93",     "GI1HYT/P"),
    new Sample("C-shipped-n120", "GI1HYT/P IU7FFH AO93",     "IU7FFH"),
    new Sample("C-shipped-n120", "XT6VA CU4VET CG52",        "XT6VA"),
    new Sample("C-shipped-n120", "XT6VA CU4VET CG52",        "CU4VET"),
    new Sample("C-shipped-n120", "6Q3FWF/R 3Q4WUB RM21",     "6Q3FWF/R"),
    new Sample("C-shipped-n120", "6Q3FWF/R 3Q4WUB RM21",     "3Q4WUB"),
    new Sample("C-shipped-n120", "<...> WA7CTO RA99",        "WA7CTO"),
    new Sample("C-shipped-n120", "CQ NZP10KAK/9J",           "NZP10KAK/9J"),
    new Sample("C-shipped-n120", "ZY2HCA 16TDH/P QD32",      "ZY2HCA"),
    new Sample("C-shipped-n120", "ZY2HCA 16TDH/P QD32",      "16TDH/P"),
    new Sample("C-shipped-n120", "<...> LV3MFZ KK73",        "LV3MFZ"),
};

Console.WriteLine();
Console.WriteLine($"{"Source",-16} {"Token",-16} {"Verdict",-10} Reason / matched message");
Console.WriteLine(new string('-', 100));

var results = new List<(Sample sample, EngagementValidationResult result)>();
foreach (var s in samples)
{
    var result = validator.Validate(s.Token);
    results.Add((s, result));
    var verdict = result.IsAllowed ? "ALLOWED" : "REJECTED";
    Console.WriteLine($"{s.Source,-16} {s.Token,-16} {verdict,-10} " +
                       $"{(result.IsAllowed ? s.Message : result.RejectionReason)}");
}

Console.WriteLine();
foreach (var group in results.GroupBy(r => r.sample.Source))
{
    var total    = group.Count();
    var allowed  = group.Count(r => r.result.IsAllowed);
    var rejected = total - allowed;
    Console.WriteLine($"{group.Key,-16} total={total,3}  allowed(survives)={allowed,3}  " +
                       $"rejected(caught)={rejected,3}  survival={100.0 * allowed / total,6:F1}%");
}

var overallTotal    = results.Count;
var overallAllowed  = results.Count(r => r.result.IsAllowed);
Console.WriteLine();
Console.WriteLine($"OVERALL total={overallTotal}  allowed(survives)={overallAllowed}  " +
                   $"rejected(caught)={overallTotal - overallAllowed}  " +
                   $"survival={100.0 * overallAllowed / overallTotal:F1}%");

return 0;

// ── Types ─────────────────────────────────────────────────────────────────────────
sealed record Sample(string Source, string Message, string Token);
