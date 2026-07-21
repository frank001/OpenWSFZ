using System.Threading.Channels;
using FluentAssertions;
using Microsoft.Extensions.Logging.Abstractions;
using NSubstitute;
using OpenWSFZ.Abstractions;
using OpenWSFZ.Daemon;
using OpenWSFZ.TestSupport;
using OpenWSFZ.Web;
using Xunit;

namespace OpenWSFZ.Daemon.Tests;

/// <summary>
/// Unit tests for <see cref="QsoAnswererService.TryEngageExternal"/> (gridtracker-udp-reporting,
/// task 5.4) — the five scenarios in <c>specs/qso-answerer/spec.md</c>'s "External reply engages
/// a specific decoded CQ" requirement.
///
/// <para>
/// Every SUT here is built with <c>autoAnswer=false</c> so that feeding a CQ decode batch never
/// auto-engages it — this isolates <see cref="QsoAnswererService.TryEngageExternal"/>'s own
/// engagement path from the pre-existing auto-answer path (already covered by
/// <c>QsoAnswererServiceTests</c>).
/// </para>
///
/// NFR-021: all callsigns use ITU-unallocated Q-prefix (Q1OFZ = ours, Q1TST = partner).
/// </summary>
[Trait("Category", "Unit")]
public sealed class QsoAnswererServiceExternalReplyTests
{
    private const string OurCallsign = "Q1OFZ";
    private const string OurGrid     = "JO33";
    private const string PartnerCall = "Q1TST";
    private const int    AudioFreqHz = 897;

    private sealed class MutableConfigStore : IConfigStore
    {
        private AppConfig _current;
        public MutableConfigStore(AppConfig initial) => _current = initial;
        public AppConfig Current => _current;
        public event Action<AppConfig>? OnSaved;
        public Task SaveAsync(AppConfig config, CancellationToken ct = default)
        {
            _current = config;
            OnSaved?.Invoke(config);
            return Task.CompletedTask;
        }
    }

    private sealed class MutableDecodeFilterStore : IDecodeFilterStore
    {
        public DecodeFilterState Current { get; private set; } = DecodeFilterState.Unfiltered;
        public void Set(DecodeFilterState state) => Current = state;

        // fix-decode-filter-new-value-admission: this test double never narrows an axis, so
        // there is nothing to admit into — real AdmitNewValues coverage lives in
        // DecodeFilterStoreAdmitNewValuesTests (OpenWSFZ.Web.Tests) against the real store.
        public DecodeFilterState? AdmitNewValues(DecodeResult decode) => null;
    }

    private sealed record Sut(
        QsoAnswererService Service, Channel<DecodeBatch> Channel, IPttController Ptt,
        CancellationTokenSource Cts) : IAsyncDisposable
    {
        public async ValueTask DisposeAsync()
        {
            await Cts.CancelAsync();
            await Service.StopAsync(CancellationToken.None);
            await Ptt.DisposeAsync();
            Cts.Dispose();
        }
    }

    private static async Task<Sut> CreateSutAsync(
        IDecodeFilterStore? filterStore = null, bool autoAnswer = false,
        ExternalReportingConfig? externalReporting = null)
    {
        var config = new AppConfig() with
        {
            Tx = new TxConfig
            {
                AutoAnswer      = autoAnswer,
                Callsign        = OurCallsign,
                Grid            = OurGrid,
                RetryCount      = 2,
                WatchdogMinutes = 4,
            },
            ExternalReporting = externalReporting ?? new ExternalReportingConfig(),
        };
        var store = new MutableConfigStore(config);
        var ptt   = Substitute.For<IPttController>();
        ptt.KeyDownAsync(Arg.Any<CancellationToken>()).Returns(Task.CompletedTask);
        ptt.KeyUpAsync(Arg.Any<CancellationToken>()).Returns(Task.CompletedTask);

        var channel = Channel.CreateUnbounded<DecodeBatch>();
        var adifLog = new AdifLogWriter(store, NullLogger<AdifLogWriter>.Instance);

        var service = new QsoAnswererService(channel.Reader, store, ptt, new TxEventBus(),
            adifLog, new AudioOffsetEventBus(), NullLogger<QsoAnswererService>.Instance,
            watchdogDurationOverride: TimeSpan.FromMinutes(4),
            timeProvider: null,
            catState: null,
            decodeFilterStore: filterStore);

        var cts = new CancellationTokenSource();
        await service.StartAsync(cts.Token);
        return new Sut(service, channel, ptt, cts);
    }

