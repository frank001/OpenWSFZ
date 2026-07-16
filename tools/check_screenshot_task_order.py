#!/usr/bin/env python3
"""
check_screenshot_task_order.py — flag tasks.md/dev-tasks files that violate
HK-005's before/after screenshot ordering rule.

Usage:
  python3 tools/check_screenshot_task_order.py [path ...]

  With no arguments, scans every openspec/changes/*/tasks.md and every
  dev-tasks/*.md in the repository. With explicit paths, scans only those.

Background (HK-005, see the QA memory note this script exists to satisfy):
`decode-status-control-merge/tasks.md` originally placed a single trailing
"Take a before/after screenshot" task after all implementation work, forcing
the developer to `git stash`/`stash pop` to reconstruct the pre-change state
the task list should have captured naturally in sequence. The rule going
forward: a "before" screenshot task must be one of the very first tasks in
the list (ahead of any implementation work), and the "after" half must come
later, once implementation is done — never a single combined task, never
"before" placed after implementation has already started.

This is a heuristic lint, not a perfect parser — markdown task lists don't
carry enough structure to mechanically prove "before implementation" in
every case. It flags the patterns that are unambiguous (a single task
mentioning both "before" and "after" screenshots; a "before" screenshot task
positioned after a task that is clearly implementation work) and warns on
anything it can't classify confidently, matching this project's existing
"best-effort automated flag augmenting human review" convention (see e.g.
NFR-019/SEC-003 in traceability-debt.md). A human still has to read the
result — this narrows what a human has to think about, it doesn't replace
them.

Exit codes
  0  no files scanned mention "screenshot" at all, or every screenshot
     mention that was found passed (WARN-only findings do not fail the run)
  1  at least one hard violation (combined task, or before-after-implementation
     ordering) was found in at least one file
  2  usage / no files found to scan
"""
import glob
import os
import re
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# A markdown task-list line: "- [ ] 3.1 <text>" or "- [x] 3.1 <text>".
# The leading "N.N" (or bare "N") is the task's own label — used only for
# display, not for ordering (ordering is by position in the file).
TASK_RE = re.compile(r"^-\s*\[( |x|X)\]\s*(?P<label>\S+)\s+(?P<text>.+)$")

# A section heading, e.g. "## 1. Requirements & Documentation".
HEADING_RE = re.compile(r"^#{1,6}\s+(?P<text>.+)$")

DOC_SECTION_RE = re.compile(r"requirements|documentation", re.IGNORECASE)


class Task:
    def __init__(self, index, label, text, section, line_no):
        self.index = index          # position among ALL tasks in the file, 0-based
        self.label = label
        self.text = text
        self.section = section      # the most recent heading text above this task
        self.line_no = line_no

    def __repr__(self):
        return f"{self.label} ({self.text[:60]!r})"


def _default_paths():
    paths = []
    paths += glob.glob(os.path.join(REPO_ROOT, "openspec", "changes", "*", "tasks.md"))
    paths += glob.glob(os.path.join(REPO_ROOT, "dev-tasks", "*.md"))
    return sorted(paths)


def _parse_tasks(path):
    tasks = []
    current_section = ""
    with open(path, "r", encoding="utf-8") as fh:
        for line_no, raw_line in enumerate(fh, start=1):
            line = raw_line.rstrip("\n")

            heading_match = HEADING_RE.match(line)
            if heading_match:
                current_section = heading_match.group("text")
                continue

            task_match = TASK_RE.match(line)
            if task_match:
                tasks.append(Task(
                    index=len(tasks),
                    label=task_match.group("label"),
                    text=task_match.group("text"),
                    section=current_section,
                    line_no=line_no,
                ))
    return tasks


def _is_screenshot_task(task):
    return "screenshot" in task.text.lower()


def _mentions_before(task):
    return re.search(r"\bbefore\b", task.text, re.IGNORECASE) is not None


def _mentions_after(task):
    return re.search(r"\bafter\b", task.text, re.IGNORECASE) is not None


def _is_doc_section(section_text):
    return bool(DOC_SECTION_RE.search(section_text))


