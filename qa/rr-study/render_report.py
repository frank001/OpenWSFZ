"""render_report.py — Convert an R&R study report.md to an HTML page.

Usage
-----
    python render_report.py [path/to/report.md]

    If no path is given, the most recently modified report.md under
    qa/rr-study/results/ is rendered automatically.

Output
------
    report.html written alongside the source report.md.

Images are referenced by relative path (not embedded), so the HTML file
must remain in the same directory as the PNG charts to display correctly.

Visual style replicates GitHub's dark-mode Markdown rendering — the same
appearance as opening a .md file on github.com with the GitHub Dark theme.
"""

from __future__ import annotations

import re
import sys
import subprocess
from pathlib import Path

# Windows consoles default to cp1252 which cannot encode some Unicode
# characters.  Reconfigure stdout/stderr to UTF-8 before any output.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# ---------------------------------------------------------------------------
# Bootstrap: ensure 'markdown' is installed in the active interpreter
# ---------------------------------------------------------------------------
try:
    import markdown as _md_pkg  # noqa: F401
except ModuleNotFoundError:
    print("'markdown' package not found — installing into current environment …",
          flush=True)
    subprocess.check_call([sys.executable, "-m", "pip", "install", "markdown"])
    import markdown as _md_pkg  # noqa: F401