    /// <summary>
    /// Feeds a batch containing a CQ from <see cref="PartnerCall"/> and waits long enough for the
    /// background loop's <c>HandleIdleAsync</c> to record it as the most recent Idle-time batch
    /// (consulted by <c>TryEngageExternal</c>). Since <c>autoAnswer=false</c>, the batch is never
    /// auto-consumed — no race with the auto-answer path.
    /// </summary>
    private static async Task SeedCqBatchAsync(Sut sut, string cqCallsign = PartnerCall, RegionInfo? region = null)
    {
        sut.Channel.Writer.TryWrite(new DecodeBatch(
            DateTimeOffset.UtcNow,
            [new DecodeResult(Time: "17:30:15", Snr: -5, Dt: 0.1, FreqHz: AudioFreqHz,
                Message: $"CQ {cqCallsign} JO22", Region: region)]));

        // Wait for the background loop to record the seeded batch as the most recent Idle-time
        // decode — the exact volatile field TryEngageExternal consults — rather than a fixed
        // settle delay. Reflection mirrors this file's existing _state/_partner access pattern.
        var lastIdleField = typeof(QsoAnswererService).GetField(
            "_lastIdleDecodeBatch",
            System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance);
        await Poll.UntilAsync(() => lastIdleField!.GetValue(sut.Service) is not null,
            timeout: TimeSpan.FromSeconds(2),
            timeoutMessage: () => "background loop never recorded the seeded CQ batch");
    }

    // ── Scenario: matching decoded CQ engages ───────────────────────────────

    [Fact(DisplayName = "FR-054: External reply engages a matching decoded CQ")]
    public async Task TryEngageExternal_MatchingCq_Engages()
    {
        await using var sut = await CreateSutAsync();
        await SeedCqBatchAsync(sut);

        var engaged = await sut.Service.TryEngageExternal(PartnerCall);

        engaged.Should().BeTrue("the callsign is a non-filtered CQ in the most recent decode batch");
        sut.Service._wakeupChannel.Reader.TryRead(out _); // drain wakeup, mirroring AnswerCqAsync tests
    }

    // ── Scenario: works even when autoAnswer is disabled ────────────────────

    [Fact(DisplayName = "External reply works even when autoAnswer is disabled")]
    public async Task TryEngageExternal_AutoAnswerDisabled_StillEngages()
    {
        await using var sut = await CreateSutAsync(autoAnswer: false);
        await SeedCqBatchAsync(sut);

        var engaged = await sut.Service.TryEngageExternal(PartnerCall);

        engaged.Should().BeTrue("TryEngageExternal is not gated by tx.autoAnswer");
        sut.Service._wakeupChannel.Reader.TryRead(out _);
    }

    // ── Scenario: unknown callsign is a no-op ───────────────────────────────

    [Fact(DisplayName = "External reply to an unknown callsign is a no-op")]
    public async Task TryEngageExternal_UnknownCallsign_NoOp()
    {
        await using var sut = await CreateSutAsync();
        await SeedCqBatchAsync(sut); // seeds a CQ from PartnerCall (Q1TST), not Q9ZZZ

        var engaged = await sut.Service.TryEngageExternal("Q9ZZZ");

        engaged.Should().BeFalse("no CQ from Q9ZZZ is present in the most recent decode batch");
        sut.Service.State.Should().Be(QsoState.Idle);
        await sut.Ptt.DidNotReceive().KeyDownAsync(Arg.Any<CancellationToken>());
    }

    // ── Scenario: filtered-out callsign — restrict-to-filter opted in ───────

    [Fact(DisplayName = "Restrict-to-filter opted in: external reply to a filtered-out callsign is a no-op")]
    public async Task TryEngageExternal_FilteredOutCallsign_RestrictOptedIn_NoOp()
    {
        var filterStore = new MutableDecodeFilterStore();
        await using var sut = await CreateSutAsync(
            filterStore: filterStore,
            externalReporting: new ExternalReportingConfig(restrictExternalRepliesToDecodeFilter: true));
        await SeedCqBatchAsync(sut);

        // Attribute allow-list axes (AllowedEntities etc.) fail OPEN when Region is unresolved
        // (DecodeFilterEvaluator's documented fail-open rule) — our seeded decode has no Region,
        // so those axes can never hide it. A worked-before axis has no such fail-open guard: a
        // null WorkedBefore is treated as WorkedBeforeInfo.None (Contact = Never), so an empty
        // ContactStates allow-list genuinely filters this decode out.
        filterStore.Set(new DecodeFilterState(ContactStates: []));

        var engaged = await sut.Service.TryEngageExternal(PartnerCall);

        engaged.Should().BeFalse("Q1TST's CQ is present but filtered out under the active DecodeFilterState, " +
            "and restrictExternalRepliesToDecodeFilter is true");
        sut.Service.State.Should().Be(QsoState.Idle);
        await sut.Ptt.DidNotReceive().KeyDownAsync(Arg.Any<CancellationToken>());
    }

