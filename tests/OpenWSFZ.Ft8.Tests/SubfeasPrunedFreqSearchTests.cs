using System.Diagnostics;
using FluentAssertions;
using Xunit;
using Xunit.Abstractions;

namespace OpenWSFZ.Ft8.Tests;

/// <summary>
/// sub-feas-speed-redesign Stage B item B2 (tasks.md 15.4, design.md D11): the pruned <c>freq_search</c> of the native fit
/// against the REFERENCE full-FFT search.
///
/// <para>
/// <c>freq_search</c> is a <c>static</c> function inside <c>subfeas_fit.c</c> and the shipped export list is NOT widened to
/// reach it, so the equivalence is checked by a C self-test, <c>tests/Ft8.FitProbe/native/freq_search_selftest.c</c>, that
/// <c>#include</c>s the product source and carries Stage A's function verbatim as the oracle. This test BUILDS AND RUNS it
/// (<c>run_freq_search_selftest.py</c>: MSVC <c>/std:c11 /O2 /W3</c> on Windows, <c>cc -std=c11 -O2</c> elsewhere, the shipped
/// flags) and requires: every synthetic tone across the full ±2.0 Hz range (both edges, 0, bin centres, between bins, just
/// outside), with and without noise at a fixed seed, and every chirp, returns the SAME bin as the reference; two tones 1 % and
/// 0.1 % apart both pick the larger; an exactly equal pair keeps the reference's scan-order tie-break; a set cancel flag
/// returns -4 promptly. It fails, it does not skip, when no C compiler can be found: the same compilers build the product.
/// </para>
///
/// <para>
/// The managed-side counterpart is <c>SubfeasNativeSpeedTests</c> 8.1: its recorded Stage A fit hashes (golden) are asserted
/// bit-for-bit through the real <c>ft8_subfeas_fit_signal</c> with the pruned search in place, which only holds if the pruned
/// search lands on Stage A's bins on those signals.
/// </para>
/// </summary>
public sealed class SubfeasPrunedFreqSearchTests(ITestOutputHelper output)
{
    private static string RepoRoot()
    {
        for (var dir = new DirectoryInfo(AppContext.BaseDirectory); dir is not null; dir = dir.Parent)
            if (File.Exists(Path.Combine(dir.FullName, "OpenWSFZ.slnx"))) return dir.FullName;
        throw new InvalidOperationException("OpenWSFZ.slnx not found above " + AppContext.BaseDirectory);
    }

    private static (int ExitCode, string Output) Python(string script, string scratch)
    {
        foreach (var exe in new[] { "python", "python3" })
        {
            try
            {
                var psi = new ProcessStartInfo(exe)
                {
                    RedirectStandardOutput = true, RedirectStandardError = true, UseShellExecute = false,
                };
                psi.ArgumentList.Add(script);
                psi.ArgumentList.Add(scratch);
                using var p = Process.Start(psi)!;
                var stdout = p.StandardOutput.ReadToEndAsync();
                var stderr = p.StandardError.ReadToEndAsync();
                if (!p.WaitForExit(TimeSpan.FromMinutes(8)))
                {
                    p.Kill(entireProcessTree: true);
                    return (-1, "timed out after 8 minutes");
                }
                return (p.ExitCode, stdout.Result + stderr.Result);
            }
            catch (System.ComponentModel.Win32Exception) { /* try the next interpreter name */ }
        }
        return (3, "no python interpreter found");
    }

    [Fact(DisplayName = "B2: the pruned freq_search returns the reference's bin on every tone, chirp and two-tone case, keeps the tie-break, and honours the cancel flag")]
    public void PrunedFreqSearch_MatchesTheReferenceFullFftSearch()
    {
        string root = RepoRoot();
        string script = Path.Combine(root, "tests", "Ft8.FitProbe", "native", "run_freq_search_selftest.py");
        string scratch = Path.Combine(Path.GetTempPath(), "freq_search_selftest_" + Environment.ProcessId);

        var (code, text) = Python(script, scratch);
        output.WriteLine(text);
        try { Directory.Delete(scratch, recursive: true); } catch (IOException) { /* a still-open exe handle: leave it to the temp cleaner */ }

        code.Should().NotBe(3, "a C compiler is needed to build the self-test (the same one that builds libft8)");
        code.Should().Be(0, "the self-test's own assertions must all hold; its output is above");
        text.Should().Contain("RESULT: PASS");
        text.Should().MatchRegex(@"A: \d+ tones \(noise-free and noisy\), 0 bin disagreements");
        text.Should().MatchRegex(@"B: \d+ chirps, 0 bin disagreements");
        text.Should().MatchRegex(@"C: 4 two-tone cases \(1% and 0\.1% gaps\), 0 disagreements");
        text.Should().Contain("E: cancel flag set -> -4");
    }
}
