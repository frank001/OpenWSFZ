using System.Reflection;
using System.Text.Json;
using System.Text.Json.Serialization;
using FluentAssertions;
using OpenWSFZ.Abstractions;
using Xunit;

namespace OpenWSFZ.Config.Tests;

/// <summary>
/// Regression tests for issue #209: a key absent from a PRESENT config section must read the
/// documented default, never <c>default(T)</c>. System.Text.Json's source generator bypasses
/// property initialisers on records that lack a <c>[JsonConstructor]</c>.
/// </summary>
[Trait("Category", "Unit")]
public sealed class ConfigAbsentKeyTests
{
    private sealed class TempDirectory : IDisposable
    {
        public string Path { get; } = System.IO.Path.Combine(
            System.IO.Path.GetTempPath(), "openwsfz-absentkey-" + System.IO.Path.GetRandomFileName());

        public TempDirectory() => Directory.CreateDirectory(Path);

        public void Dispose()
        {
            try { Directory.Delete(Path, recursive: true); } catch { /* best-effort */ }
        }
    }

    /// <summary>Every config record registered in <see cref="ConfigJsonContext"/>, by reflection.</summary>
    public static IEnumerable<object[]> RegisteredRecordTypes() =>
        typeof(ConfigJsonContext)
            .GetCustomAttributesData()
            .Where(a => a.AttributeType == typeof(JsonSerializableAttribute))
            .Select(a => (Type)a.ConstructorArguments[0].Value!)
            .Where(t => t.IsClass && t != typeof(AppConfig))   // AppConfig: asserted through the store
            .OrderBy(t => t.Name, StringComparer.Ordinal)
            .Select(t => new object[] { t });

    private static string ToJson(object? value, Type type) =>
        JsonSerializer.Serialize(value, ConfigJsonContext.Default.GetTypeInfo(type)!);

    /// <summary>A default-constructed instance: the constructor whose parameters are all optional.</summary>
    private static object? DefaultInstance(Type type)
    {
        var ctor = type.GetConstructors(BindingFlags.Public | BindingFlags.Instance)
            .Where(c => c.GetParameters().All(q => q.IsOptional))
            .OrderByDescending(c => c.GetParameters().Length)
            .First();
        return ctor.Invoke(
            BindingFlags.OptionalParamBinding, binder: null,
            parameters: ctor.GetParameters().Select(_ => Type.Missing).ToArray(), culture: null);
    }

    [Theory(DisplayName = "FR-031/FR-056/FR-028: every registered config record deserialises an empty object to its default instance")]
    [MemberData(nameof(RegisteredRecordTypes))]
    public void ConfigRecord_EmptyObject_EqualsDefaultInstance(Type type)
    {
        var fromJson = JsonSerializer.Deserialize("{}", ConfigJsonContext.Default.GetTypeInfo(type)!);
        var expected = DefaultInstance(type);

        fromJson.Should().NotBeNull();
        expected.Should().NotBeNull();

        foreach (var p in type.GetProperties(BindingFlags.Public | BindingFlags.Instance)
                              .Where(p => p.CanRead && p.GetIndexParameters().Length == 0))
        {
            var got  = JsonSerializer.Serialize(p.GetValue(fromJson),  p.PropertyType, ConfigJsonContext.Default.Options);
            var want = JsonSerializer.Serialize(p.GetValue(expected), p.PropertyType, ConfigJsonContext.Default.Options);
            got.Should().Be(want, $"{type.Name}.{p.Name} must read its default for an absent key");
        }
    }

    [Fact(DisplayName = "FR-001: AppConfig empty file loads every config section non-null with its defaults")]
    public void Store_EmptyFile_AllSectionsDefault()
    {
        using var dir = new TempDirectory();
        var path = System.IO.Path.Combine(dir.Path, "config.json");
        File.WriteAllText(path, "{}");

        var loaded = new JsonConfigStore(path).Current;
        var nullability = new NullabilityInfoContext();
        var checkedSections = 0;

        foreach (var p in typeof(AppConfig).GetProperties(BindingFlags.Public | BindingFlags.Instance))
        {
            if (!p.PropertyType.IsClass || p.PropertyType == typeof(string)) continue;
            if (ConfigJsonContext.Default.GetTypeInfo(p.PropertyType) is null) continue;
            if (nullability.Create(p).WriteState == NullabilityState.Nullable) continue;

            var got = p.GetValue(loaded);
            got.Should().NotBeNull($"AppConfig.{p.Name} must be guarded by the store");
            ToJson(got, p.PropertyType).Should().Be(ToJson(DefaultInstance(p.PropertyType), p.PropertyType),
                $"AppConfig.{p.Name}");
            checkedSections++;
        }

        checkedSections.Should().BeGreaterThan(5, "the loop must actually have covered the config sections");
    }

    private static AppConfig LoadStored(string json)
    {
        using var dir = new TempDirectory();
        var path = System.IO.Path.Combine(dir.Path, "config.json");
        File.WriteAllText(path, json);
        return new JsonConfigStore(path).Current;
    }

