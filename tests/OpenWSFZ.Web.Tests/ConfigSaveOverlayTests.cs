using FluentAssertions;
using Microsoft.Extensions.DependencyInjection;
using OpenWSFZ.Abstractions;
using System.Collections;
using System.Net;
using System.Reflection;
using System.Text;
using System.Text.Json;
using System.Text.Json.Nodes;
using Xunit;

namespace OpenWSFZ.Web.Tests;

/// <summary>
/// The key set of the payload <c>web/js/settings.js</c> posts on every save — the literal passed to
/// <c>postConfig({...})</c>. Test T13 (<c>web/js/settingsPayload.test.js</c>) fails when the JS
/// payload and this table disagree, so a payload change without a fixture change cannot pass.
/// </summary>
internal static class SettingsPayload
{
    /// <summary>Top-level key → nested keys (<c>null</c> = scalar leaf).</summary>
    public static readonly IReadOnlyDictionary<string, string[]?> Shape = new Dictionary<string, string[]?>
    {
        ["audioDeviceId"]           = null,
        ["audioDeviceFriendlyName"] = null,
        ["audioOutputDeviceId"]     = null,
        ["audioOutputFriendlyName"] = null,
        ["port"]                    = null,
        ["showCycleCountdown"]      = null,
        ["logLevel"]                = null,
        ["decodeLog"]   = ["enabled", "path", "dialFrequencyMHz"],
        ["logging"]     = ["fileEnabled", "directory", "fileLogLevel", "rotationSchedule",
                           "rotationTime", "rotationDayOfWeek", "maxFiles"],
        ["cat"]         = ["enabled", "rigModel", "serialPort", "baudRate", "rigctldHost",
                           "rigctldPort", "pollIntervalSeconds", "lastPolledFrequencyMHz"],
        ["ptt"]         = ["method", "serialPort", "serialLine", "leadTimeMs", "tailTimeMs",
                           "watchdogTimeoutMs"],
        ["tx"]          = ["callsign", "grid", "watchdogMinutes", "retryCount", "role",
                           "callerPartnerSelect", "qsoConfirmation"],
        ["remoteAccess"] = ["enabled", "passphrase"],
        ["decoder"]     = ["kMinScorePass2", "osdCorrThreshold", "osdNhardMax"],
        ["decodeNoiseSuppression"] = ["suppressUnknownRegion", "suppressSynthetic"],
        ["externalReporting"] = ["enabled", "targets", "honourInboundCommands",
                                 "restrictExternalRepliesToDecodeFilter"],
        // Part C adds the archive group. The pre-Part-C payload (an old cached page) omits it.
        ["cycleAudioArchive"] = ["mode", "directory", "maxSizeMb", "maxAgeHours", "writeManifest"],
    };

    /// <summary>
    /// Builds a Settings-shaped body from a stored config: exactly the keys of <see cref="Shape"/>,
    /// with the stored values. <paramref name="includeArchive"/> <c>false</c> reproduces the
    /// pre-Part-C page (no <c>cycleAudioArchive</c> key).
    /// </summary>
    public static JsonObject BodyFrom(JsonNode stored, bool includeArchive)
    {
        var body = new JsonObject();
        foreach (var (key, nested) in Shape)
        {
            if (!includeArchive && key == "cycleAudioArchive") continue;
            var src = stored[key];
            if (nested is null || src is not JsonObject srcObj)
            {
                body[key] = src?.DeepClone();
                continue;
            }
            var obj = new JsonObject();
            foreach (var k in nested)
                obj[k] = srcObj[k]?.DeepClone();
            body[key] = obj;
        }
        return body;
    }
}

/// <summary>
/// Builds an <see cref="AppConfig"/> in which every leaf differs from its default, by reflection,
/// so a field added to <see cref="AppConfig"/> in future is covered without anyone editing a test (T4).
/// Values are chosen to stay inside the handler's clamp/validation ranges: the point is that the
/// config round-trips unchanged, not that validation fires.
/// </summary>
internal static class NonDefaultConfig
{
    public static AppConfig Build()
    {
        // Nullable sections (cat, tx, decoder) default to null; NonDefaultFor() materialises them.
        return (AppConfig)Populate(typeof(AppConfig));
    }

