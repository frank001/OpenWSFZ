using FluentAssertions;
using System.Net;
using System.Text;
using System.Text.Json;
using Xunit;

namespace OpenWSFZ.Web.Tests;

/// <summary>
/// Regression tests for D-010: <c>POST /api/v1/config</c> must never persist a
/// <c>null</c> <c>logging</c> or <c>decodeLog</c> section into the live in-memory
/// config, even when the request body omits those keys entirely.
///
/// <para>
/// Payloads here are built as raw JSON strings via <see cref="StringContent"/>,
/// NOT <c>new AppConfig() with {...}</c> — the latter always populates
/// <c>Logging</c>/<c>DecodeLog</c> through the C# property initialisers and would
/// never reproduce the System.Text.Json source-generation quirk where an omitted
/// key deserialises a non-nullable init property to <c>null</c> instead of falling
/// back to its initialiser.
/// </para>
/// </summary>
[Trait("Category", "Integration")]
public sealed class ConfigApiNullGuardTests : IClassFixture<WebTestFactory>
{
    private readonly WebTestFactory _factory;

    public ConfigApiNullGuardTests(WebTestFactory factory) => _factory = factory;

    [Fact(DisplayName = "D-010 AC-1: POST omitting \"decodeLog\" key does not persist a null DecodeLog")]
    public async Task PostConfig_OmittingDecodeLogKey_DoesNotPersistNullDecodeLog()
    {
        var client  = _factory.CreateClient();
        var content = new StringContent(
            """{ "audioDeviceId": "test-device" }""",
            Encoding.UTF8, "application/json");

        var postResp = await client.PostAsync("/api/v1/config", content);
        postResp.StatusCode.Should().Be(HttpStatusCode.OK,
            "a request body omitting decodeLog must still be accepted");

        var getResp = await client.GetAsync("/api/v1/config");
        getResp.StatusCode.Should().Be(HttpStatusCode.OK);

        var json = await getResp.Content.ReadAsStringAsync();
        using var doc = JsonDocument.Parse(json);

        doc.RootElement.TryGetProperty("decodeLog", out var decodeLogElement).Should().BeTrue(
            "GET /api/v1/config must include the decodeLog key");
        decodeLogElement.ValueKind.Should().NotBe(JsonValueKind.Null,
            "a POST body omitting \"decodeLog\" must never leave IConfigStore.Current.DecodeLog null " +
            "(D-010: this null persists and crashes every subsequent AllTxtWriter.AppendAsync call)");

        // Must be default DecodeLogConfig values (Enabled = false), not merely non-null.
        decodeLogElement.GetProperty("enabled").GetBoolean().Should().BeFalse(
            "the recovered DecodeLog must be the default DecodeLogConfig(), i.e. disabled");
    }

    [Fact(DisplayName = "D-010 AC-2: POST omitting \"logging\" key does not persist a null Logging")]
    public async Task PostConfig_OmittingLoggingKey_DoesNotPersistNullLogging()
    {
        var client  = _factory.CreateClient();
        var content = new StringContent(
            """{ "audioDeviceId": "test-device" }""",
            Encoding.UTF8, "application/json");

        var postResp = await client.PostAsync("/api/v1/config", content);
        postResp.StatusCode.Should().Be(HttpStatusCode.OK,
            "a request body omitting logging must still be accepted");

        var getResp = await client.GetAsync("/api/v1/config");
        getResp.StatusCode.Should().Be(HttpStatusCode.OK);

        var json = await getResp.Content.ReadAsStringAsync();
        using var doc = JsonDocument.Parse(json);

        doc.RootElement.TryGetProperty("logging", out var loggingElement).Should().BeTrue(
            "GET /api/v1/config must include the logging key");
        loggingElement.ValueKind.Should().NotBe(JsonValueKind.Null,
            "a POST body omitting \"logging\" must never leave IConfigStore.Current.Logging null");
    }

