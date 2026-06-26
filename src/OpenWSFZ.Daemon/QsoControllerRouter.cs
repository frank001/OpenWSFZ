using Microsoft.Extensions.Logging;
using OpenWSFZ.Abstractions;
using OpenWSFZ.Web;

namespace OpenWSFZ.Daemon;

/// <summary>
/// Runtime role switcher that wraps both <see cref="QsoAnswererService"/> and
/// <see cref="QsoCallerService"/> and delegates <see cref="IQsoController"/> calls
/// to whichever service is currently active.
///
/// <para>
/// Allows the operator to click "Call CQ" at any time — even when the daemon was
/// started in Answerer mode — without a settings visit or daemon restart.  After the
/// caller QSO completes or is aborted, the active role reverts automatically to the
/// configured role (typically Answerer).
/// </para>
///
/// <para>
/// <see cref="SwitchToCallerAsync"/> is called by <c>POST /api/v1/tx/call-cq</c>.
/// <see cref="QsoCallerService.OnBecameIdle"/> is wired to <see cref="RevertToConfiguredRole"/>
/// in the constructor so that revert happens automatically on QSO completion or abort.
/// </para>
///
/// <para>
/// Registered in DI as both <see cref="IQsoController"/> and <see cref="QsoControllerRouter"/>
/// so that WebApp route handlers can resolve the concrete type when they need
/// <see cref="SwitchToCallerAsync"/>.
/// </para>
/// </summary>
public sealed class QsoControllerRouter : IQsoController, IQsoRoleSwitcher
{
    private readonly QsoAnswererService           _answerer;
    private readonly QsoCallerService             _caller;
    private readonly QsoRole                      _configuredRole;
    private          QsoRole                      _activeRole;
    private readonly IConfigStore                 _configStore;
    private readonly ITxEventBus                  _txEventBus;
    private readonly ILogger<QsoControllerRouter> _logger;

    /// <summary>
    /// Initialises the router, determines the configured role from <paramref name="configStore"/>,
    /// and sets the initial <see cref="QsoAnswererService.IsActive"/> /
    /// <see cref="QsoCallerService.IsActive"/> flags.
    /// </summary>
    public QsoControllerRouter(
        QsoAnswererService           answerer,
        QsoCallerService             caller,
        IConfigStore                 configStore,
        ITxEventBus                  txEventBus,
        ILogger<QsoControllerRouter> logger)
    {
        _answerer    = answerer;
        _caller      = caller;
        _configStore = configStore;
        _txEventBus  = txEventBus;
        _logger      = logger;

        // Determine the configured role from the persisted config.
        _configuredRole = (configStore.Current.Tx?.Role ?? TxRole.Answerer) == TxRole.Caller
            ? QsoRole.Caller
            : QsoRole.Answerer;
        _activeRole = _configuredRole;

        // Enforce initial IsActive flags based on the configured role.
        // (The factory lambdas in Program.cs also set these, but set them here too
        // for safety so tests that construct the router directly get correct behaviour.)
        _answerer.IsActive = (_configuredRole == QsoRole.Answerer);
        _caller.IsActive   = (_configuredRole == QsoRole.Caller);

        // Wire the revert callback so that after any caller QSO ends, the active role
        // is automatically switched back to the configured role.
        _caller.OnBecameIdle = RevertToConfiguredRole;
    }

    // ── IQsoController delegation ─────────────────────────────────────────────

    private IQsoController ActiveController =>
        _activeRole == QsoRole.Caller ? _caller : _answerer;

    /// <inheritdoc/>
    /// <remarks>
    /// Returns the ACTIVE role (transient, may differ from the configured role during a
    /// Call CQ session) so that all HTTP status responses and WS events are consistent.
    /// The configured role is available only from the persisted config via
    /// <c>GET /api/v1/config</c> — it is not surfaced through this property.
    /// </remarks>
    public QsoRole Role => _activeRole;

