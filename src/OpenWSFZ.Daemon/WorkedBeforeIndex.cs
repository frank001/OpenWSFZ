using Microsoft.Extensions.Logging;
using OpenWSFZ.Abstractions;

namespace OpenWSFZ.Daemon;

/// <summary>
/// Concrete <see cref="IWorkedBeforeIndex"/> that reads <c>ADIF.log</c> (via
/// <see cref="AdifReader"/>, sharing its path with <see cref="AdifLogWriter"/> through
/// <see cref="AdifPathResolver"/>) and resolves each distinct logged callsign's DXCC
/// entity/continent through <see cref="ICallsignRegionStore"/> (<c>qso-confirmation</c>
/// capability, design.md Decisions 3–5).
///
/// <para>
/// Three in-memory sets are maintained: worked callsigns (uppercased, exactly as logged),
/// worked DXCC entities, and worked continents. A resolution that is a lookup miss or resolves
/// to the synthetic Q-series region (design.md Decision 4) is excluded from the entity/continent
/// sets entirely — it can still contribute to the callsign set (the Partner/Call check is a
/// plain string comparison, independent of region resolution).
/// </para>
///
/// <para>
/// Thread-safe: <see cref="Register"/> can run concurrently with <see cref="Resolve"/> (a QSO
/// completing mid-session while a decode cycle is in flight) — all set mutation and lookup is
/// guarded by a single <c>lock</c>. Data volumes here (hundreds to low thousands of callsigns)
/// make this a correctness detail, not a performance concern (design.md Risks).
/// </para>
/// </summary>
public sealed class WorkedBeforeIndex : IWorkedBeforeIndex
{
    private readonly IConfigStore                    _configStore;
    private readonly ICallsignRegionStore             _regionStore;
    private readonly ILogger<WorkedBeforeIndex>?      _logger;
    private readonly object                           _lock = new();

    private readonly HashSet<string> _callsigns = new(StringComparer.Ordinal);
    private readonly HashSet<string> _entities  = new(StringComparer.Ordinal);
    private readonly HashSet<string> _continents = new(StringComparer.Ordinal);

    public WorkedBeforeIndex(
        IConfigStore                configStore,
        ICallsignRegionStore        regionStore,
        ILogger<WorkedBeforeIndex>? logger = null)
    {
        _configStore = configStore;
        _regionStore = regionStore;
        _logger      = logger;
    }

    /// <inheritdoc/>
    public Task LoadAsync(CancellationToken cancellationToken = default)
    {
        var path = AdifPathResolver.Resolve(_configStore);
        var raw  = AdifReader.ReadCallsigns(path, _logger);

        // Dedupe before resolving region so each distinct callsign is only ever run through
        // ICallsignRegionStore.TryGetRegion once (design.md Decision 5).
        var distinct = new HashSet<string>(StringComparer.Ordinal);
        foreach (var call in raw)
        {
            if (!string.IsNullOrWhiteSpace(call))
                distinct.Add(call.ToUpperInvariant());
        }

        lock (_lock)
        {
            _callsigns.Clear();
            _entities.Clear();
            _continents.Clear();

            foreach (var call in distinct)
                RegisterUnlocked(call);
        }

        _logger?.LogInformation(
            "qso-confirmation: worked-before index built with {Count} distinct callsign(s) from '{Path}'.",
            distinct.Count, path);

        return Task.CompletedTask;
    }

    /// <inheritdoc/>
    public void Register(string callsign)
    {
        if (string.IsNullOrWhiteSpace(callsign)) return;

        lock (_lock)
        {
            RegisterUnlocked(callsign.ToUpperInvariant());
        }
    }

    /// <inheritdoc/>
    public WorkedBeforeInfo Resolve(string callsignToken)
    {
        if (string.IsNullOrWhiteSpace(callsignToken)) return WorkedBeforeInfo.None;

        var token = callsignToken.ToUpperInvariant();

        RegionInfo? region;
        try
        {
            region = _regionStore.TryGetRegion(StripPortableSuffix(token));
        }
        catch
        {
            region = null;
        }

        bool callMatch, countryMatch = false, regionMatch = false;
        lock (_lock)
        {
            callMatch = MatchesAnyLoggedCallsign(token);

            if (region is not null && !region.Synthetic)
            {
                countryMatch = _entities.Contains(region.Entity);
                regionMatch  = region.Continent is not null && _continents.Contains(region.Continent);
            }
        }

        return new WorkedBeforeInfo(callMatch, countryMatch, regionMatch);
    }

    // ── Internals (must be called under _lock) ─────────────────────────────────

    private void RegisterUnlocked(string upperCallsign)
    {
        _callsigns.Add(upperCallsign);

        RegionInfo? region;
        try
        {
            region = _regionStore.TryGetRegion(StripPortableSuffix(upperCallsign));
        }
        catch
        {
            region = null;
        }

        if (region is null || region.Synthetic) return;

        _entities.Add(region.Entity);
        if (region.Continent is not null)
            _continents.Add(region.Continent);
    }

    private bool MatchesAnyLoggedCallsign(string token)
    {
        foreach (var logged in _callsigns)
        {
            if (MatchesCallsign(token, logged)) return true;
        }
        return false;
    }

    /// <summary>
    /// Ports <c>web/js/main.js</c>'s <c>tokenMatchesCallsign</c> semantics to the backend
    /// (design.md Decision 3), extended to check both directions: two tokens are the same
    /// station if they are exactly equal, or if either is a portable-suffixed variant
    /// (<c>"/"</c>-delimited) of the other's base callsign.
    /// </summary>
    internal static bool MatchesCallsign(string a, string b)
    {
        if (string.Equals(a, b, StringComparison.Ordinal)) return true;
        if (a.StartsWith(b + "/", StringComparison.Ordinal)) return true;
        if (b.StartsWith(a + "/", StringComparison.Ordinal)) return true;
        return false;
    }

    private static string StripPortableSuffix(string token)
    {
        var slashPos = token.IndexOf('/');
        return slashPos >= 0 ? token[..slashPos] : token;
    }
}
