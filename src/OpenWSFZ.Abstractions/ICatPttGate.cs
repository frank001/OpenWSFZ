namespace OpenWSFZ.Abstractions;

/// <summary>
/// Narrow PTT-keying seam exposed by the CAT subsystem (FR-056).
/// Implemented by <c>CatPollingService</c>, which is the sole holder of the shared
/// <see cref="IRadioConnection"/> instance used for CAT; this interface lets a
/// CAT-command <c>IPttController</c> implementation assert/de-assert PTT without
/// ever touching <see cref="IRadioConnection"/> directly, so every call is
/// automatically serialised against the CAT poll loop's own frequency reads
/// (design.md Decision 1 of the <c>cat-tx-ptt</c> change).
///
/// <para>
/// Mirrors <see cref="ICatTuner"/>/<see cref="ICatController"/> — the other narrow
/// public seams <c>CatPollingService</c> exposes for its other capabilities.
/// </para>
/// </summary>
public interface ICatPttGate
{
    /// <summary>
    /// Commands the active CAT connection to key (<paramref name="transmitting"/> =
    /// <c>true</c>) or unkey (<paramref name="transmitting"/> = <c>false</c>) the
    /// transmitter, waiting for any in-flight poll to complete first.
    /// </summary>
    /// <exception cref="InvalidOperationException">
    /// Thrown when CAT is disabled (<c>AppConfig.Cat.Enabled == false</c>) or no
    /// connection has ever been established.
    /// </exception>
    Task SetPttAsync(bool transmitting, CancellationToken cancellationToken = default);
}
