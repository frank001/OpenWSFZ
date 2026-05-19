namespace TraceabilityCheck;

/// <summary>
/// Runs the two rubric checks (C1: missing mappings; stale references) and
/// builds the data model for the report.
/// </summary>
public sealed class TraceabilityAnalyser
{
    private readonly IReadOnlySet<string> _knownIds;
    private readonly IReadOnlyList<TestEntry> _tests;

    /// <summary>
    /// IDs in this set are acknowledged as pending their implementing phase.
    /// They are excluded from the missing-mapping check (C1) but stale-reference
    /// checks still apply (an ID listed as debt must still exist in REQUIREMENTS.md).
    /// </summary>
    private readonly IReadOnlySet<string> _debtIds;

    public TraceabilityAnalyser(
        IReadOnlySet<string> knownIds,
        IReadOnlyList<TestEntry> tests,
        IReadOnlySet<string>? debtIds = null)
    {
        _knownIds = knownIds;
        _tests = tests;
        _debtIds = debtIds ?? new HashSet<string>(StringComparer.Ordinal);
    }

    /// <summary>Runs all checks and returns the analysis result.</summary>
    public AnalysisResult Analyse()
    {
        // Build mapping: requirementId -> list of test display names that reference it.
        var mapping = new Dictionary<string, List<string>>(StringComparer.Ordinal);
        foreach (var id in _knownIds)
        {
            mapping[id] = new List<string>();
        }

        var staleRefs = new List<(string Id, string TestName)>();

        foreach (var test in _tests)
        {
            var ids = TestAssemblyScanner.ExtractIds(test.DisplayName);
            foreach (var id in ids)
            {
                if (_knownIds.Contains(id))
                {
                    mapping[id].Add(test.DisplayName);
                }
                else
                {
                    staleRefs.Add((id, test.DisplayName));
                }
            }
        }

        // Stale debt: an ID listed in the debt file that no longer exists in REQUIREMENTS.md.
        var staleDebtIds = _debtIds
            .Where(id => !_knownIds.Contains(id))
            .OrderBy(id => id, StringComparer.Ordinal)
            .ToList();

        foreach (var id in staleDebtIds)
        {
            staleRefs.Add((id, "[traceability-debt file]"));
        }

        // Missing-mapping check: IDs in the debt file are excluded (they are pending).
        var unmapped = _knownIds
            .Where(id => mapping[id].Count == 0 && !_debtIds.Contains(id))
            .OrderBy(id => id, StringComparer.Ordinal)
            .ToList();

        return new AnalysisResult(
            Mapping: mapping.ToDictionary(kv => kv.Key, kv => (IReadOnlyList<string>)kv.Value),
            UnmappedIds: unmapped,
            StaleReferences: staleRefs);
    }
}

/// <summary>The output of the traceability analysis.</summary>
public sealed record AnalysisResult(
    IReadOnlyDictionary<string, IReadOnlyList<string>> Mapping,
    IReadOnlyList<string> UnmappedIds,
    IReadOnlyList<(string Id, string TestName)> StaleReferences)
{
    public bool IsSuccess => UnmappedIds.Count == 0 && StaleReferences.Count == 0;
}
