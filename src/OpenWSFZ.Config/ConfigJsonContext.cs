using System.Text.Json.Serialization;
using OpenWSFZ.Abstractions;

namespace OpenWSFZ.Config;

/// <summary>
/// Source-generated JSON serialisation context for the config subsystem.
/// Required for AOT compatibility — no reflection at runtime.
/// Uses camelCase to match the REST API wire format.
/// </summary>
[JsonSourceGenerationOptions(
    PropertyNamingPolicy         = JsonKnownNamingPolicy.CamelCase,
    WriteIndented                = true,
    DefaultIgnoreCondition       = JsonIgnoreCondition.Never)]
[JsonSerializable(typeof(AppConfig))]
[JsonSerializable(typeof(LoggingConfig))]
[JsonSerializable(typeof(DecodeLogConfig))]
[JsonSerializable(typeof(CatConfig))]
[JsonSerializable(typeof(TxConfig))]
[JsonSerializable(typeof(RemoteAccessConfig))]
[JsonSerializable(typeof(DecoderConfig))]
public sealed partial class ConfigJsonContext : JsonSerializerContext { }
