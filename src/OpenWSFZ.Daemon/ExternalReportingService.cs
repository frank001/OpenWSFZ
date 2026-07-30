using System.Collections.Concurrent;
using System.Net;
using System.Net.Http;
using System.Net.Http.Json;
using System.Net.Sockets;
using System.Threading.Channels;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Logging;
using OpenWSFZ.Abstractions;
using OpenWSFZ.Web;

namespace OpenWSFZ.Daemon;

/// <summary>
/// WSJT-X-protocol UDP broadcaster and inbound command listener
/// (<c>external-reporting</c> capability, gridtracker-udp-reporting change).
///
/// <para>
/// Registered unconditionally as an <see cref="IHostedService"/> (design.md Decision 1). When
/// <see cref="AppConfig.ExternalReporting"/> is disabled or has no enabled targets, it opens no
/// sockets and does nothing — "inert by default," matching <c>CatPollingService</c>'s posture
/// when <c>cat.enabled</c> is <c>false</c>.
/// </para>
///
/// <para>
/// Outbound: Heartbeat and Status on a periodic timer (plus on-change for Status); Decode per
/// decode-batch cycle (fed by a dedicated channel, mirroring
/// <c>QsoAnswererService</c>/<c>QsoCallerService</c>'s own dedicated decode-batch channels rather
/// than design.md's originally-sketched <c>DecodeEventBus</c> subscription — <c>DecodeEventBus</c>
/// is a one-way WebSocket broadcaster with no subscriber surface, so a third dedicated bounded
/// channel is the simpler, already-precedented mechanism); QSOLogged via
/// <see cref="NotifyQsoLogged"/>, called by the <see cref="IAdifLogWriter"/> decorator that wraps
/// every ADIF-write call site; Clear and Close on graceful shutdown only — <em>not</em> per decode
/// cycle, matching real WSJT-X's own trigger for Clear (fix-external-reporting-clear-and-reply-
/// filter change; sending Clear every cycle was a protocol-conformance defect that caused
/// consumers such as GridTracker2 to discard their whole accumulated decode history every ~15s).
/// </para>
///
/// <para>
/// Inbound: a single listener bound to the first enabled target's port (WSJT-X convention: the
/// app listens on the same port it sends to). Halt Tx is always honoured; Reply/Free Text are
/// gated by <c>externalReporting.honourInboundCommands</c>; Close is logged only and never
/// terminates the daemon; any other recognised type is discarded at Debug.
/// </para>
///
/// <para>
/// <see cref="IQsoController"/> and <see cref="IExternalReplyTarget"/> are resolved lazily via
/// <see cref="IServiceProvider"/> (not taken as constructor parameters) to avoid a DI
/// construction cycle: both are ultimately implemented by <c>QsoControllerRouter</c>, which
/// depends on <c>QsoAnswererService</c>/<c>QsoCallerService</c>, which depend on
/// <see cref="IAdifLogWriter"/> — the very decorator that depends on this service.
/// </para>
///
/// <para>
/// <strong>Absolute, non-configurable exclusion (no exceptions):</strong> R&amp;R-study synthetic
/// signals (NFR-021 Q-prefix convention) and unresolved (unknown-region) callsigns SHALL NEVER
/// reach an external program via this service, regardless of the operator's
/// <c>DecodeNoiseSuppressionConfig</c> settings — that filter gates the decode panel and QSO
/// automation only and can be disabled by the operator; this is a second, unconditional, hard
/// filter inside this class itself (<see cref="IsSuppressedCallsign"/>, applied in
/// <see cref="DecodeLoopAsync"/>, <see cref="BuildStatusFields"/>, and
/// <see cref="NotifyQsoLogged"/>) so the guarantee survives regardless of upstream config and
/// cannot be turned off. See design.md's "Absolute exclusion of synthetic/unknown-region traffic"
/// decision.
/// </para>
/// </summary>
public sealed class ExternalReportingService : IHostedService, IAsyncDisposable, IExternalReportingRelayTarget
{
    /// <summary>
    /// One atomic unit of work for <see cref="DispatchLoopAsync"/>: an ordered list of already-
    /// encoded datagrams to send to every enabled target, one after another, before the next
    /// queued item begins (design.md Decision 3 — never interleaved with another source's traffic
    /// mid-dispatch). <see cref="Done"/> is completed once every datagram in this item has actually
    /// been sent, so callers that need to know delivery has happened (e.g. Clear/Close on shutdown)
    /// can await it; <c>null</c> for fire-and-forget callers.
    /// </summary>
    private readonly record struct DispatchItem(IReadOnlyList<byte[]> Datagrams, TaskCompletionSource? Done);


    private readonly ChannelReader<DecodeBatch>            _decodeChannel;
    private readonly IConfigStore                          _configStore;
    private readonly IServiceProvider                      _serviceProvider;
    private readonly ICatState?                             _catState;
    private readonly ICallsignRegionStore?                  _regionStore;
    private readonly ILogger<ExternalReportingService>      _logger;
    private readonly TimeSpan                               _heartbeatInterval;
    private readonly TimeSpan                               _statusPollInterval;

    // Lazily resolved on first use (see class remarks) — never in the constructor.
    private IQsoController?      _qsoController;
    private bool                 _qsoControllerResolved;
    private IExternalReplyTarget? _replyTarget;
    private bool                 _replyTargetResolved;

    private IQsoController? QsoController
    {
        get
        {
            if (!_qsoControllerResolved)
            {
                _qsoController         = _serviceProvider.GetService<IQsoController>();
                _qsoControllerResolved = true;
            }
            return _qsoController;
        }
    }

    private IExternalReplyTarget? ReplyTarget
    {
        get
        {
            if (!_replyTargetResolved)
            {
                _replyTarget         = _serviceProvider.GetService<IExternalReplyTarget>();
                _replyTargetResolved = true;
            }
            return _replyTarget;
        }
    }

    private readonly object _targetsLock = new();

    // Secondary targets only — index 1+ of the enabled target list. Each keeps its own
    // dedicated, outbound-only, ephemeral-port UdpClient exactly as before D-014.
    private List<(ExternalReportingTarget Target, UdpClient Client)> _outboundClients = [];

    // Primary target (index 0 of the enabled target list) — D-014 Part B. Its outbound sends go
    // through the shared _inboundClient socket (so a peer's reply-to-sender-port semantics work,
    // per design.md's "GridTracker2 replies from the same port it received on" rationale) rather
    // than a separate ephemeral client. _primaryFallbackClient is used only when _inboundClient
    // failed to bind (or isn't configured), so outbound delivery to the primary target is never
    // lost — only the source port it's sent from changes.
    private ExternalReportingTarget? _primaryTarget;
    private UdpClient?               _primaryFallbackClient;

