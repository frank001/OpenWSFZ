using OpenWSFZ.Abstractions;
using OpenWSFZ.Daemon;

namespace OpenWSFZ.Daemon.Tests;

/// <summary>
/// Scripted batch-1-only integration replays for the answerer and the caller (late-batches-in-qso AC1 / R4). The scripts use
/// nothing that exists only after the change, so this file builds unchanged on origin/main 0c7124db: run there, the lists below
/// are the "before"; run on the new tip they must be identical, with and without EMPTY batches 2 and 3 interleaved.
/// Each output line is "slot-start-clock message", so message order AND slot starts are compared as exact lists.
/// </summary>
internal static class QsoReplayScripts
{
    private const string Ours = QsoRigBase.Ours;
    private const string P1 = "Q1TST", P2 = "Q1ABC", P3 = "Q1DEF", P4 = "Q1GHI", Other = "Q1ZZZ";

    private static DecodeResult M(string message, int snr = -5) => QsoRigBase.Make(message, snr);

    /// <summary>Late (supplementary) batches to interleave after the batch 1 of a cycle, with the delay after its processing time.</summary>
    public delegate IEnumerable<(TimeSpan After, DecodeBatch Batch)> LateBatches(int cycle);

    private static async Task Step(QsoRigBase rig, int n, LateBatches? late, params DecodeResult[] results)
    {
        await rig.Batch1Async(n, results);
        if (late is null) return;
        foreach (var (after, batch) in late(n))
            await rig.FeedAsync(Cy.Batch1Time(n) + after, batch);
    }

    private static List<string> Lines(QsoRigBase rig, string end)
    {
        var lines = rig.Tx.Select(t => $"{t.At:HH:mm:ss.fff} {t.Message}").ToList();
        lines.Add(end);
        return lines;
    }

    /// <summary>
    /// The answerer: a full QSO (answer, report, RR73 -> 73); a QSO with missed replies and RRR; a partner who goes to
    /// another station (abort); and a QSO that exhausts its retries.
    /// </summary>
    public static async Task<IReadOnlyList<string>> AnswererAsync(LateBatches? late = null)
    {
        await using var rig = await AnswererRig.CreateAsync(autoAnswer: true, retryCount: 2);

        // QSO 1: straight through.
        await Step(rig, 0, late, M($"CQ {P1} JO22"));
        await Step(rig, 1, late);
        await Step(rig, 2, late, M($"{Ours} {P1} +05"));
        await Step(rig, 3, late);
        await Step(rig, 4, late, M($"{Ours} {P1} RR73"));
        // QSO 2: a missed reply in WaitReport (retry), the report, a missed reply in WaitRr73 (retry), then RRR.
        await Step(rig, 5, late, M($"CQ {P2} IO91"));
        await Step(rig, 6, late);
        await Step(rig, 7, late, M("CQ Q2NOISE IO91"));
        await Step(rig, 8, late);
        await Step(rig, 9, late, M($"{Ours} {P2} -12", snr: -12));
        await Step(rig, 10, late);
        await Step(rig, 11, late, M("CQ Q2NOISE IO91"));
        await Step(rig, 12, late);
        await Step(rig, 13, late, M($"{Ours} {P2} RRR"));
        // QSO 3: the partner is heard working another station -> abort, no transmission.
        await Step(rig, 14, late, M($"CQ {P3} FN20"));
        await Step(rig, 15, late);
        await Step(rig, 16, late, M($"{Other} {P3} -03"));
        // QSO 4: nothing ever comes back: two retries, then the abort.
        await Step(rig, 17, late, M($"CQ {P4} EM12"));
        await Step(rig, 18, late);
        await Step(rig, 19, late, M("CQ Q2NOISE IO91"));
        await Step(rig, 20, late);
        await Step(rig, 21, late, M("CQ Q2NOISE IO91"));
        await Step(rig, 22, late);
        await Step(rig, 23, late, M("CQ Q2NOISE IO91"));
        await Step(rig, 24, late);

        return Lines(rig, $"end state={rig.Sut.State} retry={rig.RetryCount}");
    }

    /// <summary>
    /// The caller: CQ, an answer, the report, a roger report -> RR73; a CQ with a missed answer (CQ repeat) then an answer
    /// and a missed roger (report retry), then the roger.
    /// </summary>
    public static async Task<IReadOnlyList<string>> CallerAsync(LateBatches? late = null)
    {
        await using var rig = await CallerRig.CreateAsync(retryCount: 2);

        // QSO 1.
        await Step(rig, 0, late);                                   // Idle -> CQ
        await Step(rig, 1, late);                                   // own slot
        await Step(rig, 2, late, M($"{Ours} {P1} JO22"));           // answer -> report
        await Step(rig, 3, late);
        await Step(rig, 4, late, M($"{Ours} {P1} R-07"));           // roger report -> RR73 -> complete
        // QSO 2: a missed answer (CQ repeat), the answer, a missed roger (report retry), the roger.
        await Step(rig, 5, late);                                   // Idle -> CQ
        await Step(rig, 6, late);
        await Step(rig, 7, late, M("CQ Q2NOISE IO91"));             // missed -> CQ repeat
        await Step(rig, 8, late);
        await Step(rig, 9, late, M($"{Ours} {P2} IO91"));           // answer -> report
        await Step(rig, 10, late);
        await Step(rig, 11, late, M("CQ Q2NOISE IO91"));            // missed roger -> report retry
        await Step(rig, 12, late);
        await Step(rig, 13, late, M($"{Ours} {P2} R-11"));          // roger -> RR73 -> complete
        // QSO 3: the partner is heard working another station -> abort.
        await Step(rig, 14, late);                                  // Idle -> CQ
        await Step(rig, 15, late);
        await Step(rig, 16, late, M($"{Ours} {P3} FN20"));          // answer -> report
        await Step(rig, 17, late);
        await Step(rig, 18, late, M($"{Other} {P3} -03"));          // busy -> abort

        return Lines(rig, $"end state={rig.Sut.State} retry={rig.RetryCount}");
    }
}