    [Fact(DisplayName = "D-010-class AC-3: POST omitting \"decodeNoiseSuppression\" key does not persist a null DecodeNoiseSuppression")]
    public async Task PostConfig_OmittingDecodeNoiseSuppressionKey_DoesNotPersistNullDecodeNoiseSuppression()
    {
        var client  = _factory.CreateClient();
        var content = new StringContent(
            """{ "audioDeviceId": "test-device" }""",
            Encoding.UTF8, "application/json");

        var postResp = await client.PostAsync("/api/v1/config", content);
        postResp.StatusCode.Should().Be(HttpStatusCode.OK,
            "a request body omitting decodeNoiseSuppression must still be accepted");

        var getResp = await client.GetAsync("/api/v1/config");
        getResp.StatusCode.Should().Be(HttpStatusCode.OK);

        var json = await getResp.Content.ReadAsStringAsync();
        using var doc = JsonDocument.Parse(json);

        doc.RootElement.TryGetProperty("decodeNoiseSuppression", out var decodeNoiseSuppressionElement)
            .Should().BeTrue("GET /api/v1/config must include the decodeNoiseSuppression key");
        decodeNoiseSuppressionElement.ValueKind.Should().NotBe(JsonValueKind.Null,
            "a POST body omitting \"decodeNoiseSuppression\" must never leave " +
            "IConfigStore.Current.DecodeNoiseSuppression null (this class of bug crashes every " +
            "subsequent DecodeNoiseSuppressionFilter.Apply call in the decode-pump loop before " +
            "AllTxtWriter.AppendAsync is reached)");

        // Must be default DecodeNoiseSuppressionConfig values, not merely non-null.
        decodeNoiseSuppressionElement.GetProperty("suppressUnknownRegion").ValueKind.Should().Be(
            JsonValueKind.Null,
            "the recovered DecodeNoiseSuppression must be the default DecodeNoiseSuppressionConfig(), " +
            "i.e. SuppressUnknownRegion unset");
        decodeNoiseSuppressionElement.GetProperty("suppressSynthetic").GetBoolean().Should().BeTrue(
            "the recovered DecodeNoiseSuppression must be the default DecodeNoiseSuppressionConfig(), " +
            "i.e. SuppressSynthetic = true");
    }

    [Fact(DisplayName = "gridtracker-udp-reporting: POST omitting \"externalReporting\" key does not persist a null ExternalReporting")]
    public async Task PostConfig_OmittingExternalReportingKey_DoesNotPersistNullExternalReporting()
    {
        var client  = _factory.CreateClient();
        var content = new StringContent(
            """{ "audioDeviceId": "test-device" }""",
            Encoding.UTF8, "application/json");

        var postResp = await client.PostAsync("/api/v1/config", content);
        postResp.StatusCode.Should().Be(HttpStatusCode.OK,
            "a request body omitting externalReporting must still be accepted");

        var getResp = await client.GetAsync("/api/v1/config");
        getResp.StatusCode.Should().Be(HttpStatusCode.OK);

        var json = await getResp.Content.ReadAsStringAsync();
        using var doc = JsonDocument.Parse(json);

        doc.RootElement.TryGetProperty("externalReporting", out var extRepElement).Should().BeTrue(
            "GET /api/v1/config must include the externalReporting key");
        extRepElement.ValueKind.Should().NotBe(JsonValueKind.Null,
            "a POST body omitting \"externalReporting\" must never leave " +
            "IConfigStore.Current.ExternalReporting null (this class of bug crashes " +
            "ExternalReportingService.Reconcile, called synchronously from IConfigStore.OnSaved " +
            "on every subsequent POST /api/v1/config)");

        // Must be default ExternalReportingConfig values, not merely non-null.
        extRepElement.GetProperty("enabled").GetBoolean().Should().BeFalse(
            "the recovered ExternalReporting must be the default ExternalReportingConfig(), i.e. disabled");
    }

    [Fact(DisplayName =
        "cycle-audio-archive crash: POST omitting \"cycleAudioArchive\" key does not persist a null " +
        "CycleAudioArchive (dev-tasks/2026-07-28-fix-cycle-audio-archive-null-config-crash.md)")]
    public async Task PostConfig_OmittingCycleAudioArchiveKey_DoesNotPersistNullCycleAudioArchive()
    {
        var client  = _factory.CreateClient();
        var content = new StringContent(
            """{ "audioDeviceId": "test-device" }""",
            Encoding.UTF8, "application/json");

        var postResp = await client.PostAsync("/api/v1/config", content);
        postResp.StatusCode.Should().Be(HttpStatusCode.OK,
            "a request body omitting cycleAudioArchive must still be accepted — there is no " +
            "Settings-page UI for this section (same situation as ptt), so EVERY ordinary " +
            "Settings-page save omits this key");

        var getResp = await client.GetAsync("/api/v1/config");
        getResp.StatusCode.Should().Be(HttpStatusCode.OK);

        var json = await getResp.Content.ReadAsStringAsync();
        using var doc = JsonDocument.Parse(json);

        doc.RootElement.TryGetProperty("cycleAudioArchive", out var cycleAudioArchiveElement).Should().BeTrue(
            "GET /api/v1/config must include the cycleAudioArchive key");
        cycleAudioArchiveElement.ValueKind.Should().NotBe(JsonValueKind.Null,
            "a POST body omitting \"cycleAudioArchive\" must never leave " +
            "IConfigStore.Current.CycleAudioArchive null — this crashes the very next decode cycle's " +
            "CycleArchiveService.TryEnqueue with an unguarded NullReferenceException and takes the " +
            "whole daemon process down (the live incident this regression test guards against)");

        // Must be default CycleAudioArchiveConfig values (Mode = Off), not merely non-null — a
        // live read of .Mode (mirroring TryEnqueue's first line) must not throw.
        cycleAudioArchiveElement.GetProperty("mode").GetString().Should().Be("off",
            "the recovered CycleAudioArchive must be the default CycleAudioArchiveConfig(), i.e. Off");
    }