    private UdpClient? _inboundClient;
    private int         _inboundBoundPort = -1;

    private readonly ConcurrentDictionary<string, bool> _resolutionWarned = new();

    private WsjtxDatagram.StatusFields? _lastStatus;
    private DateTimeOffset              _lastHeartbeatSentUtc = DateTimeOffset.MinValue;
    private DateTimeOffset              _lastStatusSentUtc    = DateTimeOffset.MinValue;

    /// <summary>
    /// Most recently received inbound Free Text, when <c>honourInboundCommands</c> is enabled.
    /// Accepted and stored per the "Inbound Free Text gated and currently a no-op" requirement —
    /// no OpenWSFZ TX state machine has a free-message slot to apply it to yet (see design.md).
    /// </summary>
    internal string? LastFreeText { get; private set; }

    private CancellationTokenSource? _cts;
    private Task? _decodeLoopTask;
    private Task? _timerLoopTask;
    private Task? _inboundLoopTask;
    private Task? _dispatchLoopTask;

    // ── external-reporting-single-connection: leader/follower relay state ──────
    //
    // Single-consumer dispatch queue (design.md Decision 3): both this instance's own outbound
    // sends (when acting as leader) and every relay batch accepted from a follower
    // (EnqueueRelayBatch) funnel through this one channel, drained solely by DispatchLoopAsync, so
    // no batch is ever interleaved with another mid-dispatch.
    private readonly Channel<DispatchItem> _dispatchChannel = Channel.CreateUnbounded<DispatchItem>();

    // Set true the moment a follower's relay attempt fails (connect error, timeout, non-2xx) and
    // cleared on the next successful relay (Decision 4). While true, Reconcile opens real sockets
    // to `targets` — "degrades to exactly leader-role behaviour" — so SendToAllEnabledAsync has
    // something to send to for the direct-send fallback.
    private volatile bool _followerDegraded;

    // Most recently observed decode batch, tracked regardless of role/active state, purely so a
    // leader's inbound Reply handler can diagnose "not in my own decode batch" (task 5.1) distinctly
    // from "no callsign could be extracted".
    private volatile DecodeBatch? _lastDecodeBatch;

    // Shared HttpClient for both the follower→leader relay POST and the leader→follower Halt-Tx
    // broadcast — both are loopback/LAN calls between co-located daemon instances, not WAN calls,
    // hence the short sub-second timeout (task 2.3).
    private readonly HttpClient _relayHttpClient;

    /// <summary>Production constructor — all dependencies from DI.</summary>
    public ExternalReportingService(
        ChannelReader<DecodeBatch>       decodeChannel,
        IConfigStore                     configStore,
        IServiceProvider                 serviceProvider,
        ILogger<ExternalReportingService> logger,
        ICatState?                        catState = null,
        ICallsignRegionStore?             regionStore = null)
        : this(decodeChannel, configStore, serviceProvider, logger, catState, regionStore,
               heartbeatInterval: TimeSpan.FromSeconds(15),
               statusPollInterval: TimeSpan.FromSeconds(1))
    {
    }

    /// <summary>
    /// Test constructor — allows overriding the timer cadences to avoid multi-second waits, and
    /// (external-reporting-single-connection) injecting a fake <see cref="HttpMessageHandler"/> for
    /// the follower→leader relay POST / leader→follower Halt-Tx broadcast without live network
    /// access.
    /// </summary>
    internal ExternalReportingService(
        ChannelReader<DecodeBatch>       decodeChannel,
        IConfigStore                     configStore,
        IServiceProvider                 serviceProvider,
        ILogger<ExternalReportingService> logger,
        ICatState?                        catState,
        ICallsignRegionStore?             regionStore,
        TimeSpan                          heartbeatInterval,
        TimeSpan                          statusPollInterval,
        HttpClient?                       relayHttpClient = null)
    {
        _decodeChannel      = decodeChannel;
        _configStore        = configStore;
        _serviceProvider    = serviceProvider;
        _logger             = logger;
        _catState           = catState;
        _regionStore        = regionStore;
        _heartbeatInterval  = heartbeatInterval;
        _statusPollInterval = statusPollInterval;
        _relayHttpClient    = relayHttpClient ?? new HttpClient { Timeout = TimeSpan.FromMilliseconds(800) };
    }

    /// <summary>
    /// Absolute, non-configurable exclusion gate (Captain's directive, no exceptions — see
    /// design.md's "Absolute exclusion of synthetic/unknown-region traffic" decision): returns
    /// <c>true</c> when <paramref name="callsign"/> resolves to an R&amp;R-study synthetic entry
    /// or cannot be resolved at all. A <c>null</c> <see cref="_regionStore"/> (not wired up) is
    /// treated the same as an unresolved callsign — deliberately fails <em>closed</em> (suppress),
    /// not open, unlike most other optional-dependency null-checks in this codebase: this is a
    /// data-integrity floor, not a convenience feature, and "cannot verify" must never be treated
    /// as "verified real."
    /// </summary>
    private bool IsSuppressedCallsign(string? callsign)
    {
        if (string.IsNullOrWhiteSpace(callsign)) return false; // nothing to suppress

        var token = callsign.Trim();
        var slashPos = token.IndexOf('/');
        if (slashPos >= 0) token = token[..slashPos]; // strip portable suffix (/P, /M, ...)

        var region = _regionStore?.TryGetRegion(token);
        return region is null || region.Synthetic;
    }

    // ── IHostedService ────────────────────────────────────────────────────────

    /// <inheritdoc/>
    public Task StartAsync(CancellationToken cancellationToken)
    {
        _cts = new CancellationTokenSource();
        // Capture the token in a local now — the three Task.Run lambdas below close over this
        // local, not the mutable _cts field, so a concurrent StopAsync nulling out _cts (via
        // Interlocked.Exchange) before the thread pool actually starts running a queued lambda
        // can never throw a NullReferenceException reading _cts.Token from inside that lambda.
        var token = _cts.Token;
        Reconcile(_configStore.Current.ExternalReporting);
        _configStore.OnSaved += OnConfigSaved;

        _decodeLoopTask   = Task.Run(() => DecodeLoopAsync(token), CancellationToken.None);
        _timerLoopTask    = Task.Run(() => TimerLoopAsync(token), CancellationToken.None);
        _inboundLoopTask  = Task.Run(() => InboundLoopAsync(token), CancellationToken.None);
        _dispatchLoopTask = Task.Run(() => DispatchLoopAsync(token), CancellationToken.None);
        return Task.CompletedTask;
    }

