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

    public void Register(string callsign) { /* not needed for these tests */ }

    public WorkedBeforeInfo Resolve(string callsignToken) => result;
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

    public void Register(string callsign)
        => throw new InvalidOperationException("Simulated worked-before-index failure.");

    public WorkedBeforeInfo Resolve(string callsignToken)
        => throw new InvalidOperationException("Simulated worked-before-index failure.");
}