    private static object Populate(Type type)
    {
        var obj = CreateDefault(type);
        foreach (var p in type.GetProperties(BindingFlags.Public | BindingFlags.Instance))
        {
            if (p.SetMethod is not { IsPublic: true }) continue;
            p.SetValue(obj, NonDefaultFor(p.PropertyType, p.GetValue(obj), p.Name));
        }
        return obj;
    }

    private static object CreateDefault(Type type)
    {
        var parameterless = type.GetConstructor(Type.EmptyTypes);
        if (parameterless is not null) return parameterless.Invoke(null);

        // Records with an all-optional [JsonConstructor]: invoke it with every parameter missing.
        var ctor = type.GetConstructors()
            .First(c => c.GetParameters().All(pi => pi.IsOptional));
        var args = ctor.GetParameters().Select(_ => Type.Missing).ToArray();
        return ctor.Invoke(BindingFlags.OptionalParamBinding, null, args, null);
    }

    private static object? NonDefaultFor(Type type, object? current, string name)
    {
        var t = Nullable.GetUnderlyingType(type) ?? type;

        if (t == typeof(bool))   return !((current as bool?) ?? false);
        if (t == typeof(int))    return ((current as int?) ?? 0) + 1;
        if (t == typeof(float))  return ((current as float?) ?? 0f) + 0.01f;
        if (t == typeof(double)) return ((current as double?) ?? 0d) + 7.074;
        if (t == typeof(string))
        {
            // Values that other code parses must stay parseable.
            return name switch
            {
                "LogLevel"     => "Warning",
                "FileLogLevel" => "Debug",
                "SerialLine"   => "Dtr",
                "Method"       => "SerialRtsDtr",
                "RigModel"     => "RigCtld",
                "Role"         => "follower", // ExternalReporting.Role; its leaderUrl becomes "-nd", non-empty, so valid
                _              => ((current as string) ?? "") + "-nd",
            };
        }
        if (t.IsEnum)
        {
            var values = Enum.GetValues(t);
            var idx = Array.IndexOf(values, current ?? values.GetValue(0));
            return values.GetValue((idx + 1) % values.Length);
        }
        if (t == typeof(IReadOnlyList<ExternalReportingTarget>))
            return new List<ExternalReportingTarget>
            {
                new(name: "T-nd", host: "192.0.2.1", port: 2238, enabled: false),
            };
        if (t == typeof(IReadOnlyList<string>))
            return new List<string> { "http://192.0.2.1:8081" };
        if (t.IsClass && t.Namespace == "OpenWSFZ.Abstractions")
            return Populate(t);

        throw new NotSupportedException(
            $"NonDefaultConfig cannot build a non-default {type} for '{name}'. " +
            "A new field type was added to AppConfig: teach NonDefaultConfig about it, so T4 keeps covering it.");
    }
}

/// <summary>
/// #193 and its class: <c>POST /api/v1/config</c> applies the body as an overlay on the stored config;
/// a key the body omits (at any depth) is left as stored. Tests T1, T2, T4–T12 of the
/// config-save-preserves-unsent-settings change.
/// </summary>
[Trait("Category", "Integration")]
public sealed class ConfigSaveOverlayTests
{
    private static readonly JsonSerializerOptions Web = new(JsonSerializerDefaults.Web);

    private static async Task<string> GetConfigJsonAsync(HttpClient client)
        => await client.GetStringAsync("/api/v1/config");

    private static Task<HttpResponseMessage> PostAsync(HttpClient client, string json)
        => client.PostAsync("/api/v1/config", new StringContent(json, Encoding.UTF8, "application/json"));

    private static async Task SeedAsync(WebTestFactory factory, AppConfig cfg)
        => await factory.Services.GetRequiredService<IConfigStore>().SaveAsync(cfg);

    private static AppConfig ArchiveSeed() => new()
    {
        CycleAudioArchive = new CycleAudioArchiveConfig(
            mode: CycleAudioArchiveMode.All, directory: "X", maxSizeMb: 999, maxAgeHours: 9,
            writeManifest: false),
    };

    // ── T1 ──────────────────────────────────────────────────────────────────