    /// <inheritdoc/>
    public async Task StopAsync(CancellationToken cancellationToken)
    {
        _configStore.OnSaved -= OnConfigSaved;

        var cts = Interlocked.Exchange(ref _cts, null);
        if (cts is null) return;

        // Send Clear, then Close, to every enabled target before closing sockets — matching
        // WSJT-X's own "Clear sent on graceful shutdown" trigger (design.md Decision 1; fix-
        // external-reporting-clear-and-reply-filter task 1.2). Clear is deliberately sent first so
        // a consumer's "history discarded" bookkeeping is updated before the connection-teardown
        // signal. Each call now routes through DispatchOrRelayAsync (leader: the single-consumer
        // dispatch queue, awaited to actual-send completion; follower: relay-or-degrade), so
        // DispatchLoopAsync must still be running when these are awaited — hence completing the
        // channel writer and cancelling `cts` only afterwards, below.
        await SendClearToAllAsync().ConfigureAwait(false);
        await SendCloseToAllAsync().ConfigureAwait(false);

        _dispatchChannel.Writer.TryComplete();

        await cts.CancelAsync().ConfigureAwait(false);

        var tasks = new[] { _decodeLoopTask, _timerLoopTask, _inboundLoopTask, _dispatchLoopTask }
            .Where(t => t is not null).Select(t => t!).ToArray();
        try
        {
            await Task.WhenAll(tasks).WaitAsync(TimeSpan.FromSeconds(3), CancellationToken.None)
                      .ConfigureAwait(false);
        }
        catch (TimeoutException) { /* acceptable on shutdown */ }
        catch (OperationCanceledException) { /* expected */ }

        CloseAllSockets();
        cts.Dispose();
    }

    // ── IAsyncDisposable ─────────────────────────────────────────────────────

    /// <inheritdoc/>
    public async ValueTask DisposeAsync()
    {
        await StopAsync(CancellationToken.None).ConfigureAwait(false);
    }

    // ── Config reconciliation (task 3.2) ────────────────────────────────────

    private void OnConfigSaved(AppConfig config) => Reconcile(config.ExternalReporting);

    /// <summary>
    /// Opens outbound <see cref="UdpClient"/>s for newly-enabled secondary targets, closes ones
    /// for targets no longer enabled/present, and (re)binds the single inbound listener to the
    /// primary (index 0) enabled target's port — all without a daemon restart.
    /// </summary>
    /// <param name="config">
    /// May be <c>null</c> in principle: <c>System.Text.Json</c> source-generation initialises a
    /// non-nullable init property to <c>null</c> (bypassing its C# property initialiser) when the
    /// corresponding JSON key is absent, the same quirk documented throughout
    /// <c>JsonConfigStore.Load</c> for <c>Logging</c>/<c>DecodeLog</c>/<c>RemoteAccess</c>/
    /// <c>DecodeNoiseSuppression</c>. <c>WebApp</c>'s <c>POST /api/v1/config</c> guards against
    /// this before saving, but this defensive coalesce keeps <c>Reconcile</c> correct for any
    /// caller that does not.
    /// </param>
    private void Reconcile(ExternalReportingConfig? config)
    {
        config ??= new ExternalReportingConfig();

        // external-reporting-single-connection: a "follower" opens no outbound/inbound socket to
        // its own targets at all in steady state (Requirement: "Follower role relays instead of
        // sending directly") — every datagram goes to leaderUrl instead. Only once a relay attempt
        // has actually failed and this instance has degraded (Decision 4) does it need real
        // sockets, at which point it "degrades to exactly leader-role behaviour", sockets included,
        // so RelayToLeaderAsync's direct-send fallback (SendToAllEnabledAsync) has something to
        // send to. A "leader" is unaffected — always wants sockets exactly as before this change.
        var isFollower    = string.Equals(config.Role, "follower", StringComparison.Ordinal);
        var socketsWanted = !isFollower || _followerDegraded;

        lock (_targetsLock)
        {
            var desiredEnabled = (config.Enabled && socketsWanted)
                ? config.Targets.Where(t => t.Enabled).ToList()
                : [];

            var newPrimary       = desiredEnabled.Count > 0 ? desiredEnabled[0] : null;
            var secondaryTargets = desiredEnabled.Count > 1 ? desiredEnabled.Skip(1).ToList() : [];

            // ── Secondary targets (index 1+): each keeps its own dedicated ephemeral client ──
            var toClose = _outboundClients.Where(c => !secondaryTargets.Contains(c.Target)).ToList();
            foreach (var c in toClose)
            {
                _outboundClients.Remove(c);
                try { c.Client.Dispose(); } catch { /* best-effort */ }
            }

            foreach (var target in secondaryTargets)
            {
                if (_outboundClients.Any(c => c.Target.Equals(target))) continue;
                try
                {
                    _outboundClients.Add((target, new UdpClient()));
                }
                catch (Exception ex)
                {
                    _logger.LogWarning(ex,
                        "external-reporting: failed to open outbound socket for target '{Name}'.",
                        target.Name);
                }
            }

            // ── Primary target (index 0): drop the stale fallback client on any target change —
            //    re-evaluated below against the (possibly newly re-bound) inbound socket. ──
            if (!Equals(_primaryTarget, newPrimary))
            {
                _primaryTarget = newPrimary;
                _primaryFallbackClient?.Dispose();
                _primaryFallbackClient = null;
            }

            // ── Inbound listener: bind to the primary target's port with ReuseAddress so it
            //    coexists with a peer (e.g. GridTracker2, which itself binds with Qt's
            //    ShareAddress|ReuseAddressHint) already bound there (D-014 Part A). Without this,
            //    the bind throws whenever the operator's mapping tool is already running — the
            //    normal real-world case — and Halt Tx/Reply/Free Text become silently
            //    unreachable. ──
            var desiredInboundPort = newPrimary?.Port ?? -1;
            if (desiredInboundPort != _inboundBoundPort)
            {
                _inboundClient?.Dispose();
                _inboundClient    = null;
                _inboundBoundPort = -1;

                if (desiredInboundPort > 0)
                {
                    try
                    {
                        var client = new UdpClient(AddressFamily.InterNetwork);
                        client.Client.SetSocketOption(
                            SocketOptionLevel.Socket, SocketOptionName.ReuseAddress, true);
                        client.Client.Bind(new IPEndPoint(IPAddress.Any, desiredInboundPort));
                        _inboundClient    = client;
                        _inboundBoundPort = desiredInboundPort;
                    }
                    catch (Exception ex)
                    {
                        _logger.LogWarning(ex,
                            "external-reporting: failed to bind inbound listener on port {Port} — " +
                            "Halt Tx/Reply/Free Text will be unreachable until this is resolved; " +
                            "outbound delivery to the primary target continues via a fallback socket.",
                            desiredInboundPort);
                    }
                }
            }

            // ── D-014 Part B: outbound sends to the primary target go through the shared bound
            //    _inboundClient socket, so a peer's reply-to-sender-port semantics reach our
            //    inbound listener. Only fall back to a dedicated ephemeral outbound-only client
            //    when the shared bind is unavailable, so outbound delivery is never lost — only
            //    the source port it's sent from changes. ──
            if (newPrimary is not null && _inboundClient is null && _primaryFallbackClient is null)
            {
                try
                {
                    _primaryFallbackClient = new UdpClient();
                }
                catch (Exception ex)
                {
                    _logger.LogWarning(ex,
                        "external-reporting: failed to open fallback outbound socket for primary target '{Name}'.",
                        newPrimary.Name);
                }
            }
            else if ((newPrimary is null || _inboundClient is not null) && _primaryFallbackClient is not null)
            {
                _primaryFallbackClient.Dispose();
                _primaryFallbackClient = null;
            }
        }
    }