def check_file(path):
    """Returns (violations, warnings) — both lists of human-readable strings."""
    tasks = _parse_tasks(path)
    screenshot_tasks = [t for t in tasks if _is_screenshot_task(t)]
    if not screenshot_tasks:
        return [], []

    violations = []
    warnings = []

    before_tasks = []
    after_tasks = []

    for t in screenshot_tasks:
        mentions_before = _mentions_before(t)
        mentions_after = _mentions_after(t)

        if mentions_before and mentions_after:
            violations.append(
                f"{path}:{t.line_no}: task {t.label} mentions BOTH 'before' and "
                f"'after' in one screenshot task — HK-005 requires this split into "
                f"two separate tasks, before-screenshot first: {t.text!r}")
            continue

        if mentions_before:
            before_tasks.append(t)
        elif mentions_after:
            after_tasks.append(t)
        else:
            warnings.append(
                f"{path}:{t.line_no}: task {t.label} mentions 'screenshot' but "
                f"neither 'before' nor 'after' — could not classify automatically, "
                f"verify manually: {t.text!r}")

    # Rule: every "before" screenshot task must precede every non-screenshot,
    # non-documentation task that comes before it in the file. In other words:
    # nothing that looks like implementation work may appear ahead of a
    # "before" screenshot task.
    for before in before_tasks:
        preceding_impl_tasks = [
            t for t in tasks
            if t.index < before.index
            and not _is_screenshot_task(t)
            and not _is_doc_section(t.section)
        ]
        if preceding_impl_tasks:
            offender = preceding_impl_tasks[-1]
            violations.append(
                f"{path}:{before.line_no}: 'before' screenshot task {before.label} "
                f"is preceded by an apparent implementation task {offender.label} "
                f"(line {offender.line_no}: {offender.text[:60]!r}) — HK-005 "
                f"requires the 'before' screenshot ahead of any implementation work.")

    # Rule: every "after" screenshot task must come after every "before"
    # screenshot task it's paired with (trivially true if both exist and are
    # correctly ordered) — flag the degenerate case of an "after" task
    # appearing at or before the position of any "before" task in the file.
    if before_tasks and after_tasks:
        earliest_after = min(after_tasks, key=lambda t: t.index)
        latest_before = max(before_tasks, key=lambda t: t.index)
        if earliest_after.index <= latest_before.index:
            violations.append(
                f"{path}:{earliest_after.line_no}: 'after' screenshot task "
                f"{earliest_after.label} appears at or before 'before' screenshot "
                f"task {latest_before.label} (line {latest_before.line_no}) — "
                f"ordering is reversed.")
    elif before_tasks and not after_tasks:
        warnings.append(
            f"{path}: found a 'before' screenshot task ({before_tasks[0].label}) "
            f"with no paired 'after' task in the same file — verify manually.")
    elif after_tasks and not before_tasks:
        warnings.append(
            f"{path}: found an 'after' screenshot task ({after_tasks[0].label}) "
            f"with no paired 'before' task in the same file — verify manually.")

    return violations, warnings


def main():
    paths = sys.argv[1:] or _default_paths()
    if not paths:
        print("No tasks.md/dev-tasks files found to scan.", file=sys.stderr)
        return 2

    all_violations = []
    all_warnings = []
    scanned_with_screenshots = 0

    for path in paths:
        if not os.path.exists(path):
            print(f"MISSING: {path}", file=sys.stderr)
            return 2
        violations, warnings = check_file(path)
        if violations or warnings:
            scanned_with_screenshots += 1
        all_violations += violations
        all_warnings += warnings

    print(f"Scanned {len(paths)} file(s); {scanned_with_screenshots} mention "
          f"'screenshot'.")

    for w in all_warnings:
        print(f"WARN: {w}")
    for v in all_violations:
        print(f"VIOLATION: {v}", file=sys.stderr)

    if all_violations:
        print(f"\nResult : {len(all_violations)} violation(s) — fix the ordering "
              f"per HK-005 before finalising this task list.", file=sys.stderr)
        return 1

    if all_warnings:
        print(f"\nResult : PASS WITH {len(all_warnings)} WARNING(S) — no hard "
              f"ordering violation found, but some screenshot tasks could not be "
              f"fully classified. Review the WARN lines above.")
        return 0

    print("\nResult : OK — no screenshot-ordering issues found.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