    [Fact(DisplayName = "T1 (#193): a Settings-shaped save without cycleAudioArchive keeps the stored archive settings")]
    public async Task T1_SettingsShapedSave_KeepsStoredArchive()
    {
        using var factory = new WebTestFactory();
        var client = factory.CreateClient();
        await SeedAsync(factory, ArchiveSeed());

        var stored = JsonNode.Parse(await GetConfigJsonAsync(client))!;
        var body   = SettingsPayload.BodyFrom(stored, includeArchive: false);
        body.ContainsKey("cycleAudioArchive").Should().BeFalse("this is the pre-Part-C page's payload");

        (await PostAsync(client, body.ToJsonString())).StatusCode.Should().Be(HttpStatusCode.OK);

        var after = JsonNode.Parse(await GetConfigJsonAsync(client))!;
        after["cycleAudioArchive"]!.ToJsonString().Should().Be(stored["cycleAudioArchive"]!.ToJsonString());
        after["cycleAudioArchive"]!["mode"]!.GetValue<string>().Should().Be("all");
    }

    // ── T2 ──────────────────────────────────────────────────────────────────

    [Fact(DisplayName = "T2: an explicit cycleAudioArchive object is applied")]
    public async Task T2_ExplicitArchiveObject_IsApplied()
    {
        using var factory = new WebTestFactory();
        var client = factory.CreateClient();
        await SeedAsync(factory, ArchiveSeed());

        var resp = await PostAsync(client,
            """{ "cycleAudioArchive": { "mode": "noDecodes", "directory": "Y", "maxSizeMb": 5, "maxAgeHours": 6, "writeManifest": true } }""");
        resp.StatusCode.Should().Be(HttpStatusCode.OK);

        var a = JsonNode.Parse(await GetConfigJsonAsync(client))!["cycleAudioArchive"]!;
        a["mode"]!.GetValue<string>().Should().Be("noDecodes");
        a["directory"]!.GetValue<string>().Should().Be("Y");
        a["maxSizeMb"]!.GetValue<int>().Should().Be(5);
        a["maxAgeHours"]!.GetValue<int>().Should().Be(6);
        a["writeManifest"]!.GetValue<bool>().Should().BeTrue();
    }

    [Fact(DisplayName = "T2b: a partial cycleAudioArchive object merges (omitted archive keys keep their stored value)")]
    public async Task T2b_PartialArchiveObject_Merges()
    {
        using var factory = new WebTestFactory();
        var client = factory.CreateClient();
        await SeedAsync(factory, ArchiveSeed());

        (await PostAsync(client, """{ "cycleAudioArchive": { "mode": "off" } }""")).StatusCode
            .Should().Be(HttpStatusCode.OK);

        var a = JsonNode.Parse(await GetConfigJsonAsync(client))!["cycleAudioArchive"]!;
        a["mode"]!.GetValue<string>().Should().Be("off");
        a["directory"]!.GetValue<string>().Should().Be("X");
        a["maxSizeMb"]!.GetValue<int>().Should().Be(999);
        a["maxAgeHours"]!.GetValue<int>().Should().Be(9);
        a["writeManifest"]!.GetValue<bool>().Should().BeFalse();
    }

    // ── T4 ──────────────────────────────────────────────────────────────────

    [Fact(DisplayName = "T4: POST {} against a config whose every leaf is non-default changes nothing (reflection-enumerated)")]
    public async Task T4_EmptyBody_ChangesNothing()
    {
        using var factory = new WebTestFactory();
        var client = factory.CreateClient();
        var seed = NonDefaultConfig.Build();
        await SeedAsync(factory, seed);

        var before = await GetConfigJsonAsync(client);

        // Guard the fixture itself: it must really differ from the defaults everywhere, or the
        // test proves nothing (HK-022). Every property of AppConfig and of every non-null section
        // record must have moved.
        AssertEveryLeafIsNonDefault(JsonNode.Parse(before)!, JsonNode.Parse(
            JsonSerializer.Serialize(new AppConfig(), Web))!, "");

        var resp = await PostAsync(client, "{}");
        resp.StatusCode.Should().Be(HttpStatusCode.OK);

        (await GetConfigJsonAsync(client)).Should().Be(before);
    }