    private bool IsOutboundActive
    {
        get { lock (_targetsLock) return _outboundClients.Count > 0 || _primaryTarget is not null; }
    }

    /// <summary>
    /// external-reporting-single-connection: role-aware replacement for the pre-existing
    /// <see cref="IsOutboundActive"/> gate used by every outbound call site. For a
    /// <c>"leader"</c> (the default), this is extensionally identical to <see cref="IsOutboundActive"/>
    /// in every case (byte-for-byte requirement preserved: Reconcile already forces
    /// <see cref="IsOutboundActive"/> to <c>false</c> whenever <c>Enabled</c> is <c>false</c>, so the
    /// explicit <c>Enabled</c> check below never changes a leader's observed gating). For a
    /// <c>"follower"</c>, "active" means simply <c>Enabled</c> — a follower has no sockets to be
    /// "outbound active" via in steady state, but is still fully expected to build and relay
    /// datagrams.
    /// </summary>
    private bool IsReportingActive
    {
        get
        {
            var config = _configStore.Current.ExternalReporting;
            if (!config.Enabled) return false;
            return string.Equals(config.Role, "follower", StringComparison.Ordinal) || IsOutboundActive;
        }
    }

    // ── Outbound: decode-batch-driven Clear + Decode (tasks 3.3–3.4) ────────

    private async Task DecodeLoopAsync(CancellationToken ct)
    {
        try
        {
            await foreach (var batch in _decodeChannel.ReadAllAsync(ct).ConfigureAwait(false))
            {
                // external-reporting-single-connection (task 5.1): tracked unconditionally, before
                // the active-gate below, so a leader's inbound Reply handler can always diagnose
                // "not in my own current decode batch" — independent of whether this specific batch
                // happened to be reportable.
                _lastDecodeBatch = batch;

                if (!IsReportingActive) continue;

                var config     = _configStore.Current.ExternalReporting;
                var instanceId = config.InstanceId;
                var isFollower = string.Equals(config.Role, "follower", StringComparison.Ordinal);

                // external-reporting-single-connection (task 2.2): a follower groups one decode
                // cycle's Status (if changed/due) immediately followed by its Decode datagrams into
                // a single relay batch/POST (design.md Decision 3's ordering requirement), instead
                // of relaying one datagram per POST. A leader's own Status stays on TimerLoopAsync's
                // pre-existing independent 1s-polled cadence, completely unchanged — see the
                // "Leader with no followers is unchanged from today's behaviour" requirement.
                List<(string Type, byte[] Bytes)>? followerBatch = isFollower ? [] : null;

                if (isFollower)
                {
                    var status  = BuildStatusFields();
                    var changed = _lastStatus is null || !_lastStatus.Value.Equals(status);
                    var due     = DateTimeOffset.UtcNow - _lastStatusSentUtc >= _heartbeatInterval;
                    if (changed || due)
                    {
                        _lastStatus        = status;
                        _lastStatusSentUtc = DateTimeOffset.UtcNow;
                        followerBatch!.Add(("Status", WsjtxDatagram.EncodeStatus(instanceId, status)));
                    }
                }

                foreach (var r in batch.Results)
                {
                    // Absolute guarantee (Captain's directive, no exceptions) — NOT gated by
                    // DecodeNoiseSuppressionConfig, NOT configurable, NOT an opt-out via any
                    // Settings-page control. R&R-synthetic and unknown-region decodes SHALL NEVER
                    // be broadcast to any external program, regardless of what the operator has
                    // chosen for the decode panel or the QSO controllers upstream — this is a
                    // second, unconditional filter inside the class that actually emits UDP
                    // traffic, independent of DecodeNoiseSuppressionFilter's own operator-toggleable
                    // gate on the shared decode-pump channel (which this service's inbound batches
                    // have already passed through and could, if the operator has disabled both
                    // suppression settings, still contain unknown-region/synthetic entries). Applies
                    // identically before a datagram is ever handed to the relay path (follower) —
                    // this absolute exclusion runs before either branch below.
                    if (r.Region is null || r.Region.Synthetic)
                    {
                        _logger.LogDebug(
                            "external-reporting: suppressed outbound Decode for '{Message}' — {Reason}.",
                            r.Message, r.Region is null ? "unknown region" : "synthetic (R&R study)");
                        continue;
                    }

                    var fields = new WsjtxDatagram.DecodeFields(
                        New:                    true,
                        TimeMsSinceMidnightUtc: ParseTimeToMs(r.Time),
                        SnrDb:                  r.Snr,
                        DeltaTimeSeconds:       r.Dt,
                        DeltaFrequencyHz:       (uint)Math.Max(0, r.FreqHz),
                        Mode:                   "~",
                        Message:                r.Message,
                        LowConfidence:          false);
                    var decodeBytes = WsjtxDatagram.EncodeDecode(instanceId, fields);

                    if (isFollower)
                        followerBatch!.Add(("Decode", decodeBytes));
                    else
                        await DispatchAsync([decodeBytes]).ConfigureAwait(false);
                }

                if (isFollower && followerBatch!.Count > 0)
                    await RelayToLeaderAsync(followerBatch).ConfigureAwait(false);
            }
        }
        catch (OperationCanceledException) { /* shutdown */ }
    }

    private static uint ParseTimeToMs(string time)
        => TimeSpan.TryParseExact(time, @"hh\:mm\:ss", null, out var ts)
            ? (uint)ts.TotalMilliseconds
            : 0;

