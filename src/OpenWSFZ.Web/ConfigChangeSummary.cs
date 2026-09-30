using OpenWSFZ.Abstractions;
using System.Text.Json;
using System.Text.Json.Nodes;

namespace OpenWSFZ.Web;

/// <summary>
/// Builds the one-line "what did this save change" summary logged on every successful
/// <c>POST /api/v1/config</c> (config-save-preserves-unsent-settings, Part D).
/// </summary>
/// <remarks>
/// 🔒 NFR-021 / HK-037: only dotted <b>paths</b> are printed, plus the value of the six fields in
/// <see cref="ValueAllowlist"/> (enum or boolean, never personal). A callsign, a passphrase, a host or a
/// directory path can therefore never reach the log through this line, whatever changed. The allowlist
/// is explicit code, not a "looks harmless" heuristic: a new field is path-only until someone adds it
/// here on purpose.
/// </remarks>
internal static class ConfigChangeSummary
{
    /// <summary>Fields whose old and new value are printed. Everything else is path only.</summary>
    internal static readonly IReadOnlyDictionary<string, Func<AppConfig, string>> ValueAllowlist =
        new Dictionary<string, Func<AppConfig, string>>(StringComparer.Ordinal)
        {
            ["cycleAudioArchive.mode"] = c => c.CycleAudioArchive.Mode.ToString(),
            ["decodingEnabled"]        = c => Bool(c.DecodingEnabled),
            ["tx.autoAnswer"]          = c => c.Tx is null ? "unset" : Bool(c.Tx.AutoAnswer),
            ["tx.holdTxFreq"]          = c => c.Tx is null ? "unset" : Bool(c.Tx.HoldTxFreq),
            ["cat.enabled"]            = c => c.Cat is null ? "unset" : Bool(c.Cat.Enabled),
            ["remoteAccess.enabled"]   = c => Bool(c.RemoteAccess.Enabled),
        };

    private static string Bool(bool value) => value ? "true" : "false";

    /// <summary>The text after <c>Config saved via API: </c>.</summary>
    internal static string Describe(AppConfig before, AppConfig after)
    {
        var a = Leaves(before);
        var b = Leaves(after);

        var changed = a.Keys.Union(b.Keys, StringComparer.Ordinal)
            .Where(path => !a.TryGetValue(path, out var x) || !b.TryGetValue(path, out var y) || x != y)
            .OrderBy(path => path, StringComparer.Ordinal)
            .Select(path => ValueAllowlist.TryGetValue(path, out var read)
                ? $"{path} ({read(before)}→{read(after)})"
                : path)
            .ToList();

        return changed.Count == 0 ? "no changes" : "changed " + string.Join(", ", changed);
    }

    /// <summary>Flattens a config to dotted-path → canonical JSON text. Arrays are single leaves.</summary>
    private static Dictionary<string, string> Leaves(AppConfig config)
    {
        var leaves = new Dictionary<string, string>(StringComparer.Ordinal);
        if (JsonSerializer.SerializeToNode(config, AppJsonContext.Default.AppConfig) is JsonObject root)
            Walk(root, "", leaves);
        return leaves;
    }

    private static void Walk(JsonObject node, string prefix, Dictionary<string, string> leaves)
    {
        foreach (var (key, value) in node)
        {
            var path = prefix + key;
            if (value is JsonObject child)
                Walk(child, path + ".", leaves);
            else
                leaves[path] = value?.ToJsonString() ?? "null";
        }
    }
}
