using OpenWSFZ.Abstractions;
using System.Text.Json;
using System.Text.Json.Nodes;

namespace OpenWSFZ.Web;

/// <summary>
/// Applies a <c>POST /api/v1/config</c> body as an <b>overlay</b> on the stored configuration
/// (config-save-preserves-unsent-settings, design D1; GitHub #193).
/// </summary>
/// <remarks>
/// <para>
/// Before this type the endpoint <i>replaced</i> the config: every key the body omitted came back
/// through System.Text.Json as its C# default, and the handler patched up a few fields one at a
/// time. That patch-up missed a field at least three times. The overlay is schema-agnostic: the
/// stored config is serialised to a <see cref="JsonNode"/>, the body is merged onto it, and the
/// result is deserialised, so a field added to <see cref="AppConfig"/> in future is protected
/// without anyone remembering a guard.
/// </para>
/// <para>Rules (the <c>configuration</c> spec's table):</para>
/// <list type="bullet">
///   <item>key absent, at any depth: the stored value is kept;</item>
///   <item>key present, JSON object, stored value an object: merged recursively;</item>
///   <item>key present, JSON object, stored value <c>null</c>: the body object is used as-is;</item>
///   <item>key present, scalar or array: replaces the stored value wholesale (arrays are never element-merged);</item>
///   <item>key present, explicit <c>null</c>, on a non-nullable top-level section: treated as absent;</item>
///   <item>key present, explicit <c>null</c>, anywhere else: stored as <c>null</c>. On a non-nullable
///         scalar that makes deserialisation throw, which the handler answers with 400 (today's behaviour);</item>
///   <item>unknown keys: ignored by the deserialiser.</item>
/// </list>
/// The server-owned <c>decoder.nhard40MigrationApplied</c> is <b>not</b> handled here: the handler
/// forces it from the store after deserialisation.
/// </remarks>
internal static class ConfigOverlay
{
    /// <summary>
    /// Top-level sections whose C# type is non-nullable, so an explicit JSON <c>null</c> for them means
    /// "unchanged". Listed by hand, deliberately <b>not</b> derived by reflection: a section added
    /// later as nullable must not silently become non-nullable (design D1). The
    /// <c>ConfigSaveOverlayTests</c> class test covers new fields.
    /// </summary>
    internal static readonly IReadOnlySet<string> NonNullableSections = new HashSet<string>(StringComparer.Ordinal)
    {
        "logging",
        "decodeLog",
        "ptt",
        "remoteAccess",
        "decodeNoiseSuppression",
        "externalReporting",
        "cycleAudioArchive",
    };

    /// <summary>
    /// Merges <paramref name="body"/> onto <paramref name="current"/> and deserialises the result.
    /// </summary>
    /// <exception cref="JsonException">The merged document does not deserialise (for example an
    /// explicit <c>null</c> on a non-nullable scalar such as <c>port</c>).</exception>
    /// <returns>The merged configuration; never <c>null</c>.</returns>
    internal static AppConfig Apply(AppConfig current, JsonObject body)
    {
        var merged = JsonSerializer.SerializeToNode(current, AppJsonContext.Default.AppConfig) as JsonObject
            ?? throw new JsonException("Stored configuration did not serialise to a JSON object.");

        Merge(merged, body, isTopLevel: true);

        var config = merged.Deserialize(AppJsonContext.Default.AppConfig)
            ?? throw new JsonException("Merged configuration deserialised to null.");

        // Defence in depth: the merge already keeps the stored section on an explicit null, so these
        // fallbacks can only fire if the STORE itself held a null. They use the STORED value, then a
        // fresh default only as a last resort — never a fresh default in preference to the store.
        return config with
        {
            Logging                = config.Logging                ?? current.Logging                ?? new LoggingConfig(),
            DecodeLog              = config.DecodeLog              ?? current.DecodeLog              ?? new DecodeLogConfig(),
            Ptt                    = config.Ptt                    ?? current.Ptt                    ?? new PttConfig(),
            RemoteAccess           = config.RemoteAccess           ?? current.RemoteAccess           ?? new RemoteAccessConfig(),
            DecodeNoiseSuppression = config.DecodeNoiseSuppression ?? current.DecodeNoiseSuppression ?? new DecodeNoiseSuppressionConfig(),
            ExternalReporting      = config.ExternalReporting      ?? current.ExternalReporting      ?? new ExternalReportingConfig(),
            CycleAudioArchive      = config.CycleAudioArchive      ?? current.CycleAudioArchive      ?? new CycleAudioArchiveConfig(),
        };
    }

    private static void Merge(JsonObject target, JsonObject patch, bool isTopLevel)
    {
        // Snapshot the keys: the loop mutates target.
        foreach (var (key, value) in patch.ToList())
        {
            if (value is null)
            {
                // Explicit null. Non-nullable top-level section: treated as absent.
                if (isTopLevel && NonNullableSections.Contains(key))
                    continue;
                target[key] = null;
                continue;
            }

            if (value is JsonObject patchObject && target[key] is JsonObject targetObject)
            {
                Merge(targetObject, patchObject, isTopLevel: false);
                continue;
            }

            // Scalar, array, or an object over a stored null: replaces wholesale.
            target[key] = value.DeepClone();
        }
    }
}