    // ── Outbound: Heartbeat + Status timer (task 3.3) ───────────────────────

    private async Task TimerLoopAsync(CancellationToken ct)
    {
        while (!ct.IsCancellationRequested)
        {
            if (IsReportingActive)
            {
                var config     = _configStore.Current.ExternalReporting;
                var isFollower = string.Equals(config.Role, "follower", StringComparison.Ordinal);
                var now        = DateTimeOffset.UtcNow;

                if (now - _lastHeartbeatSentUtc >= _heartbeatInterval)
                {
                    _lastHeartbeatSentUtc = now;
                    var heartbeatBytes = WsjtxDatagram.EncodeHeartbeat(
                        config.InstanceId, 3, AssemblyVersion.Get(), "");
                    // Heartbeat/QSOLogged/Clear/Close each relay as their own single-datagram batch
                    // (task 2.2) — only Status+Decode are grouped, in DecodeLoopAsync, per cycle.
                    await DispatchOrRelayAsync("Heartbeat", heartbeatBytes).ConfigureAwait(false);
                }

                // Requirement "Leader role preserves existing direct-send behaviour": Status stays
                // on this pre-existing, independent 1s-polled cadence for a leader, completely
                // unchanged (same fields, same change-or-due check, same _lastStatus/_lastStatusSentUtc
                // bookkeeping). A follower's Status is instead built and grouped with its Decode
                // datagrams once per decode cycle (task 2.2, DecodeLoopAsync) so a relayed batch's
                // Status-then-Decode ordering can never be split across the relay hop — see
                // design.md Decision 3.
                if (!isFollower)
                {
                    var status  = BuildStatusFields();
                    var changed = _lastStatus is null || !_lastStatus.Value.Equals(status);
                    if (changed || now - _lastStatusSentUtc >= _heartbeatInterval)
                    {
                        _lastStatus        = status;
                        _lastStatusSentUtc = now;
                        await DispatchAsync([WsjtxDatagram.EncodeStatus(config.InstanceId, status)])
                            .ConfigureAwait(false);
                    }
                }
            }

            try
            {
                await Task.Delay(_statusPollInterval, ct).ConfigureAwait(false);
            }
            catch (OperationCanceledException) { break; }
        }
    }

    private WsjtxDatagram.StatusFields BuildStatusFields()
    {
        var config = _configStore.Current;
        var tx     = config.Tx ?? new TxConfig();

        var dialFreqMHz = WebApp.ResolveEffectiveFrequency(_catState, config);
        var dialFreqHz  = (ulong)Math.Max(0, Math.Round(dialFreqMHz * 1_000_000.0));

        var qso     = QsoController;
        var partner = qso?.Partner ?? "";
        var keying  = qso?.Keying ?? false;

        // Absolute guarantee, Tier 2 (no exceptions): an active QSO with a synthetic or
        // unresolved partner must never name that callsign to an external program in real time.
        // Only DxCall/DxGrid are withheld — the rest of Status (frequency, TX/RX state,
        // decoding-enabled) must keep flowing normally; its own "at least once per heartbeat
        // interval" requirement is independent of who (if anyone) we're currently working.
        if (IsSuppressedCallsign(partner))
        {
            _logger.LogDebug(
                "external-reporting: suppressed DxCall/DxGrid in outbound Status for synthetic/unknown-region partner '{Partner}'.",
                partner);
            partner = "";
        }

        return new WsjtxDatagram.StatusFields(
            DialFrequencyHz: dialFreqHz,
            Mode:            "FT8",
            DxCall:          partner,
            Report:          "",
            TxMode:          "FT8",
            TxEnabled:       tx.AutoAnswer,
            Transmitting:    keying,
            Decoding:        config.DecodingEnabled,
            RxDeltaFreqHz:   (uint)Math.Max(0, tx.RxAudioOffsetHz),
            TxDeltaFreqHz:   (uint)Math.Max(0, tx.TxAudioOffsetHz),
            MyCall:          tx.Callsign,
            MyGrid:          tx.Grid,
            // DX grid: not exposed via IQsoController today — left blank (best-effort; the
            // requirement allows "when known from the decode").
            DxGrid:          "");
    }

    // ── Outbound: QSOLogged (task 3.5) ──────────────────────────────────────

    /// <summary>
    /// Called by the <see cref="IAdifLogWriter"/> decorator immediately after a successful ADIF
    /// write, from every call site (<c>QsoAnswererService</c>/<c>QsoCallerService</c>'s direct
    /// write when <c>tx.qsoConfirmation=false</c>, and <c>POST /api/v1/tx/log-qso</c> when
    /// <c>tx.qsoConfirmation=true</c>, the default). A QSO aborted by watchdog or operator never
    /// reaches an ADIF write at all, so it correctly never reaches here either (mirrors FR-051's
    /// own "no record on abort" rule).
    /// </summary>
    internal void NotifyQsoLogged(QsoRecord record)
    {
        if (!IsReportingActive) return;

        // Absolute guarantee, Tier 2 (no exceptions): a completed QSO with a synthetic or
        // unresolved partner must never be reported to an external program as a real logged
        // contact — mirrors the existing early-return-on-abort pattern immediately above.
        if (IsSuppressedCallsign(record.PartnerCallsign))
        {
            _logger.LogInformation(
                "external-reporting: suppressed outbound QSOLogged for synthetic/unknown-region partner '{Partner}'.",
                record.PartnerCallsign);
            return;
        }

        var fields = new WsjtxDatagram.QsoLoggedFields(
            QsoStartUtc:    new DateTimeOffset(DateTime.SpecifyKind(record.QsoStartUtc, DateTimeKind.Utc)),
            QsoEndUtc:      new DateTimeOffset(DateTime.SpecifyKind(record.QsoEndUtc, DateTimeKind.Utc)),
            DxCall:         record.PartnerCallsign,
            DxGrid:         record.PartnerGrid ?? "",
            TxFrequencyHz:  (ulong)Math.Max(0, Math.Round(record.DialFrequencyMHz * 1_000_000.0)),
            Mode:           "FT8",
            ReportSent:     record.RstSent,
            ReportReceived: record.RstRcvd,
            MyCall:         record.OperatorCallsign,
            MyGrid:         record.OperatorGrid);

        var qsoLoggedBytes = WsjtxDatagram.EncodeQsoLogged(
            _configStore.Current.ExternalReporting.InstanceId, fields);
        _ = DispatchOrRelayAsync("QsoLogged", qsoLoggedBytes);
    }

    // ── Outbound send + Close-on-shutdown (task 3.6) ────────────────────────

