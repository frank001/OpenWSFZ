# p18 — Settings: Dirty-State Tracking & Navigation Guard

**Date:** 2026-06-03
**Status:** Merged — PR #22
**Requirements:** FR-040, FR-041

## What was delivered

Two UX safety behaviours added to the Settings page. No backend changes.

| Req    | Description                                                                 |
|--------|-----------------------------------------------------------------------------|
| FR-040 | "Unsaved changes" badge in the form footer; driven by JSON snapshot comparison |
| FR-041 | Navigation guard — `confirm()` on breadcrumb click; `beforeunload` for browser navigation |

## Files changed

| File | Change |
|------|--------|
| `web/js/settings.js` | Dirty-state engine, snapshot function, form delegation, navigation guard |
| `web/css/app.css` | `--color-warning` token; `#unsaved-badge` rule |
| `web/settings.html` | `id="back-link"` on breadcrumb; `#unsaved-badge` span in form footer |
| `REQUIREMENTS.md` | FR-040, FR-041 added; version incremented to 1.16 |
| `DEV-BRIEFING-settings-dirty-state.md` | Developer briefing committed to repo |

## Defect found and fixed during QA

**D-p18-01** — Double navigation prompt. The `beforeunload` listener was still
registered when the operator confirmed intent via the breadcrumb `confirm()`
dialog, causing the browser to fire a second leave-site prompt during the
subsequent navigation. Fixed by calling
`window.removeEventListener('beforeunload', onBeforeUnload)` in the confirmed
branch of the click handler before navigation proceeds.