    [Fact(DisplayName =
        "cycle-audio-archive crash §4: POST omitting \"remoteAccess\" key does not persist a null " +
        "RemoteAccess (same gap, bundled in per dev-tasks/2026-07-28-fix-cycle-audio-archive-null-" +
        "config-crash.md §4)")]
    public async Task PostConfig_OmittingRemoteAccessKey_DoesNotPersistNullRemoteAccess()
    {
        var client  = _factory.CreateClient();
        var content = new StringContent(
            """{ "audioDeviceId": "test-device" }""",
            Encoding.UTF8, "application/json");

        var postResp = await client.PostAsync("/api/v1/config", content);
        postResp.StatusCode.Should().Be(HttpStatusCode.OK,
            "a request body omitting remoteAccess must still be accepted");

        var getResp = await client.GetAsync("/api/v1/config");
        getResp.StatusCode.Should().Be(HttpStatusCode.OK);

        var json = await getResp.Content.ReadAsStringAsync();
        using var doc = JsonDocument.Parse(json);

        doc.RootElement.TryGetProperty("remoteAccess", out var remoteAccessElement).Should().BeTrue(
            "GET /api/v1/config must include the remoteAccess key");
        remoteAccessElement.ValueKind.Should().NotBe(JsonValueKind.Null,
            "a POST body omitting \"remoteAccess\" must never leave IConfigStore.Current.RemoteAccess null");
        remoteAccessElement.GetProperty("enabled").GetBoolean().Should().BeFalse(
            "the recovered RemoteAccess must be the default RemoteAccessConfig(), i.e. disabled");
    }

    [Fact(DisplayName = "cat-tx-ptt AC-1: POST omitting \"ptt\" key does not persist a null Ptt")]
    public async Task PostConfig_OmittingPttKey_DoesNotPersistNullPtt()
    {
        var client  = _factory.CreateClient();
        var content = new StringContent(
            """{ "audioDeviceId": "test-device" }""",
            Encoding.UTF8, "application/json");

        var postResp = await client.PostAsync("/api/v1/config", content);
        postResp.StatusCode.Should().Be(HttpStatusCode.OK,
            "a request body omitting ptt must still be accepted — the Settings page never sends " +
            "a \"ptt\" key at all (design.md Decision 6: no speculative UI), so every ordinary " +
            "Settings-page save must not be rejected");

        var getResp = await client.GetAsync("/api/v1/config");
        getResp.StatusCode.Should().Be(HttpStatusCode.OK);

        var json = await getResp.Content.ReadAsStringAsync();
        using var doc = JsonDocument.Parse(json);

        doc.RootElement.TryGetProperty("ptt", out var pttElement).Should().BeTrue(
            "GET /api/v1/config must include the ptt key");
        pttElement.ValueKind.Should().NotBe(JsonValueKind.Null,
            "a POST body omitting \"ptt\" must never leave IConfigStore.Current.Ptt null " +
            "(silently reverts CAT-command/serial RTS-DTR PTT to VOX with no warning, and risks a " +
            "stuck-key NullReferenceException in CatPttController/SerialRtsDtrPttController.KeyDownAsync " +
            "if a CAT/serial controller is already the active singleton)");

        // Freshly-initialised store: Current.Ptt is still the untouched default at this
        // point, so falling back to it (rather than a hardcoded new PttConfig()) produces
        // the same observable defaults as before. See the AC-2 test below for the case
        // that actually distinguishes the two fallbacks — a previously-persisted non-default
        // Ptt surviving an unrelated save.
        pttElement.GetProperty("method").GetString().Should().Be("AudioVox");
        pttElement.GetProperty("serialLine").GetString().Should().Be("Rts");
        pttElement.GetProperty("leadTimeMs").GetInt32().Should().Be(50);
        pttElement.GetProperty("tailTimeMs").GetInt32().Should().Be(50);
        pttElement.GetProperty("watchdogTimeoutMs").GetInt32().Should().Be(20000);
    }