    private async Task SendToAllEnabledAsync(byte[] datagram)
    {
        List<(ExternalReportingTarget Target, UdpClient Client)> clients;
        lock (_targetsLock)
        {
            clients = [.. _outboundClients];

            // D-014 Part B: the primary target sends through the shared inbound socket when
            // bound, falling back to the dedicated ephemeral client otherwise.
            if (_primaryTarget is { } primary)
            {
                var primaryClient = _inboundClient ?? _primaryFallbackClient;
                if (primaryClient is not null)
                    clients.Add((primary, primaryClient));
            }
        }

        foreach (var (target, client) in clients)
        {
            try
            {
                await client.SendAsync(datagram, datagram.Length, target.Host, target.Port)
                            .ConfigureAwait(false);
                _resolutionWarned.TryRemove(TargetKey(target), out _);
            }
            catch (Exception ex) when (ex is SocketException or ArgumentException or ObjectDisposedException)
            {
                // ObjectDisposedException: the shared _inboundClient can be disposed and
                // rebound concurrently by Reconcile (D-014 Part B) — treat exactly like any
                // other per-target send failure; the next tick resolves the current socket fresh.
                if (_resolutionWarned.TryAdd(TargetKey(target), true))
                {
                    _logger.LogWarning(ex,
                        "external-reporting: failed to resolve/send to target '{Name}' ({Host}:{Port}) — " +
                        "other targets are unaffected; will keep retrying silently.",
                        target.Name, target.Host, target.Port);
                }
            }
        }
    }

    private static string TargetKey(ExternalReportingTarget t) => $"{t.Name}|{t.Host}|{t.Port}";

    /// <summary>
    /// Sends a Clear datagram to every enabled target — invoked only on graceful shutdown
    /// (<see cref="StopAsync"/>), matching real WSJT-X's own "Clear on shutdown" trigger. The
    /// per-decode-cycle Clear send this class previously performed was a protocol-conformance
    /// defect (it caused consumers such as GridTracker2 to discard their entire accumulated
    /// decode history every ~15 seconds) and has been removed from <see cref="DecodeLoopAsync"/>
    /// entirely — see design.md Decision 1.
    /// </summary>
    private async Task SendClearToAllAsync()
    {
        if (!IsReportingActive) return;
        try
        {
            await DispatchOrRelayAsync(
                "Clear", WsjtxDatagram.EncodeClear(_configStore.Current.ExternalReporting.InstanceId))
                .ConfigureAwait(false);
        }
        catch { /* best-effort on shutdown */ }
    }

    private async Task SendCloseToAllAsync()
    {
        if (!IsReportingActive) return;
        try
        {
            await DispatchOrRelayAsync(
                "Close", WsjtxDatagram.EncodeClose(_configStore.Current.ExternalReporting.InstanceId))
                .ConfigureAwait(false);
        }
        catch { /* best-effort on shutdown */ }
    }

    // ── Single-consumer dispatch queue (external-reporting-single-connection, task 3.2) ─────

    /// <summary>
    /// Enqueues one atomic, ordered batch of already-encoded datagrams onto
    /// <see cref="_dispatchChannel"/>, returning a <see cref="Task"/> that completes once
    /// <see cref="DispatchLoopAsync"/> has actually sent every datagram in <paramref name="datagrams"/>
    /// to every enabled target. Used for this instance's own outbound sends when acting as leader;
    /// <see cref="EnqueueRelayBatch"/> uses the fire-and-forget form for a follower's relayed batch.
    /// </summary>
    private Task DispatchAsync(IReadOnlyList<byte[]> datagrams)
    {
        var tcs = new TaskCompletionSource(TaskCreationOptions.RunContinuationsAsynchronously);
        if (!_dispatchChannel.Writer.TryWrite(new DispatchItem(datagrams, tcs)))
            tcs.TrySetResult(); // writer already completed (shutting down) — nothing left to send
        return tcs.Task;
    }

    /// <summary>
    /// Drains <see cref="_dispatchChannel"/> one <see cref="DispatchItem"/> at a time, sending
    /// every datagram in an item to every enabled target, in order, before beginning the next
    /// queued item — whether that item is this leader's own traffic or a follower's relayed batch
    /// (design.md Decision 3: no batch is ever interleaved with another mid-dispatch). This is the
    /// sole remaining call site of <see cref="SendToAllEnabledAsync"/> for the leader path
    /// (<see cref="DegradeAndSendDirectAsync"/> is the only other one, used by a degraded follower).
    /// </summary>
    private async Task DispatchLoopAsync(CancellationToken ct)
    {
        try
        {
            await foreach (var item in _dispatchChannel.Reader.ReadAllAsync(ct).ConfigureAwait(false))
            {
                foreach (var datagram in item.Datagrams)
                    await SendToAllEnabledAsync(datagram).ConfigureAwait(false);
                item.Done?.TrySetResult();
            }
        }
        catch (OperationCanceledException) { /* shutdown */ }
    }

    /// <summary>
    /// Routes one already-encoded datagram to this instance's outbound path, branching on
    /// <c>externalReporting.role</c> (task 2.1): <c>"leader"</c> enqueues it onto the single-
    /// consumer dispatch queue (unchanged wire behaviour, just serialised through one more hop);
    /// <c>"follower"</c> relays it to <c>leaderUrl</c> (or degrades to direct send — Decision 4).
    /// </summary>
    private Task DispatchOrRelayAsync(string type, byte[] datagram)
        => string.Equals(_configStore.Current.ExternalReporting.Role, "follower", StringComparison.Ordinal)
            ? RelayToLeaderAsync([(type, datagram)])
            : DispatchAsync([datagram]);

    // ── Follower-side relay send path (external-reporting-single-connection, tasks 2.3–2.4) ──

