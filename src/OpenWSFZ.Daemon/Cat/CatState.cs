using OpenWSFZ.Abstractions;

namespace OpenWSFZ.Daemon.Cat;

/// <summary>
/// Thread-safe singleton that holds live CAT telemetry for consumption by
/// all components that need the effective dial frequency (FR-032, FR-033).
///
/// <para>
/// <see cref="DialFrequencyMHz"/> is backed by a <c>long</c> and updated via
/// <see cref="System.Threading.Interlocked.Exchange(ref long, long)"/>, preventing
/// torn reads on 32-bit platforms.  <see cref="Status"/> is <c>volatile</c>.
/// </para>
///
/// <para>
/// A <see cref="double.NaN"/> sentinel represents "no frequency yet" (null).
/// This avoids the need for a separate flag field while keeping the
/// Interlocked exchange pattern.
/// </para>
/// </summary>
public sealed class CatState : ICatState
{
    // NaN sentinel: a frequency was never successfully polled.
    private static readonly long NanBits = BitConverter.DoubleToInt64Bits(double.NaN);

    private long _dialFreqBits = NanBits;

#pragma warning disable CS0420  // volatile field passed by ref — safe here; Interlocked is correct
    private volatile CatConnectionStatus _status = CatConnectionStatus.Disabled;
#pragma warning restore CS0420

    // ── ICatState ─────────────────────────────────────────────────────────────

    /// <inheritdoc/>
    public double? DialFrequencyMHz
    {
        get
        {
            var bits  = Interlocked.Read(ref _dialFreqBits);
            var value = BitConverter.Int64BitsToDouble(bits);
            return double.IsNaN(value) ? null : value;
        }
    }

    /// <inheritdoc/>
    public CatConnectionStatus Status => _status;

    // ── Internal mutation (CatPollingService only) ────────────────────────────

    /// <summary>
    /// Updates frequency and connection status.  Each field is individually atomic; the
    /// two-field compound update is not.
    /// Pass <c>null</c> for <paramref name="freqMHz"/> to clear the last-known frequency
    /// (e.g. on connection loss).
    /// </summary>
    internal void Update(double? freqMHz, CatConnectionStatus status)
    {
        var bits = freqMHz.HasValue
            ? BitConverter.DoubleToInt64Bits(freqMHz.Value)
            : NanBits;

        Interlocked.Exchange(ref _dialFreqBits, bits);
        _status = status;
    }
}
