using Microsoft.Extensions.Logging;
using OpenWSFZ.Abstractions;

namespace OpenWSFZ.Daemon;

/// <summary>
/// Concrete <see cref="IWorkedBeforeIndex"/> that reads <c>ADIF.log</c> (via
/// <see cref="AdifReader"/>, sharing its path with <see cref="AdifLogWriter"/> through
/// <see cref="AdifPathResolver"/>) and resolves each distinct logged callsign's DXCC
/// entity/continent/CQ-zone/ITU-zone through <see cref="ICallsignRegionStore"/>
/// (<c>qso-confirmation</c> capability, design.md Decisions 3–5; band-tracking added by
/// <c>qso-confirmation-band-awareness</c> design.md Decision 2).
///
/// <para>
/// Five in-memory dictionaries are maintained, one per worked-before dimension — worked
/// callsigns, worked DXCC entities, worked continents, worked CQ zones, worked ITU zones — each
/// mapping a worked value to the set of band names it has been worked on. A resolution that is a
/// lookup miss or resolves to the synthetic Q-series region (design.md Decision 4) is excluded
/// from the entity/continent/CQ-zone/ITU-zone dictionaries entirely — it can still contribute to
/// the callsign dictionary (the Contact/Call check is a plain string comparison, independent of
/// region resolution).
/// </para>
///
/// <para>
/// Thread-safe: <see cref="Register"/> can run concurrently with <see cref="Resolve"/> (a QSO
/// completing mid-session while a decode cycle is in flight) — all dictionary mutation and
/// lookup is guarded by a single <c>lock</c>. Data volumes here (hundreds to low thousands of
/// callsigns) make this a correctness detail, not a performance concern (design.md Risks).
/// </para>
/// </summary>
public sealed class WorkedBeforeIndex : IWorkedBeforeIndex
{
    private readonly IConfigStore                    _configStore;
    private readonly ICallsignRegionStore             _regionStore;
    private readonly ILogger<WorkedBeforeIndex>?      _logger;
    private readonly object                           _lock = new();

    // Value → set of band names worked on. A value present as a key (regardless of whether its
    // band set is empty) means "worked at all" — an empty band set means every historical
    // contribution for that value had no parseable BAND (qso-confirmation-band-awareness
    // design.md Decision 2).
    private readonly Dictionary<string, HashSet<string>> _callsignBands  = new(StringComparer.Ordinal);
    private readonly Dictionary<string, HashSet<string>> _entityBands    = new(StringComparer.Ordinal);
    private readonly Dictionary<string, HashSet<string>> _continentBands = new(StringComparer.Ordinal);
    private readonly Dictionary<int, HashSet<string>>    _cqZoneBands    = new();
    private readonly Dictionary<int, HashSet<string>>    _ituZoneBands   = new();

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
        var path    = AdifPathResolver.Resolve(_configStore);
        var entries = AdifReader.ReadEntries(path, _logger);

        // Group by distinct uppercased callsign, unioning every record's band contribution
        // (a callsign may have been worked on more than one band across its history) — so
        // ICallsignRegionStore.TryGetRegion is still only ever run once per distinct callsign
        // (design.md Decision 5), regardless of how many bands it was worked on.
        var bandsByCall = new Dictionary<string, HashSet<string>>(StringComparer.Ordinal);
        foreach (var entry in entries)
        {
            if (string.IsNullOrWhiteSpace(entry.Call)) continue;

            var call = entry.Call.ToUpperInvariant();
            if (!bandsByCall.TryGetValue(call, out var bands))
            {
                bands = new HashSet<string>(StringComparer.Ordinal);
                bandsByCall[call] = bands;
            }
            if (entry.Band is not null)
                bands.Add(entry.Band);
        }

        lock (_lock)
        {
            _callsignBands.Clear();
            _entityBands.Clear();
            _continentBands.Clear();
            _cqZoneBands.Clear();
            _ituZoneBands.Clear();

            foreach (var (call, bands) in bandsByCall)
                RegisterUnlocked(call, bands);
        }

