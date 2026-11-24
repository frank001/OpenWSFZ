using System.Text;
using OpenWSFZ.Ft8;
using OpenWSFZ.Ft8.Interop;

// FD-PROXY N-RAND (spec 4.2): uniformly random 77-bit payloads -> the product's own unpacker (Ft8LibInterop.CohFallbackUnpack, the call the decoder itself
// makes for fallback rows) -> kept only if the product's own plausibility filter (Ft8Decoder.IsPlausibleMessage, grammar store = null = BuiltInDefault, exactly what the
// ON replay's harness decoder used) accepts it. Mode "ap" fixes the CQ field (c28 = 2, ipa = 0, i3 = 1) and draws the rest at random.
// HK-037: the accepted texts go to a working file under _qa-scratch ONLY (refused elsewhere); stdout carries counts, never text.
//   Ft8.FitProbe.exe --mode rand|ap --count N --seed S --max-tries M --out <path under _qa-scratch>
var a = new Dictionary<string, string>();
for (int i = 0; i + 1 < args.Length; i += 2) a[args[i].TrimStart('-')] = args[i + 1];
string mode = a["mode"]; int count = int.Parse(a["count"]); int seed = int.Parse(a["seed"]); long maxTries = long.Parse(a["max-tries"]); string outp = a["out"];
if (!outp.Replace((char)92, '/').Contains("/_qa-scratch/")) throw new ArgumentException("--out must be under _qa-scratch (HK-037)");
if (mode != "rand" && mode != "ap") throw new ArgumentException("mode");

static void SetBits(byte[] p, int start, int len, uint value)   // MSB-first, as the 77-bit payload is laid out
{
    for (int k = 0; k < len; k++)
    {
        int bit = start + k;
        bool one = ((value >> (len - 1 - k)) & 1u) != 0;
        if (one) p[bit / 8] |= (byte)(0x80 >> (bit % 8)); else p[bit / 8] &= (byte)~(0x80 >> (bit % 8));
    }
}

var rng = new Random(seed);
long tries = 0, unpackNull = 0, implausible = 0, accepted = 0;
using var w = new StreamWriter(outp, false, new UTF8Encoding(false));
var buf = new byte[10];
while (accepted < count && tries < maxTries)
{
    tries++;
    rng.NextBytes(buf);
    buf[9] &= 0xF8;                                  // 77 bits: the low 3 bits of byte 9 are not part of the payload
    if (mode == "ap")
    {
        SetBits(buf, 0, 28, 2u);                     // c28 = 2: "CQ"
        SetBits(buf, 28, 1, 0u);                     // ipa
        SetBits(buf, 74, 3, 1u);                     // i3 = 1: standard message
    }
    string? text = Ft8LibInterop.CohFallbackUnpack(buf);
    if (text is null) { unpackNull++; continue; }
    if (!Ft8Decoder.IsPlausibleMessage(text, null)) { implausible++; continue; }
    accepted++;
    w.WriteLine(text.TrimEnd());
}
Console.WriteLine($"mode={mode} seed={seed} tries={tries} unpackNull={unpackNull} implausible={implausible} accepted={accepted} passRate={(tries == 0 ? 0 : (double)accepted / tries):R}");
