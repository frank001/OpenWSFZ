using NSubstitute.Core;

namespace OpenWSFZ.TestSupport;

/// <summary>
/// Shared test-synchronization primitive: poll a condition at a bounded interval until it is
/// satisfied or a timeout elapses, instead of awaiting a fixed-duration delay and assuming an
/// asynchronous condition has been reached by then (fix-flaky-test-delay-synchronization).
///
/// This is not a new invention — it generalizes the shape that
/// <c>QsoAnswererServiceTests.WaitForStateAsync</c>/<c>WaitForKeyingAsync</c>/
/// <c>WaitForKeyDownAsync</c>/<c>WaitForPublishCountAsync</c> (and
/// <c>QsoCallerServiceTests</c>'s independently hand-duplicated copies) already converged on
/// separately, into one shared place every test project can reference.
/// </summary>
public static class Poll
{
    /// <summary>
    /// Matches the majority convention already in use across the audited call sites (design.md
    /// Decision 1). The one 3s outlier (<c>QsoAnswererServiceTests.WaitForStateAsync</c>'s original
    /// default) is a caller-supplied override at its migrated call sites, not a behavior change.
    /// </summary>
    public static readonly TimeSpan DefaultTimeout = TimeSpan.FromSeconds(5);

    /// <summary>Matches every existing hand-written polling loop found in the audit, with no exceptions.</summary>
    public static readonly TimeSpan DefaultPollInterval = TimeSpan.FromMilliseconds(10);

    /// <summary>
    /// Polls <paramref name="condition"/> at <paramref name="pollInterval"/> intervals until it
    /// returns <see langword="true"/> or <paramref name="timeout"/> elapses.
    /// </summary>
    /// <param name="condition">The condition to poll. Evaluated synchronously on each tick.</param>
    /// <param name="timeout">Overall deadline. Defaults to <see cref="DefaultTimeout"/>.</param>
    /// <param name="pollInterval">Delay between polls. Defaults to <see cref="DefaultPollInterval"/>.</param>
    /// <param name="timeoutMessage">
    /// Optional factory for the <see cref="TimeoutException"/> message, invoked only on timeout so
    /// it can read the condition's current (failing) state at that moment.
    /// </param>
    /// <exception cref="TimeoutException">
    /// Thrown if <paramref name="condition"/> never returns <see langword="true"/> before the deadline.
    /// </exception>
    /// <remarks>
    /// A transient <see cref="IOException"/> raised by <paramref name="condition"/> (e.g. a
    /// just-closed file briefly opened non-shared by an external process such as Windows Defender
    /// or the search indexer) is treated the same as a <see langword="false"/> result and the poll
    /// continues until the bounded timeout, rather than aborting immediately
    /// (dev-tasks/2026-09-14-cyclearchiveservicetests-manifestgapmarker-ioexception-repeat-flake.md).
    /// If the condition never stops throwing, the last <see cref="IOException"/> observed is
    /// wrapped as the <see cref="TimeoutException"/>'s <see cref="Exception.InnerException"/> so a
    /// genuinely persistent I/O failure is still visible in the failure, not just "timed out".
    /// Only <see cref="IOException"/> is tolerated; every other exception type still propagates
    /// immediately, unchanged from prior behavior.
    /// </remarks>
    public static async Task UntilAsync(
        Func<bool> condition,
        TimeSpan? timeout = null,
        TimeSpan? pollInterval = null,
        Func<string>? timeoutMessage = null)
    {
        var deadline = DateTime.UtcNow + (timeout ?? DefaultTimeout);
        var interval = pollInterval ?? DefaultPollInterval;
        IOException? lastTransientError = null;
        while (DateTime.UtcNow < deadline)
        {
            try
            {
                if (condition()) return;
            }
            catch (IOException ex)
            {
                lastTransientError = ex;
            }

            await Task.Delay(interval);
        }

        throw new TimeoutException(
            timeoutMessage?.Invoke() ?? "Condition not met within timeout.",
            lastTransientError);
    }

    /// <summary>
    /// Polls <paramref name="actual"/> until it equals <paramref name="expected"/> or times out.
    /// Generalizes state-equality polling (e.g. <c>svc.State == expected</c>) and boolean-flag
    /// polling (e.g. <c>svc.Keying == expected</c>) — both are the same equality shape.
    /// </summary>
    /// <param name="actual">Reads the current value. Evaluated on every poll tick.</param>
    /// <param name="expected">The value being waited for.</param>
    /// <param name="what">
    /// Optional human-readable label for the value being polled, used only in the timeout message.
    /// </param>
    public static Task WaitForEqualAsync<T>(
        Func<T> actual,
        T expected,
        TimeSpan? timeout = null,
        TimeSpan? pollInterval = null,
        string? what = null)
    {
        return UntilAsync(
            () => EqualityComparer<T>.Default.Equals(actual(), expected),
            timeout,
            pollInterval,
            () => $"Expected {what ?? "value"} to be {expected} but was {actual()} " +
                  $"after {(timeout ?? DefaultTimeout).TotalSeconds:F1}s.");
    }

    /// <summary>
    /// Polls until at least one recorded call to <paramref name="methodName"/> is observed, or times out.
    /// </summary>
    /// <param name="calls">
    /// Factory returning the substitute's current received calls, e.g.
    /// <c>() =&gt; ptt.ReceivedCalls()</c>. Deliberately a factory, not a plain
    /// <see cref="IEnumerable{ICall}"/> snapshot: NSubstitute's <c>ReceivedCalls()</c> returns a
    /// snapshot taken at call time, not a live view — capturing it once, before the poll loop
    /// starts, would freeze the list at whatever it held at that instant and the wrapper would
    /// never observe calls received afterward. Re-invoking the factory each poll tick (matching how
    /// the hand-written helpers this generalizes already called <c>ReceivedCalls()</c> fresh inside
    /// their own loops) is what makes this actually see new calls as they arrive.
    /// </param>
    /// <param name="methodName">The method name to look for, e.g. <c>nameof(IPttController.KeyDownAsync)</c>.</param>
    public static Task WaitForCallAsync(
        Func<IEnumerable<ICall>> calls,
        string methodName,
        TimeSpan? timeout = null,
        TimeSpan? pollInterval = null)
    {
        return UntilAsync(
            () => calls().Any(c => c.GetMethodInfo().Name == methodName),
            timeout,
            pollInterval,
            () => $"Expected a call to {methodName} but none was received " +
                  $"within {(timeout ?? DefaultTimeout).TotalSeconds:F1}s.");
    }

    /// <summary>
    /// Polls until at least <paramref name="expectedCount"/> recorded calls to
    /// <paramref name="methodName"/> are observed, or times out. See
    /// <see cref="WaitForCallAsync"/>'s remarks on why <paramref name="calls"/> is a factory.
    /// </summary>
    public static Task WaitForCallCountAsync(
        Func<IEnumerable<ICall>> calls,
        string methodName,
        int expectedCount,
        TimeSpan? timeout = null,
        TimeSpan? pollInterval = null)
    {
        return UntilAsync(
            () => calls().Count(c => c.GetMethodInfo().Name == methodName) >= expectedCount,
            timeout,
            pollInterval,
            () => $"Expected at least {expectedCount} call(s) to {methodName} but did not observe " +
                  $"them within {(timeout ?? DefaultTimeout).TotalSeconds:F1}s.");
    }
}