    private static void AssertEveryLeafIsNonDefault(JsonNode stored, JsonNode defaults, string path)
    {
        if (stored is JsonObject so)
        {
            foreach (var (k, v) in so)
            {
                var d = (defaults as JsonObject)?[k];
                if (v is JsonObject && d is null)
                {
                    // Nullable section (cat/tx/decoder): compare against a default instance of it.
                    var def = k switch
                    {
                        "cat"     => JsonSerializer.Serialize(new CatConfig(), Web),
                        "tx"      => JsonSerializer.Serialize(new TxConfig(), Web),
                        "decoder" => JsonSerializer.Serialize(new DecoderConfig(), Web),
                        _         => throw new InvalidOperationException($"unexpected nullable section '{k}'"),
                    };
                    AssertEveryLeafIsNonDefault(v, JsonNode.Parse(def)!, $"{path}{k}.");
                    continue;
                }
                if (v is null)
                {
                    // a stored null is a "default-equal" leaf unless the default is non-null
                    d.Should().NotBeNull($"leaf {path}{k} must differ from its default");
                    continue;
                }
                AssertEveryLeafIsNonDefault(v, d ?? new JsonObject(), $"{path}{k}.");
            }
            return;
        }
        (stored.ToJsonString() != (defaults?.ToJsonString() ?? "null"))
            .Should().BeTrue($"leaf {path.TrimEnd('.')} must be non-default in the T4 fixture");
    }

    // ── T5 ──────────────────────────────────────────────────────────────────

    [Fact(DisplayName = "T5: a Settings-shaped save with the stored values leaves every leaf unchanged, including the ones it never sends")]
    public async Task T5_SettingsShapedSave_LeavesUnsentLeavesUnchanged()
    {
        using var factory = new WebTestFactory();
        var client = factory.CreateClient();
        await SeedAsync(factory, NonDefaultConfig.Build());

        var before = await GetConfigJsonAsync(client);
        var body   = SettingsPayload.BodyFrom(JsonNode.Parse(before)!, includeArchive: false);

        (await PostAsync(client, body.ToJsonString())).StatusCode.Should().Be(HttpStatusCode.OK);

        (await GetConfigJsonAsync(client)).Should().Be(before);
    }

    // ── T6 ──────────────────────────────────────────────────────────────────

    [Fact(DisplayName = "T6: decodingEnabled=false survives a Settings-shaped save and no save ever reports true (no pipeline start)")]
    public async Task T6_DecodingDisabled_SurvivesSettingsSave()
    {
        using var factory = new WebTestFactory();
        var client = factory.CreateClient();
        await SeedAsync(factory, new AppConfig { DecodingEnabled = false });

        var store = factory.Services.GetRequiredService<IConfigStore>();
        var seenEnabled = new List<bool>();
        store.OnSaved += c => seenEnabled.Add(c.DecodingEnabled);

        var stored = JsonNode.Parse(await GetConfigJsonAsync(client))!;
        var body   = SettingsPayload.BodyFrom(stored, includeArchive: false);
        (await PostAsync(client, body.ToJsonString())).StatusCode.Should().Be(HttpStatusCode.OK);

        JsonNode.Parse(await GetConfigJsonAsync(client))!["decodingEnabled"]!.GetValue<bool>().Should().BeFalse();
        seenEnabled.Should().NotBeEmpty().And.OnlyContain(v => v == false,
            "the daemon starts the pipeline on a false→true DecodingEnabled transition; a save must never cause one");
    }

    // ── T7 ──────────────────────────────────────────────────────────────────