    /// <summary>
    /// Relays an ordered batch of already-encoded datagrams to <c>externalReporting.leaderUrl</c>
    /// via <c>POST /api/v1/external-reporting/relay</c>. On any failure (missing/malformed
    /// <c>leaderUrl</c>, connect error, timeout, non-2xx response) degrades to sending the same
    /// batch directly to this instance's own <c>targets</c>, under its own <c>instanceId</c>
    /// (Decision 4) — reuses <see cref="SendToAllEnabledAsync"/>, the exact same path a
    /// <c>"leader"</c> instance's own traffic goes through via <see cref="DispatchLoopAsync"/>.
    /// </summary>
    private async Task RelayToLeaderAsync(IReadOnlyList<(string Type, byte[] Bytes)> batch)
    {
        if (batch.Count == 0) return;

        var config    = _configStore.Current.ExternalReporting;
        var leaderUrl = config.LeaderUrl;

        if (string.IsNullOrWhiteSpace(leaderUrl))
        {
            await DegradeAndSendDirectAsync(batch, "leaderUrl is not configured", exception: null)
                .ConfigureAwait(false);
            return;
        }

        try
        {
            var payload = new RelayBatchRequest(
                config.InstanceId,
                batch.Select(b => new RelayDatagramDto(b.Type, Convert.ToBase64String(b.Bytes))).ToList());

            using var content  = JsonContent.Create(payload, AppJsonContext.Default.RelayBatchRequest);
            var       relayUri = $"{leaderUrl.TrimEnd('/')}/api/v1/external-reporting/relay";
            using var response = await _relayHttpClient.PostAsync(relayUri, content).ConfigureAwait(false);

            if (!response.IsSuccessStatusCode)
                throw new HttpRequestException($"leader responded HTTP {(int)response.StatusCode}");

            // Requirement "Follower resumes relaying once its leader becomes reachable again":
            // automatic, on the very next successful relay attempt — no restart or manual action.
            if (_followerDegraded)
                _logger.LogInformation(
                    "external-reporting: leader at '{LeaderUrl}' reachable again — resuming relay.",
                    leaderUrl);
            SetFollowerDegraded(false);
        }
        catch (Exception ex) when (ex is HttpRequestException or OperationCanceledException)
        {
            // OperationCanceledException here can only originate from _relayHttpClient's own
            // Timeout (surfaced as TaskCanceledException, a subclass) — this method is never passed
            // the service's own shutdown token, so a real shutdown cancellation can never be
            // mistaken for a relay failure here.
            await DegradeAndSendDirectAsync(batch, ex.Message, ex).ConfigureAwait(false);
        }
    }

    /// <summary>
    /// Decision 4's degrade fallback: logs a Warning at most once per leader-unreachable state
    /// (mirrors <see cref="_resolutionWarned"/>'s once-per-failure-state pattern above), then sends
    /// the batch directly via <see cref="SendToAllEnabledAsync"/> — the follower behaves "exactly
    /// like leader role" for the duration the leader stays unreachable.
    /// </summary>
    private async Task DegradeAndSendDirectAsync(
        IReadOnlyList<(string Type, byte[] Bytes)> batch, string reason, Exception? exception)
    {
        var alreadyDegraded = _followerDegraded;
        SetFollowerDegraded(true);

        if (!alreadyDegraded)
        {
            _logger.LogWarning(exception,
                "external-reporting: relay to leader failed ({Reason}) — degrading to direct send " +
                "under this instance's own instanceId until the leader becomes reachable again.",
                reason);
        }

        foreach (var (_, bytes) in batch)
            await SendToAllEnabledAsync(bytes).ConfigureAwait(false);
    }

    /// <summary>
    /// Flips <see cref="_followerDegraded"/> and re-runs <see cref="Reconcile"/> so the socket
    /// machinery (open on degrade, closed again on reconciliation) tracks the transition
    /// immediately, without waiting for the next unrelated config change.
    /// </summary>
    private void SetFollowerDegraded(bool degraded)
    {
        if (_followerDegraded == degraded) return;
        _followerDegraded = degraded;
        Reconcile(_configStore.Current.ExternalReporting);
    }

    // ── IExternalReportingRelayTarget (external-reporting-single-connection, task 3.1) ───────

    /// <inheritdoc/>
    public bool CanAcceptRelay
    {
        get
        {
            var config = _configStore.Current.ExternalReporting;
            return config.Enabled && string.Equals(config.Role, "leader", StringComparison.Ordinal);
        }
    }

    /// <inheritdoc/>
    public void EnqueueRelayBatch(string followerInstanceId, IReadOnlyList<byte[]> datagrams)
    {
        if (datagrams.Count == 0) return;

        _logger.LogDebug(
            "external-reporting: enqueuing a {Count}-datagram relay batch from follower '{FollowerInstanceId}'.",
            datagrams.Count, followerInstanceId);

        // Fire-and-forget: the HTTP handler that called this should not block waiting for the
        // actual UDP send(s) to complete — "enqueue", not "deliver synchronously" (interface
        // contract). Ordering/no-interleaving is still guaranteed by the single-consumer channel.
        _ = DispatchAsync(datagrams);
    }

    private void CloseAllSockets()
    {
        lock (_targetsLock)
        {
            foreach (var (_, client) in _outboundClients)
                try { client.Dispose(); } catch { /* best-effort */ }
            _outboundClients.Clear();

            _primaryTarget = null;
            _primaryFallbackClient?.Dispose();
            _primaryFallbackClient = null;

            _inboundClient?.Dispose();
            _inboundClient    = null;
            _inboundBoundPort = -1;
        }
    }

    // ── Inbound listener (task 4) ────────────────────────────────────────────

    private async Task InboundLoopAsync(CancellationToken ct)
    {
        while (!ct.IsCancellationRequested)
        {
            UdpClient? client;
            lock (_targetsLock) client = _inboundClient;

            if (client is null)
            {
                try { await Task.Delay(250, ct).ConfigureAwait(false); }
                catch (OperationCanceledException) { break; }
                continue;
            }

            UdpReceiveResult result;
            try
            {
                result = await client.ReceiveAsync(ct).ConfigureAwait(false);
            }
            catch (OperationCanceledException) when (ct.IsCancellationRequested)
            {
                break;
            }
            catch (ObjectDisposedException)
            {
                continue; // rebound/closed concurrently by Reconcile — pick up the new client
            }
            catch (SocketException ex)
            {
                _logger.LogDebug(ex, "external-reporting: inbound socket error — continuing.");
                continue;
            }

            HandleInboundDatagram(result.Buffer);
        }
    }

    /// <summary>
    /// Dispatches a single decoded inbound datagram. Never throws: <see cref="WsjtxDatagram.TryDecode"/>
    /// already guarantees malformed input becomes a discarded datagram, not an exception
    /// (task 4.1/2.4), and every handler below is itself exception-safe.
    /// </summary>
    private void HandleInboundDatagram(byte[] buffer)
    {
        if (!WsjtxDatagram.TryDecode(buffer, out var message) || message is null)
        {
            _logger.LogDebug("external-reporting: discarded a malformed inbound datagram.");
            return;
        }

        switch (message)
        {
            case WsjtxDatagram.InboundMessage.HaltTxMessage:
                // Halt Tx is ALWAYS honoured — never gated by honourInboundCommands (task 4.2).
                _logger.LogInformation(
                    "external-reporting: Halt Tx received — aborting any in-progress transmission.");
                _ = HandleHaltTxAsync();
                break;

            case WsjtxDatagram.InboundMessage.ReplyMessage reply:
                HandleReply(reply);
                break;

            case WsjtxDatagram.InboundMessage.FreeTextMessage freeText:
                HandleFreeText(freeText);
                break;

            case WsjtxDatagram.InboundMessage.CloseMessage:
                // Logged only — SHALL NOT terminate the daemon under any circumstance (task 4.4).
                _logger.LogInformation(
                    "external-reporting: inbound Close received from a client — no action taken.");
                break;

            case WsjtxDatagram.InboundMessage.HeartbeatMessage:
                _logger.LogDebug("external-reporting: inbound Heartbeat received.");
                break;

            case WsjtxDatagram.InboundMessage.UnsupportedMessage unsupported:
                // task 4.5: any other recognised-but-unsupported type — Debug log only.
                _logger.LogDebug(
                    "external-reporting: discarding unsupported inbound type {Type}.", unsupported.Type);
                break;
        }
    }