    [Fact(DisplayName =
        "fix-external-reporting-appid-collision AC: a Settings-page-shaped externalReporting save " +
        "does not revert a previously-persisted non-default InstanceId back to \"OpenWSFZ\"")]
    public async Task PostConfig_SettingsPageShapedSave_PreservesPreviouslyPersistedInstanceId()
    {
        // Unlike ptt (never sent by the UI at all), web/js/settings.js's External Programs tab
        // DOES send a full, non-null "externalReporting" object on every save — it just has no
        // field yet for "instanceId" (no UI required per this change's minimum scope). Confirmed
        // live before the WebApp.cs guard was added: this exact shape (whole section present,
        // instanceId key absent) silently reverted InstanceId to the STJ-constructor-default
        // "OpenWSFZ", undoing a multi-instance operator's configuration on the very next
        // unrelated Settings-page save and reintroducing the GridTracker collision this change
        // fixes.
        var client = _factory.CreateClient();

        try
        {
            // Seed a non-default InstanceId (simulates the targeted POST an operator uses today,
            // per dev-tasks/2026-07-28-fix-external-reporting-appid-collision.md §3 — no
            // Settings-page field exists for this).
            var seedContent = new StringContent(
                """{ "audioDeviceId": "test-device", "externalReporting": { "instanceId": "OpenWSFZ-20m" } }""",
                Encoding.UTF8, "application/json");
            (await client.PostAsync("/api/v1/config", seedContent)).StatusCode.Should().Be(HttpStatusCode.OK);

            var seededJson = await (await client.GetAsync("/api/v1/config")).Content.ReadAsStringAsync();
            using (var seededDoc = JsonDocument.Parse(seededJson))
            {
                seededDoc.RootElement.GetProperty("externalReporting").GetProperty("instanceId").GetString()
                    .Should().Be("OpenWSFZ-20m", "the seed POST must have taken effect before testing preservation");
            }

            // Now perform an ordinary Settings-page save shaped exactly like
            // web/js/settings.js's collected "externalReporting" object (settings.js:1345-1350) —
            // every field it knows about, "instanceId" entirely absent.
            var settingsPageShaped = new StringContent(
                """
                {
                  "audioDeviceId": "test-device",
                  "externalReporting": {
                    "enabled": false,
                    "targets": [],
                    "honourInboundCommands": false,
                    "restrictExternalRepliesToDecodeFilter": false
                  }
                }
                """,
                Encoding.UTF8, "application/json");
            (await client.PostAsync("/api/v1/config", settingsPageShaped)).StatusCode.Should().Be(HttpStatusCode.OK);

            var afterJson = await (await client.GetAsync("/api/v1/config")).Content.ReadAsStringAsync();
            using var afterDoc = JsonDocument.Parse(afterJson);
            afterDoc.RootElement.GetProperty("externalReporting").GetProperty("instanceId").GetString()
                .Should().Be("OpenWSFZ-20m",
                    "an unrelated Settings-page save must not silently revert InstanceId to " +
                    "\"OpenWSFZ\" — this is the exact multi-instance-collision regression this test " +
                    "guards against");
        }
        finally
        {
            // Restore Current.ExternalReporting to the default before returning control to the
            // shared WebTestFactory (IClassFixture — one instance for this whole test class), so
            // this test's seeded state can never leak into the gridtracker-udp-reporting test
            // above or any other test in this class regardless of xUnit's execution order.
            var resetContent = new StringContent(
                """{ "audioDeviceId": "test-device", "externalReporting": { "instanceId": "OpenWSFZ" } }""",
                Encoding.UTF8, "application/json");
            await client.PostAsync("/api/v1/config", resetContent);
        }
    }

