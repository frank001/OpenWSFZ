#!/usr/bin/env python
"""QA's OWN numeric-literal lister for S1-f(ii). Independent of the Developer's litscan.py.
Reads C source from `git show <ref>:<path>` (never the working tree), strips comments/strings/char
literals (preserving line numbers), tokenises numeric literals, and prints one line per source line
that holds >=1 literal, tagged with the enclosing function.  NOTHING is filtered (0 and 1 included).
Usage: python qalit.py REF PATH [PATH...]
"""
import re
import subprocess
import sys

NUM = re.compile(r"(?<![A-Za-z_0-9.])(0[xX][0-9A-Fa-f]+[uUlL]*|(?:\d+\.\d*|\.\d+)(?:[eE][+-]?\d+)?[fFlL]?|\d+[eE][+-]?\d+[fFlL]?|\d+[uUlL]*)(?![A-Za-z_0-9])")
FUNC = re.compile(r"^[A-Za-z_][\w \*\t]*?\b([A-Za-z_]\w*)\s*\([^;]*$")


def strip(src):
    out, i, n = [], 0, len(src)
    while i < n:
        if src.startswith("/*", i):
            j = src.find("*/", i + 2); j = n if j < 0 else j + 2
            out.append("".join("\n" if c == "\n" else " " for c in src[i:j])); i = j
        elif src.startswith("//", i):
            j = src.find("\n", i); j = n if j < 0 else j
            out.append(" " * (j - i)); i = j
        elif src[i] in "\"'":
            q = src[i]; j = i + 1
            while j < n and src[j] != q:
                j += 2 if src[j] == "\\" else 1
            out.append(q + " " * (j - i - 1) + q); i = j + 1
        else:
            out.append(src[i]); i += 1
    return "".join(out)


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ref, paths = sys.argv[1], sys.argv[2:]
    for p in paths:
        raw = subprocess.run(["git", "show", "%s:%s" % (ref, p)], capture_output=True, check=True).stdout.decode("utf-8", "replace")
        clean = strip(raw)
        rl, cl = raw.split("\n"), clean.split("\n")
        func, depth = "<file>", 0
        for i, (r, c) in enumerate(zip(rl, cl), 1):
            if depth == 0:
                m = FUNC.match(c)
                if m and not c.lstrip().startswith("#") and "=" not in c.split("(")[0]:
                    func = m.group(1)
            depth += c.count("{") - c.count("}")
            if c.lstrip().startswith("#include"):
                continue
            lits = [m.group(1) for m in NUM.finditer(c)]
            if lits:
                print("%s:%d [%s] %s | %s" % (p.split("/")[-1], i, func, ",".join(lits), r.strip()[:150]))


if __name__ == "__main__":
    main()
