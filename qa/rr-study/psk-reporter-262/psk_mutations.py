#!/usr/bin/env python3
"""#262 review (HK-039): QA's mutation checks on the Developer's feat/psk-reporter-262. Each mutation edits ONE source file in a scratch checkout,
runs the PSK Reporter tests (plus QA's differential encoder test when the checkout holds it), records which tests fail, and restores the file.
A mutation that leaves every test green is a SURVIVOR: a requirement the tests do not guard.

  python psk_mutations.py <scratch tree> <out json> [only-ids]
"""
import json, re, subprocess, sys

D = "src/OpenWSFZ.Daemon/PskReporter/"
DAEMON = ("tests/OpenWSFZ.Daemon.Tests", "FullyQualifiedName~PskReporter|FullyQualifiedName~QaEncoderDifferential")
CONFIG = ("tests/OpenWSFZ.Config.Tests", "FullyQualifiedName~PskReporter")
WEB = ("tests/OpenWSFZ.Web.Tests", "FullyQualifiedName~PskReporter|FullyQualifiedName~ConfigSaveOverlay")

M = [
 # id, file, old, new, test sets, what it breaks
 ("Q01 8-field descriptor: locator and flowStart swapped", D + "PskReporterEncoder.cs",
  "PskField.Mode, PskField.Source, PskField.Locator, PskField.FlowStart]);", "PskField.Mode, PskField.Source, PskField.FlowStart, PskField.Locator]);", [DAEMON]),
 ("Q02 block order: 7-field block before the 8-field block", D + "PskReporterEncoder.cs",
  "(WithLocator, spots.Where(s => !string.IsNullOrEmpty(s.Locator)).ToList()),\n            (NoLocator,   spots.Where(s => string.IsNullOrEmpty(s.Locator)).ToList()),",
  "(NoLocator,   spots.Where(s => string.IsNullOrEmpty(s.Locator)).ToList()),\n            (WithLocator, spots.Where(s => !string.IsNullOrEmpty(s.Locator)).ToList()),", [DAEMON]),
 ("Q03 SNR not clamped (wraps)", D + "PskReporterEncoder.cs",
  "unchecked((byte)(sbyte)Math.Clamp(s.Snr, sbyte.MinValue, sbyte.MaxValue))", "unchecked((byte)s.Snr)", [DAEMON]),
 ("Q04 iMD sent as 1", D + "PskReporterEncoder.cs", "private const sbyte ImdNotMeasured = 0;", "private const sbyte ImdNotMeasured = 1;", [DAEMON]),
 ("Q05 informationSource 2", D + "PskReporterEncoder.cs", "private const byte AutomaticSource = 1;", "private const byte AutomaticSource = 2;", [DAEMON]),
 ("Q06 sequence counts datagrams, not records", D + "PskReporterEngine.cs", "_sequence += (uint)datagram.Spots.Count;", "_sequence += 1;", [DAEMON]),
 ("Q07 sequence advances on an unsent datagram", D + "PskReporterEngine.cs", "_pending.InsertRange(0, datagram.Spots);", "_pending.InsertRange(0, datagram.Spots); _sequence += (uint)datagram.Spots.Count;", [DAEMON]),
 ("Q08 5-minute per-call minimum removed", D + "PskReporterEngine.cs", "(_lastAnyBand.TryGetValue(call, out var any) && nowUtc - any < PerCallInterval)", "false", [DAEMON]),
 ("Q09 60-minute per-(call,band) rule removed", D + "PskReporterEngine.cs", "|| (_lastCallBand.TryGetValue((call, band), out var cb) && nowUtc - cb < PerCallBandInterval)", "", [DAEMON]),
 ("Q10 templates only in the first datagram", D + "PskReporterEngine.cs", "InitialTemplateDatagrams = 3;", "InitialTemplateDatagrams = 1;", [DAEMON]),
 ("Q11 templates never repeated hourly", D + "PskReporterEngine.cs", "|| nowUtc - _lastTemplatesUtc >= TemplateInterval;", ";", [DAEMON]),
 ("Q12 identity guard: Q-prefix call allowed", D + "PskReporterEngine.cs", "|| Callsign.TrimStart().StartsWith('Q') || Callsign.TrimStart().StartsWith('q')", "", [DAEMON]),
 ("Q13 identity guard: empty locator allowed", D + "PskReporterEngine.cs", "           || string.IsNullOrWhiteSpace(Locator);", "           ;", [DAEMON]),
 ("Q14 unknown-region decodes are reported", D + "PskReporterEngine.cs", "if (r.Region is null || r.Region.Synthetic)", "if (r.Region is { Synthetic: true })", [DAEMON]),
 ("Q15 synthetic decodes are reported", D + "PskReporterEngine.cs", "if (r.Region is null || r.Region.Synthetic)", "if (r.Region is null)", [DAEMON]),
 ("Q16 a batch with no dial frequency is reported on 14.074", D + "PskReporterEngine.cs", "if (batch.DialFrequencyMHz is not { } dialMHz || dialMHz <= 0)", "double dialMHz = batch.DialFrequencyMHz ?? 14.074; if (dialMHz <= 0)", [DAEMON]),
 ("Q17 RR73 accepted as a grid", D + "PskSenderExtractor.cs", "GridRegex.IsMatch(token) && !token.Equals(\"RR73\", StringComparison.OrdinalIgnoreCase)", "GridRegex.IsMatch(token)", [DAEMON]),
 ("Q18 resolved hashed calls are reported", D + "PskSenderExtractor.cs", "private static bool IsHash(string token) => token.StartsWith('<') || token.EndsWith('>');", "private static bool IsHash(string token) => token.Contains(\"...\");", [DAEMON]),
 ("Q19 own call compared on the full string", D + "PskSenderExtractor.cs", "BaseCall(found.Callsign).Equals(BaseCall(ownCallsign)", "found.Callsign.Equals(ownCallsign", [DAEMON]),
 ("Q20 CQ modifier slot removed (DX read as the call)", D + "PskSenderExtractor.cs", "if (i < t.Length && ModifierRegex.IsMatch(t[i]) && !IsCallsign(t[i])) i++;", "", [DAEMON]),
 ("Q21 service builds the socket even when disabled", D + "PskReporterService.cs", "if (!cfg.Enabled)\n            {", "if (!cfg.Enabled && cfg.Port < 0)\n            {", [DAEMON]),
 ("Q22 disabled batches are processed instead of discarded", D + "PskReporterService.cs", "if (!IsActive) continue;", "", [DAEMON]),
 ("Q23 pump never gives the batch a dial frequency", "src/OpenWSFZ.Daemon/DecodePump.cs", "DialFrequencyMHz: KnownDial(dialFreq))", "DialFrequencyMHz: null)", [DAEMON]),
 ("Q24 pump feeds only batch 1 to the upload", "src/OpenWSFZ.Daemon/DecodePump.cs", "@@2:_d.PskReporterChannel?.TryWrite(batch);", "", [DAEMON]),
 ("Q25 config default: enabled TRUE", "src/OpenWSFZ.Abstractions/PskReporterConfig.cs", "bool   enabled            = false,", "bool   enabled            = true,", [CONFIG, WEB]),
 ("Q26 pskReporter missing from the overlay section list", "src/OpenWSFZ.Web/ConfigOverlay.cs", "        \"pskReporter\",\n", "", [WEB]),
 ("Q27 overlay fallback: a fresh default replaces the stored block", "src/OpenWSFZ.Web/ConfigOverlay.cs", "PskReporter            = config.PskReporter            ?? current.PskReporter            ?? new PskReporterConfig(),", "PskReporter            = config.PskReporter ?? new PskReporterConfig(),", [WEB]),
 ("Q28 a callsign leaks into the log line", D + "PskReporterEngine.cs", "_exRegion = _exHashed = _exUnparseable = _exOwn = _exNoDial = _exDedup = _exDropped = 0;\n                return;",
  "_exRegion = _exHashed = _exUnparseable = _exOwn = _exNoDial = _exDedup = _exDropped = 0; _logger.LogInformation(\"psk-reporter: first {Call}\", datagram.Spots[0].Callsign);\n                return;", [DAEMON]),
 ("Q29 the pending queue is not bounded", D + "PskReporterEngine.cs", "MaxPendingRecords = 1000;", "MaxPendingRecords = 100_000_000;", [DAEMON]),
 ("Q30 a full datagram waits for the window", D + "PskReporterEngine.cs", "if (!due && (!full || nowUtc < _holdFullUntilUtc)) return null;", "if (!due) return null;", [DAEMON]),
 ("Q31 the random first-send offset is ignored", D + "PskReporterService.cs", "_engine.Activate(_clock.UtcNow, _firstSendOffset());", "_engine.Activate(_clock.UtcNow, TimeSpan.Zero);", [DAEMON]),
 ("Q32 the socket is IPv6 instead of IPv4", D + "PskReporterTransport.cs", "new(AddressFamily.InterNetwork);", "new(AddressFamily.InterNetworkV6);", [DAEMON]),
 ("Q33 a failed send drops its records instead of keeping them", D + "PskReporterEngine.cs", "_pending.InsertRange(0, datagram.Spots);", "", [DAEMON]),
 ("Q34 overlay: section list AND fallback both removed (an explicit null resets the block)", ["src/OpenWSFZ.Web/ConfigOverlay.cs", "src/OpenWSFZ.Web/ConfigOverlay.cs"],
  ["        \"pskReporter\",\n", "PskReporter            = config.PskReporter            ?? current.PskReporter            ?? new PskReporterConfig(),"],
  ["", "PskReporter            = config.PskReporter ?? new PskReporterConfig(),"], [WEB, CONFIG]),
 ("Q35 equivalence check for Q22: read-loop guard AND engine guard both removed", [D + "PskReporterService.cs", D + "PskReporterEngine.cs"],
  ["if (!IsActive) continue;", "if (!_active || batch.Results.Count == 0) return;"], ["", "if (batch.Results.Count == 0) return;"], [DAEMON]),
]