    [Fact(DisplayName =
        "fix-external-reporting-appid-collision AC: an explicit POST resetting instanceId to the " +
        "literal default is honoured, not mistaken for omission")]
    public async Task PostConfig_ExplicitInstanceIdResetToDefault_IsHonoured()
    {
        // The preservation guard above (PostConfig_SettingsPageShapedSave_PreservesPreviouslyPersistedInstanceId)
        // must not overcorrect into treating every incoming "OpenWSFZ" as "the client didn't
        // really mean it" — an operator explicitly resetting a two-instance setup back to a
        // single instance (or reverting a typo) sends "instanceId": "OpenWSFZ" on purpose and
        // that must win.
        var client = _factory.CreateClient();

        try
        {
            var seedContent = new StringContent(
                """{ "audioDeviceId": "test-device", "externalReporting": { "instanceId": "OpenWSFZ-20m" } }""",
                Encoding.UTF8, "application/json");
            (await client.PostAsync("/api/v1/config", seedContent)).StatusCode.Should().Be(HttpStatusCode.OK);

            var explicitResetContent = new StringContent(
                """{ "audioDeviceId": "test-device", "externalReporting": { "instanceId": "OpenWSFZ" } }""",
                Encoding.UTF8, "application/json");
            (await client.PostAsync("/api/v1/config", explicitResetContent)).StatusCode.Should().Be(HttpStatusCode.OK);

            var afterJson = await (await client.GetAsync("/api/v1/config")).Content.ReadAsStringAsync();
            using var afterDoc = JsonDocument.Parse(afterJson);
            afterDoc.RootElement.GetProperty("externalReporting").GetProperty("instanceId").GetString()
                .Should().Be("OpenWSFZ",
                    "a POST body that explicitly includes \"instanceId\": \"OpenWSFZ\" must be honoured " +
                    "as a real reset, not silently overridden back to the previously-persisted value");
        }
        finally
        {
            var resetContent = new StringContent(
                """{ "audioDeviceId": "test-device", "externalReporting": { "instanceId": "OpenWSFZ" } }""",
                Encoding.UTF8, "application/json");
            await client.PostAsync("/api/v1/config", resetContent);
        }
    }

    [Fact(DisplayName =
        "FR-063: a Settings-page-shaped externalReporting save does not revert previously-persisted " +
        "role/leaderUrl/followerUrls")]
    public async Task PostConfig_SettingsPageShapedSave_PreservesPreviouslyPersistedRoleLeaderFollowerUrls()
    {
        // Same rationale as PostConfig_SettingsPageShapedSave_PreservesPreviouslyPersistedInstanceId
        // above (fix-external-reporting-appid-collision): web/js/settings.js's External Programs
        // tab has no field yet for role/leaderUrl/followerUrls either, so an ordinary, unrelated
        // Settings-page save must not silently collapse a configured leader/follower group back
        // onto "leader"/null/[].
        var client = _factory.CreateClient();

        try
        {
            var seedContent = new StringContent(
                """
                {
                  "audioDeviceId": "test-device",
                  "externalReporting": {
                    "role": "follower",
                    "leaderUrl": "http://127.0.0.1:8080",
                    "followerUrls": ["http://127.0.0.1:8081"]
                  }
                }
                """,
                Encoding.UTF8, "application/json");
            (await client.PostAsync("/api/v1/config", seedContent)).StatusCode.Should().Be(HttpStatusCode.OK);

            var settingsPageShaped = new StringContent(
                """
                {
                  "audioDeviceId": "test-device",
                  "externalReporting": {
                    "enabled": false,
                    "targets": [],
                    "honourInboundCommands": false,
                    "restrictExternalRepliesToDecodeFilter": false
                  }
                }
                """,
                Encoding.UTF8, "application/json");
            (await client.PostAsync("/api/v1/config", settingsPageShaped)).StatusCode.Should().Be(HttpStatusCode.OK);

            var afterJson = await (await client.GetAsync("/api/v1/config")).Content.ReadAsStringAsync();
            using var afterDoc = JsonDocument.Parse(afterJson);
            var extRep = afterDoc.RootElement.GetProperty("externalReporting");
            extRep.GetProperty("role").GetString().Should().Be("follower",
                "an unrelated Settings-page save must not silently revert role to \"leader\"");
            extRep.GetProperty("leaderUrl").GetString().Should().Be("http://127.0.0.1:8080");
            extRep.GetProperty("followerUrls").EnumerateArray().Select(e => e.GetString())
                .Should().Equal("http://127.0.0.1:8081");
        }
        finally
        {
            var resetContent = new StringContent(
                """{ "audioDeviceId": "test-device", "externalReporting": { "role": "leader", "leaderUrl": null, "followerUrls": [] } }""",
                Encoding.UTF8, "application/json");
            await client.PostAsync("/api/v1/config", resetContent);
        }
    }

