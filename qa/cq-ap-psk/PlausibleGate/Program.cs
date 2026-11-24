// Usage: PlausibleGate <publishDir> <grammarJsonCopy>   (stdin: one message per line; stdout: "1" or "0" per line)
// The grammar file must be a COPY: CallsignGrammarStore.LoadAsync writes defaults when the file is absent.
using System.Reflection;
using System.Runtime.Loader;

string pub = args[0];
string grammar = args[1];
AssemblyLoadContext.Default.Resolving += (ctx, name) =>
{
    string p = Path.Combine(pub, name.Name + ".dll");
    return File.Exists(p) ? ctx.LoadFromAssemblyPath(p) : null;
};
var ft8 = AssemblyLoadContext.Default.LoadFromAssemblyPath(Path.Combine(pub, "OpenWSFZ.Ft8.dll"));
var daemon = AssemblyLoadContext.Default.LoadFromAssemblyPath(Path.Combine(pub, "OpenWSFZ.Daemon.dll"));
var storeType = daemon.GetType("OpenWSFZ.Daemon.CallsignGrammarStore") ?? throw new Exception("store type not found");
var store = Activator.CreateInstance(storeType, grammar, null) ?? throw new Exception("store ctor");
await (Task)storeType.GetMethod("LoadAsync")!.Invoke(store, new object?[] { CancellationToken.None })!;
var dec = ft8.GetType("OpenWSFZ.Ft8.Ft8Decoder") ?? throw new Exception("Ft8Decoder not found");
var m = dec.GetMethod("IsPlausibleMessage", BindingFlags.NonPublic | BindingFlags.Static) ?? throw new Exception("IsPlausibleMessage not found");
string? line;
var o = new StreamWriter(Console.OpenStandardOutput()) { AutoFlush = true, NewLine = "\n" };
while ((line = Console.ReadLine()) != null)
    o.WriteLine(((bool)m.Invoke(null, new object?[] { line, store })!) ? "1" : "0");