    /// <inheritdoc/>
    public QsoState State => ActiveController.State;

    /// <inheritdoc/>
    public string? Partner => ActiveController.Partner;

    /// <inheritdoc/>
    public Task AbortAsync(CancellationToken ct = default)
        => ActiveController.AbortAsync(ct);

    /// <inheritdoc/>
    public Task AnswerCqAsync(
        string callsign, double frequencyHz, DateTimeOffset cqCycleStart, CancellationToken ct)
        => ActiveController.AnswerCqAsync(callsign, frequencyHz, cqCycleStart, ct);

    /// <inheritdoc/>
    public Task SelectResponderAsync(
        string callsign, double frequencyHz, DateTimeOffset responseCycleStart, CancellationToken ct)
        => ActiveController.SelectResponderAsync(callsign, frequencyHz, responseCycleStart, ct);

    // ── Router-specific ───────────────────────────────────────────────────────

    /// <summary>
    /// Switches the active role to Caller and arms <c>AutoAnswer</c>:
    /// <list type="number">
    ///   <item>If the answerer is currently active and not Idle, aborts it.</item>
    ///   <item>Deactivates the answerer (<see cref="QsoAnswererService.IsActive"/> = false)
    ///         and activates the caller (<see cref="QsoCallerService.IsActive"/> = true).</item>
    ///   <item>Saves <c>AutoAnswer = true</c> in the config store so the caller's
    ///         <c>HandleIdleAsync</c> fires on the next FT8 cycle.</item>
    /// </list>
    /// If the active role is already Caller, only step 3 is performed (idempotent).
    /// </summary>
    public async Task SwitchToCallerAsync(CancellationToken ct = default)
    {
        if (_activeRole == QsoRole.Answerer)
        {
            // Abort the answerer if a QSO is in progress.
            if (_answerer.State != QsoState.Idle)
            {
                _logger.LogInformation(
                    "QsoControllerRouter: aborting answerer before switching to caller.");
                await _answerer.AbortAsync(ct).ConfigureAwait(false);
            }

            _answerer.IsActive = false;
            _caller.IsActive   = true;
            _activeRole        = QsoRole.Caller;

            _logger.LogInformation("QsoControllerRouter: active role switched to Caller.");
        }

        // Arm AutoAnswer so the caller transmits CQ on the next batch.
        var currentTx = _configStore.Current.Tx ?? new TxConfig();
        await _configStore.SaveAsync(
            _configStore.Current with { Tx = currentTx with { AutoAnswer = true } }, ct)
            .ConfigureAwait(false);
    }

    // ── Private ───────────────────────────────────────────────────────────────

    /// <summary>
    /// Called by <see cref="QsoCallerService.OnBecameIdle"/> after a caller QSO
    /// completes or is aborted.  Reverts the active role to the configured role and
    /// publishes a synthetic <c>txState</c> WS event so connected browsers immediately
    /// update their TX panel without waiting for the next answerer batch.
    /// </summary>
    private void RevertToConfiguredRole()
    {
        if (_configuredRole == _activeRole)
            return; // already at configured role — nothing to do

        _logger.LogInformation(
            "QsoControllerRouter: caller QSO ended — reverting active role to {Role}.",
            _configuredRole);

        if (_configuredRole == QsoRole.Answerer)
        {
            _caller.IsActive   = false;
            _answerer.IsActive = true;
        }
        // (If configured role is Caller, stay as Caller — no revert needed.)

        _activeRole = _configuredRole;

        // Broadcast a synthetic txState so the frontend knows the role reverted.
        // autoAnswerEnabled: SafeAbortToIdleAsync already saved false; read current state.
        var autoAnswerEnabled = _configStore.Current.Tx?.AutoAnswer ?? false;
        _txEventBus.Publish(
            state:             "Idle",
            role:              _activeRole.ToString().ToLowerInvariant(),
            partner:           null,
            autoAnswerEnabled: autoAnswerEnabled,
            abortReason:       null);
    }
}