    private async Task HandleHaltTxAsync()
    {
        try
        {
            var qso = QsoController;
            if (qso is not null)
                await qso.AbortAsync().ConfigureAwait(false);
        }
        catch (Exception ex)
        {
            _logger.LogWarning(ex, "external-reporting: Halt Tx dispatch failed.");
        }

        // external-reporting-single-connection (task 4.1): broadcast to every configured
        // follower, concurrently, best-effort — one follower's failure/timeout SHALL NOT block this
        // instance's own AbortAsync above or delivery to any other follower. Reuses each follower's
        // own existing POST /api/v1/tx/abort endpoint, unmodified.
        var followerUrls = _configStore.Current.ExternalReporting.FollowerUrls;
        if (followerUrls.Count == 0) return;

        var broadcasts = followerUrls.Select(async url =>
        {
            try
            {
                using var response = await _relayHttpClient
                    .PostAsync($"{url.TrimEnd('/')}/api/v1/tx/abort", content: null)
                    .ConfigureAwait(false);
                if (!response.IsSuccessStatusCode)
                    _logger.LogWarning(
                        "external-reporting: Halt Tx broadcast to follower '{Url}' returned HTTP {StatusCode}.",
                        url, (int)response.StatusCode);
            }
            catch (Exception ex)
            {
                _logger.LogWarning(ex,
                    "external-reporting: Halt Tx broadcast to follower '{Url}' failed.", url);
            }
        });

        await Task.WhenAll(broadcasts).ConfigureAwait(false);
    }

    private void HandleReply(WsjtxDatagram.InboundMessage.ReplyMessage reply)
    {
        if (!_configStore.Current.ExternalReporting.HonourInboundCommands)
        {
            _logger.LogInformation(
                "external-reporting: Reply received but honourInboundCommands is disabled — ignoring.");
            return;
        }

        if (!TryExtractCallsign(reply.Message, out var callsign))
        {
            _logger.LogInformation(
                "external-reporting: Reply received but no callsign could be extracted from '{Message}' — ignoring.",
                reply.Message);
            return;
        }

        // external-reporting-single-connection (task 5.1, design.md Decision 5's v1 scope
        // limitation): a distinct diagnostic, separate from the "no callsign could be extracted"
        // case above — no behavioural change, engagement is still attempted exactly as before.
        // Lets an operator running a relaying follower tell "GridTracker2 sent nothing useful" apart
        // from "this leader never saw that callsign itself (only a follower decoded it)".
        if (!IsCallsignInCurrentDecodeBatch(callsign))
        {
            _logger.LogInformation(
                "external-reporting: Reply named '{Callsign}' which was not found in this instance's " +
                "own current decode batch — if a relaying follower decoded it, this release does not " +
                "route Reply to the originating follower (see external-reporting capability's Decision 5).",
                callsign);
        }

        var target = ReplyTarget;
        if (target is null)
        {
            _logger.LogWarning(
                "external-reporting: Reply received for '{Callsign}' but no IExternalReplyTarget is wired up — ignoring.",
                callsign);
            return;
        }

        _ = target.TryEngageAsync(callsign).ContinueWith(t =>
        {
            if (t.IsFaulted)
                _logger.LogWarning(t.Exception, "external-reporting: TryEngageAsync for '{Callsign}' faulted.", callsign);
        }, CancellationToken.None, TaskContinuationOptions.OnlyOnFaulted, TaskScheduler.Default);
    }

    /// <summary>
    /// Extracts the target callsign from a Reply datagram's echoed message text. Tries the CQ
    /// pattern first (the common case: the operator selected a CQ line in GridTracker2); falls
    /// back to the second whitespace-separated token (<c>"DEST SRC ..."</c> — the source
    /// callsign of a non-CQ directed message).
    /// </summary>
    private static bool TryExtractCallsign(string message, out string callsign)
    {
        if (QsoAnswererService.TryParseCq(message, out var cq, out _))
        {
            callsign = cq;
            return true;
        }

        var parts = message.Trim().Split(' ', StringSplitOptions.RemoveEmptyEntries);
        if (parts.Length >= 2)
        {
            callsign = parts[1];
            return true;
        }

        callsign = string.Empty;
        return false;
    }

    /// <summary>
    /// external-reporting-single-connection (task 5.1): checks whether <paramref name="callsign"/>
    /// appears as a CQ in <see cref="_lastDecodeBatch"/> — this instance's own most recent decode
    /// batch, tracked unconditionally by <see cref="DecodeLoopAsync"/> regardless of role/active
    /// state. Uses the same <see cref="QsoAnswererService.TryParseCq"/> matcher
    /// <see cref="TryExtractCallsign"/> and <c>QsoAnswererService.TryEngageExternal</c> already use.
    /// </summary>
    private bool IsCallsignInCurrentDecodeBatch(string callsign)
    {
        var batch = _lastDecodeBatch;
        if (batch is null) return false;

        foreach (var r in batch.Results)
        {
            if (QsoAnswererService.TryParseCq(r.Message, out var cq, out _)
                && string.Equals(cq, callsign, StringComparison.OrdinalIgnoreCase))
                return true;
        }
        return false;
    }

    private void HandleFreeText(WsjtxDatagram.InboundMessage.FreeTextMessage freeText)
    {
        if (!_configStore.Current.ExternalReporting.HonourInboundCommands)
        {
            _logger.LogInformation(
                "external-reporting: Free Text received but honourInboundCommands is disabled — ignoring.");
            return;
        }

        // Accepted and stored; intentionally has NO transmission effect (see design.md /
        // "Inbound Free Text gated and currently a no-op").
        LastFreeText = freeText.Text;
        _logger.LogInformation(
            "external-reporting: Free Text received and stored (no transmission effect): '{Text}'.",
            freeText.Text);
    }
}