    [Fact(DisplayName = "FR-056: stored ptt section naming only method keeps the documented defaults for every other key")]
    public void Store_PartialPttSection_UsesDefaults()
    {
        var ptt = LoadStored("""{"ptt":{"method":"SerialRtsDtr"}}""").Ptt!;

        ptt.Method.Should().Be("SerialRtsDtr");
        ptt.SerialPort.Should().Be(new PttConfig().SerialPort).And.NotBeNullOrEmpty();
        ptt.SerialLine.Should().Be("Rts");
        ptt.LeadTimeMs.Should().Be(50);
        ptt.TailTimeMs.Should().Be(50);
        ptt.WatchdogTimeoutMs.Should().Be(20000);
    }

    [Fact(DisplayName = "FR-056: an explicit ptt value that is named is kept as written, including 0")]
    public void Store_ExplicitPttValues_AreRespected()
    {
        var ptt = LoadStored("""{"ptt":{"watchdogTimeoutMs":0,"leadTimeMs":0,"serialLine":null}}""").Ptt!;

        ptt.WatchdogTimeoutMs.Should().Be(0);
        ptt.LeadTimeMs.Should().Be(0);
        ptt.SerialLine.Should().BeNull("an explicit null that is named is the operator's value");
        ptt.TailTimeMs.Should().Be(50, "the unnamed key keeps its default");
    }

    [Fact(DisplayName = "FR-031: stored cat section naming only enabled keeps the documented defaults for every other key")]
    public void Store_PartialCatSection_UsesDefaults()
    {
        var cat = LoadStored("""{"cat":{"enabled":true}}""").Cat!;

        cat.Enabled.Should().BeTrue();
        cat.RigModel.Should().Be("SerialCat");
        cat.SerialPort.Should().Be(new CatConfig().SerialPort).And.NotBeNullOrEmpty();
        cat.BaudRate.Should().Be(9600);
        cat.RigctldHost.Should().Be("127.0.0.1");
        cat.RigctldPort.Should().Be(4532);
        cat.PollIntervalSeconds.Should().Be(1);
        cat.LastPolledFrequencyMHz.Should().BeNull();
    }

    [Fact(DisplayName = "FR-031: an explicit cat value that is named is kept as written")]
    public void Store_ExplicitCatValues_AreRespected()
    {
        var cat = LoadStored("""{"cat":{"baudRate":0,"rigctldHost":null,"lastPolledFrequencyMHz":7.074}}""").Cat!;

        cat.BaudRate.Should().Be(0);
        cat.RigctldHost.Should().BeNull();
        cat.LastPolledFrequencyMHz.Should().Be(7.074);
        cat.RigctldPort.Should().Be(4532, "the unnamed key keeps its default");
    }

    [Fact(DisplayName = "FR-056/FR-031: an explicit null serialPort on Ptt and Cat loads as the platform default, the one documented exception")]
    public void Store_ExplicitNullSerialPort_LoadsAsPlatformDefault()
    {
        var loaded = LoadStored("""{"ptt":{"serialPort":null},"cat":{"serialPort":null}}""");

        loaded.Ptt!.SerialPort.Should().Be(new PttConfig().SerialPort).And.NotBeNullOrEmpty(
            "the platform default cannot be a constant parameter default, so null resolves to it");
        loaded.Cat!.SerialPort.Should().Be(new CatConfig().SerialPort).And.NotBeNullOrEmpty();
    }

    [Fact(DisplayName = "FR-028: stored decodeLog section naming only enabled keeps the documented defaults")]
    public void Store_PartialDecodeLogSection_UsesDefaults()
    {
        var log = LoadStored("""{"decodeLog":{"enabled":true}}""").DecodeLog!;

        log.Enabled.Should().BeTrue();
        log.Path.Should().Be("ALL.TXT");
        log.DialFrequencyMHz.Should().Be(0.0);
    }

    [Fact(DisplayName = "FR-028: an explicit decodeLog value that is named is kept as written")]
    public void Store_ExplicitDecodeLogValues_AreRespected()
    {
        var log = LoadStored("""{"decodeLog":{"path":null,"dialFrequencyMHz":0}}""").DecodeLog!;

        log.Path.Should().BeNull();
        log.DialFrequencyMHz.Should().Be(0.0);
    }

    [Fact(DisplayName = "FR-031/FR-056/FR-028: a complete section round-trips to byte-identical JSON")]
    public void CompleteSections_RoundTrip_ByteIdentical()
    {
        var cat = new CatConfig { Enabled = true, RigModel = "RigCtld", SerialPort = "COM9", BaudRate = 38400,
                                  RigctldHost = "10.0.0.5", RigctldPort = 4533, PollIntervalSeconds = 5,
                                  LastPolledFrequencyMHz = 14.074 };
        var ptt = new PttConfig { Method = "CatCommand", SerialPort = "COM3", SerialLine = "Dtr",
                                  LeadTimeMs = 80, TailTimeMs = 90, WatchdogTimeoutMs = 15000 };
        var log = new DecodeLogConfig { Enabled = true, Path = "x.txt", DialFrequencyMHz = 7.074 };

        foreach (var (value, type) in new (object, Type)[]
                 { (cat, typeof(CatConfig)), (ptt, typeof(PttConfig)), (log, typeof(DecodeLogConfig)) })
        {
            var first = ToJson(value, type);
            var again = ToJson(JsonSerializer.Deserialize(first, ConfigJsonContext.Default.GetTypeInfo(type)!), type);
            again.Should().Be(first, type.Name);
        }
    }
}
