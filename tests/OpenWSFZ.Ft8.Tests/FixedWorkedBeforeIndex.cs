using OpenWSFZ.Abstractions;

namespace OpenWSFZ.Ft8.Tests;

/// <summary>
/// Test double for <see cref="IWorkedBeforeIndex"/> that returns a fixed, caller-supplied
/// <see cref="WorkedBeforeInfo"/> for every <see cref="Resolve"/> call — no ADIF/region I/O.
/// Mirrors <see cref="FixedCallsignRegionStore"/>'s no-disk contract.
/// </summary>
internal sealed class FixedWorkedBeforeIndex(WorkedBeforeInfo result) : IWorkedBeforeIndex
{
    public Task LoadAsync(CancellationToken cancellationToken = default) => Task.CompletedTask;

    public void Register(string callsign, string? band) { /* not needed for these tests */ }

    public WorkedBeforeInfo Resolve(string callsignToken, string? currentBand) => result;
}

/// <summary>
/// Test double for <see cref="IWorkedBeforeIndex"/> that always throws — used to verify that a
/// worked-before resolution failure degrades to <c>WorkedBefore = null</c> (every checkbox
/// unchecked) and never withholds the underlying decode (qso-confirmation capability's
/// "advisory only" requirement).
/// </summary>
internal sealed class ThrowingWorkedBeforeIndex : IWorkedBeforeIndex
{
    public Task LoadAsync(CancellationToken cancellationToken = default)
        => throw new InvalidOperationException("Simulated worked-before-index failure.");

    public void Register(string callsign, string? band)
        => throw new InvalidOperationException("Simulated worked-before-index failure.");

    public WorkedBeforeInfo Resolve(string callsignToken, string? currentBand)
        => throw new InvalidOperationException("Simulated worked-before-index failure.");
}

/// <summary>
/// Test double for <see cref="IWorkedBeforeIndex"/> that records every <paramref name="currentBand"/>
/// value passed to <see cref="Resolve"/> — used to verify <c>Ft8Decoder.DecodeAsync</c> threads
/// its <c>currentBand</c> parameter through correctly (<c>qso-confirmation-band-awareness</c>,
/// task 4.2/4.4).
/// </summary>
internal sealed class CapturingWorkedBeforeIndex : IWorkedBeforeIndex
{
    public List<string?> ResolvedBands { get; } = [];

    public Task LoadAsync(CancellationToken cancellationToken = default) => Task.CompletedTask;

    public void Register(string callsign, string? band) { /* not needed for these tests */ }

    public WorkedBeforeInfo Resolve(string callsignToken, string? currentBand)
    {
        ResolvedBands.Add(currentBand);
        return WorkedBeforeInfo.None;
    }
}