def run(tree, proj, flt):
    p = subprocess.run(["dotnet", "test", proj, "--filter", flt, "--nologo", "-v", "q"], cwd=tree, capture_output=True, text=True, encoding="utf-8", errors="replace")
    out = p.stdout + p.stderr
    failed = re.findall(r"^\s+Failed (.+?) \[", out, re.M)
    m = re.search(r"(Passed|Failed)!\s+- Failed:\s+(\d+), Passed:\s+(\d+).*?Total:\s+(\d+)", out)
    build_err = "error CS" in out
    return dict(project=proj, failed=int(m.group(2)) if m else None, passed=int(m.group(3)) if m else None, total=int(m.group(4)) if m else None,
                names=[f[:110] for f in failed][:6], build_error=build_err)


def main():
    tree, outp = sys.argv[1], sys.argv[2]
    only = set(sys.argv[3].split(",")) if len(sys.argv) > 3 else None
    res = []
    for mid, rel, old, new, sets, in [(a, b, c, d, e) for a, b, c, d, e in M]:
        if only and mid[:3] not in only: continue
        rels = rel if isinstance(rel, list) else [rel]
        olds = old if isinstance(old, list) else [old]
        news = new if isinstance(new, list) else [new]
        saved, bad = {}, None
        for r_, o_, n_ in zip(rels, olds, news):
            path = f"{tree}/{r_}"
            cur = open(path, encoding="utf-8", newline="").read()
            saved.setdefault(path, cur)
            nl = "\r\n" if "\r\n" in cur else "\n"
            nth = 1
            if o_.startswith("@@2:"):
                o_, nth = o_[4:], 2
            o, n = o_.replace("\n", nl), n_.replace("\n", nl)
            if cur.count(o) != nth:
                bad = f"pattern found {cur.count(o)} times, expected {nth}"; break
            if nth == 2:
                i = cur.index(o, cur.index(o) + 1)
                cur = cur[:i] + n + cur[i + len(o):]
            else:
                cur = cur.replace(o, n)
            open(path, "w", encoding="utf-8", newline="").write(cur)
        if bad:
            for pth, s in saved.items():
                open(pth, "w", encoding="utf-8", newline="").write(s)
            res.append(dict(id=mid, error=bad)); print(mid, "PATTERN", bad, flush=True); continue
        try:
            runs = [run(tree, p, f) for p, f in sets]
        finally:
            for pth, s in saved.items():
                open(pth, "w", encoding="utf-8", newline="").write(s)
        killed = any((r["failed"] or 0) > 0 or r["build_error"] for r in runs)
        res.append(dict(id=mid, killed=killed, runs=runs))
        print(mid, "KILLED" if killed else "SURVIVED", [(r["failed"], r["total"]) for r in runs], flush=True)
    json.dump(res, open(outp, "w"), indent=1)


main()
