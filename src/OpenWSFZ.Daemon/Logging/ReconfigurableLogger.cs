namespace OpenWSFZ.Daemon.Logging;

/// <summary>
/// A Serilog <see cref="Serilog.ILogger"/> wrapper with a stable object identity, whose inner
/// target can be swapped at runtime without invalidating references already cached elsewhere
/// (f-004-operator-visibility-improvements, log-viewer).
///
/// <para>
/// <b>The bug this fixes:</b> Serilog.Extensions.Logging's <c>SerilogLogger</c> — the class
/// backing every <c>Microsoft.Extensions.Logging.ILogger&lt;T&gt;</c> resolved via
/// <c>ILoggingBuilder.AddSerilog()</c> — resolves <c>Serilog.Log.Logger</c> exactly <b>once</b>,
/// in its own constructor, and caches the result for its entire lifetime. Since
/// <c>Microsoft.Extensions.Logging</c>'s <c>LoggerFactory</c> caches one <c>ILogger</c> instance
/// per category name, the first time any given category logs, it permanently locks onto whatever
/// <c>Serilog.Log.Logger</c> was current at that moment.
/// </para>
///
/// <para>
/// <see cref="LoggingPipeline.Apply"/> previously reassigned <c>Log.Logger</c> to a brand-new
/// <c>Serilog.Core.Logger</c> object on every reconfigure (e.g. the operator enabling file
/// logging from the Settings page while the daemon is already running) — meaning virtually every
/// <c>ILogger&lt;T&gt;</c> call in the application (not just this class's own diagnostics)
/// silently kept writing to the first logger built at process startup, forever, no matter how
/// many times <c>Apply()</c> ran afterward. Confirmed against a live daemon: after a runtime
/// reconfigure, ASP.NET Core's own request-logging middleware kept appending to the OLD log file;
/// the newly-configured file received nothing, even after 60+ seconds and further HTTP activity.
/// </para>
///
/// <para>
/// <b>The fix:</b> assign <c>Log.Logger</c> to a single instance of this class exactly once, at
/// process startup, and never reassign it again. <see cref="Reconfigure"/> swaps only the inner
/// target; every already-cached <c>ILogger&lt;T&gt;</c> reference — and any
/// <c>.ForContext(...)</c> derivative of one, since <see cref="Serilog.ILogger"/>'s default
/// interface members for <c>ForContext</c>/<c>IsEnabled</c>/etc. all route back through this
/// instance's own <see cref="Write"/> — continues to observe the current inner logger.
/// </para>
/// </summary>
internal sealed class ReconfigurableLogger : Serilog.ILogger
{
    private volatile Serilog.ILogger _inner;

    public ReconfigurableLogger(Serilog.ILogger initial) => _inner = initial;

    /// <summary>
    /// Swaps the inner target logger. Called by <see cref="LoggingPipeline.Apply"/> instead of
    /// reassigning <c>Serilog.Log.Logger</c> itself.
    /// </summary>
    public void Reconfigure(Serilog.ILogger next) => _inner = next;

    /// <inheritdoc/>
    public void Write(Serilog.Events.LogEvent logEvent) => _inner.Write(logEvent);

    /// <inheritdoc/>
    public bool IsEnabled(Serilog.Events.LogEventLevel level) => _inner.IsEnabled(level);
}