    [Fact(DisplayName =
        "cat-tx-ptt AC-2: an unrelated Settings-page save does not revert a previously-persisted " +
        "non-default ptt.method back to AudioVox")]
    public async Task PostConfig_UnrelatedSave_PreservesPreviouslyPersistedPtt()
    {
        // This is the actual hardware-acceptance symptom (dev-tasks/2026-07-12-cat-tx-ptt-null-
        // ptt-config-guard.md, "Case A"): a null-guard that falls back to a hardcoded
        // `new PttConfig()` stops the crash but does NOT stop every ordinary Settings-page
        // save — even one that has nothing to do with PTT — from silently discarding an
        // operator's manually-configured "CatCommand"/"SerialRtsDtr" ptt.method, because
        // web/js/settings.js never sends a "ptt" key in the first place. The fix must fall
        // back to the already-persisted IConfigStore.Current.Ptt instead, so an omitted
        // "ptt" key is a true no-op rather than an implicit reset to defaults.
        var client = _factory.CreateClient();

        try
        {
            // Seed a non-default, previously-persisted Ptt section (simulates an operator
            // having configured CAT-command PTT, whether via a prior POST that did include
            // "ptt" or a hand-edited config.json picked up at daemon startup).
            var seedContent = new StringContent(
                """
                {
                  "audioDeviceId": "test-device",
                  "ptt": {
                    "method": "CatCommand",
                    "serialPort": "COM9",
                    "serialLine": "Dtr",
                    "leadTimeMs": 75,
                    "tailTimeMs": 75,
                    "watchdogTimeoutMs": 15000
                  }
                }
                """,
                Encoding.UTF8, "application/json");
            (await client.PostAsync("/api/v1/config", seedContent)).StatusCode
                .Should().Be(HttpStatusCode.OK);

            // Sanity-check the seed actually took.
            var seededJson = await (await client.GetAsync("/api/v1/config")).Content.ReadAsStringAsync();
            using (var seededDoc = JsonDocument.Parse(seededJson))
            {
                seededDoc.RootElement.GetProperty("ptt").GetProperty("method").GetString()
                    .Should().Be("CatCommand", "the seed POST must have taken effect before testing preservation");
            }

            // Now perform an ordinary, unrelated Settings-page save — a real save always
            // omits "ptt" entirely, so this reproduces exactly what web/js/settings.js sends.
            var unrelatedSaveContent = new StringContent(
                """{ "audioDeviceId": "test-device", "showCycleCountdown": true }""",
                Encoding.UTF8, "application/json");
            (await client.PostAsync("/api/v1/config", unrelatedSaveContent)).StatusCode
                .Should().Be(HttpStatusCode.OK);

            var afterJson = await (await client.GetAsync("/api/v1/config")).Content.ReadAsStringAsync();
            using var afterDoc = JsonDocument.Parse(afterJson);
            var pttAfter = afterDoc.RootElement.GetProperty("ptt");

            pttAfter.GetProperty("method").GetString().Should().Be("CatCommand",
                "an unrelated Settings-page save must not silently revert ptt.method to AudioVox " +
                "— this is the exact hardware-acceptance symptom (\"the radio never enables TX\") " +
                "this test guards against");
            pttAfter.GetProperty("serialPort").GetString().Should().Be("COM9");
            pttAfter.GetProperty("serialLine").GetString().Should().Be("Dtr");
            pttAfter.GetProperty("leadTimeMs").GetInt32().Should().Be(75);
            pttAfter.GetProperty("tailTimeMs").GetInt32().Should().Be(75);
            pttAfter.GetProperty("watchdogTimeoutMs").GetInt32().Should().Be(15000);
        }
        finally
        {
            // Restore Current.Ptt to the default before returning control to the shared
            // WebTestFactory (IClassFixture — one instance for this whole test class), so
            // this test's seeded state can never leak into AC-1 or any other test in this
            // class regardless of xUnit's execution order.
            var resetContent = new StringContent(
                """{ "audioDeviceId": "test-device", "ptt": { "method": "AudioVox" } }""",
                Encoding.UTF8, "application/json");
            await client.PostAsync("/api/v1/config", resetContent);
        }
    }
}