import markdown

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).resolve().parent          # qa/rr-study/
PROJ_ROOT  = SCRIPT_DIR.parent.parent                 # repo root


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def find_latest_report() -> Path:
    """Return the most recently modified report.md under results/."""
    results = SCRIPT_DIR / "results"
    candidates = sorted(
        results.rglob("report.md"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not candidates:
        raise FileNotFoundError(f"No report.md found under {results}")
    return candidates[0]


def get_pygments_css() -> str:
    """Return Pygments CSS for syntax highlighting, using the best available dark style."""
    try:
        from pygments.formatters import HtmlFormatter
        for style in ("github-dark", "one-dark", "monokai", "dracula", "native"):
            try:
                return HtmlFormatter(style=style).get_style_defs(".highlight")
            except Exception:
                continue
    except ImportError:
        pass
    return ""


def build_html(body: str, page_title: str, pygments_css: str) -> str:
    """Wrap the rendered body in a GitHub Dark themed HTML shell."""

    return f"""\
<!DOCTYPE html>
<html lang="en" data-color-mode="dark">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{page_title}</title>
  <style>
/* ================================================================
   GitHub Dark palette  (mirrors github.com dark-mode variables)
   ================================================================ */
:root {{
  --color-canvas-default:  #0d1117;
  --color-canvas-subtle:   #161b22;
  --color-canvas-inset:    #010409;
  --color-fg-default:      #e6edf3;
  --color-fg-muted:        #848d97;
  --color-fg-subtle:       #6e7681;
  --color-border-default:  #30363d;
  --color-border-muted:    #21262d;
  --color-accent-fg:       #58a6ff;
  --color-success-fg:      #3fb950;
  --color-danger-fg:       #f85149;
  --color-attention-fg:    #d29922;
  --color-done-fg:         #a371f7;
  --color-neutral-muted:   rgba(110,118,129,0.4);
  --font-sans: -apple-system, BlinkMacSystemFont, "Segoe UI", "Noto Sans",
               Helvetica, Arial, sans-serif, "Apple Color Emoji", "Segoe UI Emoji";
  --font-mono: ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas,
               "Liberation Mono", monospace;
}}

*, *::before, *::after {{ box-sizing: border-box; }}

html {{
  font-size: 16px;
  scroll-behavior: smooth;
  -webkit-text-size-adjust: 100%;
}}

body {{
  background-color: var(--color-canvas-default);
  color: var(--color-fg-default);
  font-family: var(--font-sans);
  font-size: 1rem;
  line-height: 1.6;
  margin: 0;
  padding: 0;
  word-wrap: break-word;
}}

/* ── Layout ─────────────────────────────────────────────────────── */
.markdown-body {{
  max-width: 980px;
  margin: 0 auto;
  padding: 45px;
}}
@media (max-width: 767px) {{
  .markdown-body {{ padding: 15px; }}
}}

/* ── Headings ────────────────────────────────────────────────────── */
.markdown-body h1,
.markdown-body h2,
.markdown-body h3,
.markdown-body h4,
.markdown-body h5,
.markdown-body h6 {{
  margin-top: 24px;
  margin-bottom: 16px;
  font-weight: 600;
  line-height: 1.25;
  color: var(--color-fg-default);
}}
.markdown-body h1 {{
  font-size: 2em;
  padding-bottom: .3em;
  border-bottom: 1px solid var(--color-border-muted);
}}
.markdown-body h2 {{
  font-size: 1.5em;
  padding-bottom: .3em;
  border-bottom: 1px solid var(--color-border-muted);
}}
.markdown-body h3 {{ font-size: 1.25em; }}
.markdown-body h4 {{ font-size: 1em;    }}
.markdown-body h5 {{ font-size: .875em; }}
.markdown-body h6 {{ font-size: .85em;  color: var(--color-fg-muted); }}

/* ── Paragraphs & inline ─────────────────────────────────────────── */
.markdown-body p {{
  margin-top: 0;
  margin-bottom: 16px;
}}
.markdown-body a {{
  color: var(--color-accent-fg);
  text-decoration: none;
  background-color: transparent;
}}
.markdown-body a:hover {{ text-decoration: underline; }}
.markdown-body strong {{ font-weight: 600; }}
.markdown-body em     {{ font-style: italic; }}
.markdown-body del    {{ text-decoration: line-through; color: var(--color-fg-muted); }}

/* ── Horizontal rule ─────────────────────────────────────────────── */
.markdown-body hr {{
  border: 0;
  border-top: 1px solid var(--color-border-default);
  height: 0;
  margin: 24px 0;
  overflow: hidden;
  padding: 0;
}}

/* ── Images ──────────────────────────────────────────────────────── */
.markdown-body img {{
  max-width: 100%;
  height: auto;
  display: block;
  margin: 20px auto;
  border-radius: 6px;
  background-color: var(--color-canvas-subtle);
  box-shadow: 0 0 0 1px var(--color-border-muted);
}}

/* ── Blockquotes ─────────────────────────────────────────────────── */
.markdown-body blockquote {{
  border-left: .25em solid var(--color-border-default);
  color: var(--color-fg-muted);
  margin: 0 0 16px 0;
  padding: 0 1em;
}}
.markdown-body blockquote > :first-child {{ margin-top: 0; }}
.markdown-body blockquote > :last-child  {{ margin-bottom: 0; }}

/* ── Lists ───────────────────────────────────────────────────────── */
.markdown-body ul,
.markdown-body ol {{
  margin-top: 0;
  margin-bottom: 16px;
  padding-left: 2em;
}}
.markdown-body li {{ margin-top: .25em; }}
.markdown-body li + li {{ margin-top: .25em; }}
.markdown-body ul ul, .markdown-body ul ol,
.markdown-body ol ul, .markdown-body ol ol {{
  margin-top: 0;
  margin-bottom: 0;
}}

/* ── Inline code ─────────────────────────────────────────────────── */
.markdown-body code {{
  font-family: var(--font-mono);
  font-size: 85%;
  background: var(--color-neutral-muted);
  border-radius: 6px;
  padding: .2em .4em;
  margin: 0;
  white-space: break-spaces;
}}
/* Reset inside fenced blocks */
.markdown-body pre code {{
  background: transparent;
  border: 0;
  font-size: 100%;
  margin: 0;
  overflow: visible;
  overflow-wrap: normal;
  padding: 0;
  white-space: pre;
  word-break: normal;
  line-height: inherit;
}}

/* ── Code blocks ─────────────────────────────────────────────────── */
.markdown-body pre {{
  background: var(--color-canvas-subtle);
  border: 1px solid var(--color-border-default);
  border-radius: 6px;
  font-family: var(--font-mono);
  font-size: 85%;
  line-height: 1.45;
  margin-bottom: 16px;
  margin-top: 0;
  overflow: auto;
  padding: 16px;
  tab-size: 4;
  word-wrap: normal;
}}

/* ── Tables ──────────────────────────────────────────────────────── */
.markdown-body table {{
  border-collapse: collapse;
  border-spacing: 0;
  display: block;
  font-size: 14px;
  margin-bottom: 16px;
  margin-top: 0;
  max-width: 100%;
  overflow: auto;
  width: max-content;
}}
.markdown-body table th {{
  font-weight: 600;
}}
.markdown-body table th,
.markdown-body table td {{
  border: 1px solid var(--color-border-default);
  padding: 6px 13px;
  text-align: left;
  vertical-align: top;
}}
.markdown-body table thead tr {{
  background-color: var(--color-canvas-subtle);
  border-top: 1px solid var(--color-border-muted);
}}
.markdown-body table tbody tr:nth-child(even) {{
  background-color: var(--color-canvas-subtle);
}}

/* ── Verdict badge colours (applied by JS below) ─────────────────── */
.verdict-pass     {{ color: var(--color-success-fg);   font-weight: 600; }}
.verdict-fail     {{ color: var(--color-danger-fg);    font-weight: 600; }}
.verdict-marginal {{ color: var(--color-attention-fg); font-weight: 600; }}
.verdict-info     {{ color: var(--color-fg-muted);     font-weight: 600; }}

/* ── Syntax highlighting (Pygments, overrides for dark canvas) ───── */
.highlight {{
  background: var(--color-canvas-subtle) !important;
  border-radius: 6px;
  overflow: auto;
}}
.highlight pre {{ background: transparent; border: none; margin: 0; }}
{pygments_css}
  </style>
</head>
<body>
  <div class="markdown-body">
{body}
  </div>
  <script>
    // Colour verdict cells: PASS / FAIL / MARGINAL / informational
    document.querySelectorAll('td, th').forEach(function (cell) {{
      var t = cell.textContent.trim();
      if (/^(PASS|✅)$/.test(t)) {{
        cell.classList.add('verdict-pass');
      }} else if (/^(FAIL|❌)$/.test(t)) {{
        cell.classList.add('verdict-fail');
      }} else if (/MARGINAL|ABOVE BAND|⚠/.test(t)) {{
        cell.classList.add('verdict-marginal');
      }} else if (/^informational$/i.test(t)) {{
        cell.classList.add('verdict-info');
      }}
    }});
  </script>
</body>
</html>"""


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    # ── Resolve input path ──────────────────────────────────────────────────
    if len(sys.argv) > 1:
        report_path = Path(sys.argv[1]).resolve()
    else:
        report_path = find_latest_report()

    if not report_path.exists():
        sys.exit(f"ERROR: {report_path} does not exist")

    report_dir  = report_path.parent
    output_path = report_dir / "report.html"

    try:
        display_in = report_path.relative_to(PROJ_ROOT)
    except ValueError:
        display_in = report_path

    print(f"Rendering: {display_in}")

    # ── Load Markdown ───────────────────────────────────────────────────────
    md_text = report_path.read_text(encoding="utf-8")

    # ── Convert Markdown → HTML ─────────────────────────────────────────────
    extensions = [
        "tables",
        "fenced_code",
        "codehilite",
        "toc",
        "sane_lists",
        "attr_list",
    ]
    ext_config = {
        "codehilite": {"css_class": "highlight", "guess_lang": False},
        "toc":        {"title": ""},
    }
    converter = markdown.Markdown(extensions=extensions, extension_configs=ext_config)
    body      = converter.convert(md_text)

    # ── Page title from first H1 ────────────────────────────────────────────
    h1_match   = re.search(r"<h1[^>]*>(.*?)</h1>", body, re.S | re.I)
    page_title = re.sub(r"<[^>]+>", "", h1_match.group(1)).strip() \
                 if h1_match else "R&R Study Report"

    # ── Build & write HTML ──────────────────────────────────────────────────
    html = build_html(body, page_title, get_pygments_css())
    output_path.write_text(html, encoding="utf-8")

    try:
        display_out = output_path.relative_to(PROJ_ROOT)
    except ValueError:
        display_out = output_path

    print(f"Written  → {display_out}")


if __name__ == "__main__":
    main()