    // ── Scenario: filtered-out callsign — default config bypasses the filter ─

    [Fact(DisplayName = "Default config: external reply to a filtered-out callsign still engages")]
    public async Task TryEngageExternal_FilteredOutCallsign_DefaultEngagesAnyway()
    {
        var filterStore = new MutableDecodeFilterStore();
        await using var sut = await CreateSutAsync(filterStore: filterStore); // restrict flag defaults to false
        await SeedCqBatchAsync(sut);

        // Same "genuinely filters out" setup as the restrict-opted-in scenario above.
        filterStore.Set(new DecodeFilterState(ContactStates: []));

        var engaged = await sut.Service.TryEngageExternal(PartnerCall);

        engaged.Should().BeTrue("restrictExternalRepliesToDecodeFilter defaults to false — an explicit " +
            "external command is authoritative regardless of the operator's own decode-panel filter");
        sut.Service._wakeupChannel.Reader.TryRead(out _);
    }

    // ── Note: synthetic/unknown-region reachability is governed entirely by the pre-existing,
    // upstream DecodeNoiseSuppressionFilter (Program.cs's decode-pump loop), not by any check
    // inside TryEngageExternal itself — identically to the internal auto-answer path
    // (HandleIdleAsync), which has the same characteristic today. Confirmed with the Captain
    // (fix-external-reporting-clear-and-reply-filter task 3.2.3): this is not a gap introduced by
    // the new restrictExternalRepliesToDecodeFilter flag, and no redundant region check is added
    // to this method. This test pins down and documents that intentional boundary, and confirms
    // the new flag has no bearing on it either way.

    [Fact(DisplayName = "TryEngageExternal has no region check of its own — a synthetic-region CQ that " +
        "reaches the decode batch engages identically regardless of restrictExternalRepliesToDecodeFilter")]
    public async Task TryEngageExternal_SyntheticRegionCq_NoOwnRegionGate()
    {
        await using var sut = await CreateSutAsync();
        await SeedCqBatchAsync(sut,
            region: new RegionInfo(Continent: null, Entity: "Synthetic (R&R Study)", Synthetic: true));

        var engaged = await sut.Service.TryEngageExternal(PartnerCall);

        engaged.Should().BeTrue(
            "TryEngageExternal performs no Region-based exclusion of its own; the absolute " +
            "synthetic/unknown-region exclusion lives in ExternalReportingService's outbound path " +
            "and in the upstream DecodeNoiseSuppressionFilter (which, under its default " +
            "SuppressSynthetic=true, would have prevented this decode from ever reaching this " +
            "method's batch in the first place — this test simulates the batch already containing " +
            "one, matching how this test file already bypasses that upstream stage throughout)");
        sut.Service._wakeupChannel.Reader.TryRead(out _);
    }

    // ── Scenario: already engaged is a no-op ────────────────────────────────

    [Fact(DisplayName = "External reply while already engaged is a no-op")]
    public async Task TryEngageExternal_AlreadyEngaged_NoOp()
    {
        await using var sut = await CreateSutAsync();
        await SeedCqBatchAsync(sut);

        // Force a different in-progress engagement via reflection (mirrors the existing test
        // file's pattern for setting _state/_partner directly without a real TX cycle).
        var type  = typeof(QsoAnswererService);
        var flags = System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance;
        type.GetField("_state",   flags)!.SetValue(sut.Service, QsoState.WaitReport);
        type.GetField("_partner", flags)!.SetValue(sut.Service, "Q2OTHER");

        var engaged = await sut.Service.TryEngageExternal(PartnerCall);

        engaged.Should().BeFalse("the service is not Idle — already mid-QSO with a different partner");
        sut.Service.State.Should().Be(QsoState.WaitReport, "the in-progress QSO must continue unaffected");
        sut.Service.Partner.Should().Be("Q2OTHER");
    }
}