    [Fact(DisplayName = "T7: tx runtime state (held TX frequency, offsets, autoAnswer, retained ADIF fields) survives a Settings-shaped save")]
    public async Task T7_TxRuntimeState_SurvivesSettingsSave()
    {
        using var factory = new WebTestFactory();
        var client = factory.CreateClient();
        await SeedAsync(factory, new AppConfig
        {
            Tx = new TxConfig(
                autoAnswer: true, holdTxFreq: true, txAudioOffsetHz: 1234, rxAudioOffsetHz: 1777,
                retainedTxPower: "50", retainedComment: "rc", retainedPropMode: "F2"),
        });

        var stored = JsonNode.Parse(await GetConfigJsonAsync(client))!;
        var body   = SettingsPayload.BodyFrom(stored, includeArchive: false);
        (await PostAsync(client, body.ToJsonString())).StatusCode.Should().Be(HttpStatusCode.OK);

        var tx = JsonNode.Parse(await GetConfigJsonAsync(client))!["tx"]!;
        tx["autoAnswer"]!.GetValue<bool>().Should().BeTrue();
        tx["holdTxFreq"]!.GetValue<bool>().Should().BeTrue();
        tx["txAudioOffsetHz"]!.GetValue<int>().Should().Be(1234);
        tx["rxAudioOffsetHz"]!.GetValue<int>().Should().Be(1777);
        tx["retainedTxPower"]!.GetValue<string>().Should().Be("50");
        tx["retainedComment"]!.GetValue<string>().Should().Be("rc");
        tx["retainedPropMode"]!.GetValue<string>().Should().Be("F2");
    }

    // ── T8 ──────────────────────────────────────────────────────────────────

    [Theory(DisplayName = "T8: an explicit null on a non-nullable section keeps the stored section")]
    [InlineData("logging")]
    [InlineData("decodeLog")]
    [InlineData("ptt")]
    [InlineData("remoteAccess")]
    [InlineData("decodeNoiseSuppression")]
    [InlineData("externalReporting")]
    [InlineData("cycleAudioArchive")]
    public async Task T8_ExplicitNullOnNonNullableSection_KeepsStored(string section)
    {
        using var factory = new WebTestFactory();
        var client = factory.CreateClient();
        await SeedAsync(factory, NonDefaultConfig.Build());
        var before = JsonNode.Parse(await GetConfigJsonAsync(client))!;

        (await PostAsync(client, $$"""{ "{{section}}": null }""")).StatusCode.Should().Be(HttpStatusCode.OK);

        var after = JsonNode.Parse(await GetConfigJsonAsync(client))!;
        after[section].Should().NotBeNull($"{section} must never be null in GET /api/v1/config");
        after[section]!.ToJsonString().Should().Be(before[section]!.ToJsonString());
    }

    // ── T9 ──────────────────────────────────────────────────────────────────

    [Fact(DisplayName = "T9: explicit null on nullable fields is stored (remoteAccess.passphrase, suppressUnknownRegion)")]
    public async Task T9_ExplicitNullOnNullableField_IsStored()
    {
        using var factory = new WebTestFactory();
        var client = factory.CreateClient();
        await SeedAsync(factory, new AppConfig
        {
            RemoteAccess           = new RemoteAccessConfig(enabled: true, passphrase: "Q-secret"),
            DecodeNoiseSuppression = new DecodeNoiseSuppressionConfig(suppressUnknownRegion: true),
        });

        var resp = await PostAsync(client,
            """{ "remoteAccess": { "enabled": false, "passphrase": null }, "decodeNoiseSuppression": { "suppressUnknownRegion": null } }""");
        resp.StatusCode.Should().Be(HttpStatusCode.OK);

        var after = JsonNode.Parse(await GetConfigJsonAsync(client))!;
        after["remoteAccess"]!["enabled"]!.GetValue<bool>().Should().BeFalse();
        after["remoteAccess"]!["passphrase"].Should().BeNull("an explicit null on a nullable field is stored");
        after["decodeNoiseSuppression"]!["suppressUnknownRegion"].Should().BeNull();
    }

    // ── T10 ─────────────────────────────────────────────────────────────────

    [Theory(DisplayName = "T10: decoder.nhard40MigrationApplied is server-owned; the body cannot flip it")]
    [InlineData(true)]
    [InlineData(false)]
    public async Task T10_MigrationMarker_IsServerOwned(bool stored)
    {
        using var factory = new WebTestFactory();
        var client = factory.CreateClient();
        await SeedAsync(factory, new AppConfig { Decoder = new DecoderConfig(nhard40MigrationApplied: stored) });

        var opposite = (!stored).ToString().ToLowerInvariant();
        (await PostAsync(client, $$"""{ "decoder": { "kMinScorePass2": 10, "osdNhardMax": 40, "nhard40MigrationApplied": {{opposite}} } }"""))
            .StatusCode.Should().Be(HttpStatusCode.OK);

        JsonNode.Parse(await GetConfigJsonAsync(client))!["decoder"]!["nhard40MigrationApplied"]!
            .GetValue<bool>().Should().Be(stored);
    }