        _logger?.LogInformation(
            "qso-confirmation: worked-before index built with {Count} distinct callsign(s) from '{Path}'.",
            bandsByCall.Count, path);

        return Task.CompletedTask;
    }

    /// <inheritdoc/>
    public void Register(string callsign, string? band)
    {
        if (string.IsNullOrWhiteSpace(callsign)) return;

        var bands = band is not null
            ? new HashSet<string>(StringComparer.Ordinal) { band }
            : [];

        lock (_lock)
        {
            RegisterUnlocked(callsign.ToUpperInvariant(), bands);
        }
    }

    /// <inheritdoc/>
    public WorkedBeforeInfo Resolve(string callsignToken, string? currentBand)
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

        WorkedBeforeState contact;
        WorkedBeforeState country  = WorkedBeforeState.Never;
        WorkedBeforeState continent = WorkedBeforeState.Never;
        WorkedBeforeState cqZone   = WorkedBeforeState.Never;
        WorkedBeforeState ituZone  = WorkedBeforeState.Never;

        lock (_lock)
        {
            contact = ResolveCallsignState(token, currentBand);

            if (region is not null && !region.Synthetic)
            {
                country = LookupState(_entityBands, region.Entity, currentBand);

                if (region.Continent is not null)
                    continent = LookupState(_continentBands, region.Continent, currentBand);

                if (region.CqZone is { } cq)
                    cqZone = LookupState(_cqZoneBands, cq, currentBand);

                if (region.ItuZone is { } itu)
                    ituZone = LookupState(_ituZoneBands, itu, currentBand);
            }
        }

        return new WorkedBeforeInfo(contact, country, continent, cqZone, ituZone);
    }

    // ── Internals (must be called under _lock) ─────────────────────────────────

    private void RegisterUnlocked(string upperCallsign, IReadOnlyCollection<string> bands)
    {
        AddOrUnion(_callsignBands, upperCallsign, bands);

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

        AddOrUnion(_entityBands, region.Entity, bands);

        if (region.Continent is not null)
            AddOrUnion(_continentBands, region.Continent, bands);

        if (region.CqZone is { } cq)
            AddOrUnion(_cqZoneBands, cq, bands);

        if (region.ItuZone is { } itu)
            AddOrUnion(_ituZoneBands, itu, bands);
    }

    private static void AddOrUnion<TKey>(
        Dictionary<TKey, HashSet<string>> dict, TKey key, IReadOnlyCollection<string> bands)
        where TKey : notnull
    {
        if (!dict.TryGetValue(key, out var set))
        {
            set = new HashSet<string>(StringComparer.Ordinal);
            dict[key] = set;
        }
        if (bands.Count > 0)
            set.UnionWith(bands);
    }

    private static WorkedBeforeState LookupState<TKey>(
        Dictionary<TKey, HashSet<string>> dict, TKey key, string? currentBand)
        where TKey : notnull
    {
        if (!dict.TryGetValue(key, out var bands)) return WorkedBeforeState.Never;
        if (currentBand is not null && bands.Contains(currentBand)) return WorkedBeforeState.ThisBand;
        return WorkedBeforeState.DifferentBand;
    }

    /// <summary>
    /// Resolves the Contact axis: any logged callsign that matches <paramref name="token"/>
    /// (exact, or either side a portable-suffixed variant of the other) contributes — a match
    /// on <paramref name="currentBand"/> from any matching entry wins over a different-band-only
    /// match, even when other matching entries were only worked on other bands.
    /// </summary>
    private WorkedBeforeState ResolveCallsignState(string token, string? currentBand)
    {
        bool matched = false;
        foreach (var (logged, bands) in _callsignBands)
        {
            if (!MatchesCallsign(token, logged)) continue;
            matched = true;
            if (currentBand is not null && bands.Contains(currentBand))
                return WorkedBeforeState.ThisBand;
        }
        return matched ? WorkedBeforeState.DifferentBand : WorkedBeforeState.Never;
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