    // ── T11 ─────────────────────────────────────────────────────────────────

    [Fact(DisplayName = "T11: arrays replace, never element-merge (externalReporting.targets: [] empties a two-entry list)")]
    public async Task T11_Arrays_Replace()
    {
        using var factory = new WebTestFactory();
        var client = factory.CreateClient();
        await SeedAsync(factory, new AppConfig
        {
            ExternalReporting = new ExternalReportingConfig(targets:
            [
                new ExternalReportingTarget(name: "A", port: 2237),
                new ExternalReportingTarget(name: "B", port: 2238),
            ]),
        });

        (await PostAsync(client, """{ "externalReporting": { "targets": [] } }""")).StatusCode
            .Should().Be(HttpStatusCode.OK);

        JsonNode.Parse(await GetConfigJsonAsync(client))!["externalReporting"]!["targets"]!.AsArray()
            .Should().BeEmpty();
    }

    // ── T12 ─────────────────────────────────────────────────────────────────

    [Fact(DisplayName = "T12: validation runs on the merged config (stored follower + body leaderUrl \"\" → 400, store unchanged)")]
    public async Task T12_ValidationRunsOnMergedConfig()
    {
        using var factory = new WebTestFactory();
        var client = factory.CreateClient();
        await SeedAsync(factory, new AppConfig
        {
            ExternalReporting = new ExternalReportingConfig(
                enabled: true, role: "follower", leaderUrl: "http://192.0.2.1:8080"),
        });
        var before = await GetConfigJsonAsync(client);

        var resp = await PostAsync(client, """{ "externalReporting": { "leaderUrl": "" } }""");
        resp.StatusCode.Should().Be(HttpStatusCode.BadRequest);

        (await GetConfigJsonAsync(client)).Should().Be(before);
    }

    // ── Behaviours the overlay must keep (design D1) ────────────────────────

    [Fact(DisplayName = "D1: an explicit null on a non-nullable scalar is still a 400 (\"Malformed JSON.\"), not treated as absent")]
    public async Task ExplicitNullOnNonNullableScalar_Is400()
    {
        using var factory = new WebTestFactory();
        var client = factory.CreateClient();
        var before = await GetConfigJsonAsync(client);

        (await PostAsync(client, """{ "port": null }""")).StatusCode.Should().Be(HttpStatusCode.BadRequest);

        (await GetConfigJsonAsync(client)).Should().Be(before);
    }

    [Fact(DisplayName = "D1: a body with a nullable section object over a stored null uses the body object (defaults fill omitted keys)")]
    public async Task BodyObjectOverStoredNull_UsesBodyObject()
    {
        using var factory = new WebTestFactory();
        var client = factory.CreateClient();
        await SeedAsync(factory, new AppConfig()); // tx == null

        (await PostAsync(client, """{ "tx": { "callsign": "Q1XYZ" } }""")).StatusCode
            .Should().Be(HttpStatusCode.OK);

        var tx = JsonNode.Parse(await GetConfigJsonAsync(client))!["tx"]!;
        tx["callsign"]!.GetValue<string>().Should().Be("Q1XYZ");
        tx["retryCount"]!.GetValue<int>().Should().Be(3);
        tx["txAudioOffsetHz"]!.GetValue<int>().Should().Be(1500);
    }

    [Fact(DisplayName = "D1: an unknown key is ignored")]
    public async Task UnknownKey_IsIgnored()
    {
        using var factory = new WebTestFactory();
        var client = factory.CreateClient();
        var before = await GetConfigJsonAsync(client);

        (await PostAsync(client, """{ "noSuchKey": 1, "tx": { "noSuchKey": 2 } }""")).StatusCode
            .Should().Be(HttpStatusCode.OK);

        var after = JsonNode.Parse(await GetConfigJsonAsync(client))!;
        after["noSuchKey"].Should().BeNull();
        after["tx"]!["callsign"]!.GetValue<string>().Should().Be("Q1OFZ");
    }
}
