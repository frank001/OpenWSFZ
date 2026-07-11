# DEV TASK — Promote the TX armed/transmitting-button colours into design tokens

**Date:** 2026-07-11
**OpenSpec change:** none. `openspec/specs/tx-state-indicators/spec.md` (Requirement: TX-enable
button distinguishes armed-idle from armed-keying) requires the armed-idle state to render "dark
red" and the armed-and-keying state to render "bright red" — it names no specific hex value for
either. This task changes *how* both colours are expressed (hardcoded literals → CSS custom
properties), not what colour renders or when. No spec-text edit needed or wanted.
**Branch:** open a fresh branch off `main`; this is a small, self-contained, non-functional cleanup
with no dependency on any in-flight change.
**Status:** New. Deferred from 2026-07-10 (commit `abe10f9`, the original armed-button legibility
fix) specifically so that fix could ship fast without also touching the shared token block; now
picking up the deferred half. Originally scoped to just the armed-idle colours
(`#803030`/`#6c2828`); the Captain asked to fold `.tx-btn-transmitting`'s `#ff3b30`/`#ff5c52` in
as well while we're touching this block — both pairs are magic-number literals of exactly the same
kind, sitting four lines apart in the same file, so there's no reason to split them into two tasks.

---

## Background

`web/css/app.css:2`–`14` defines a `:root` token block (`--color-bg`, `--color-danger`,
`--color-success`, etc.) and — with two exceptions, both in the same neighbourhood of the file —
every colour used elsewhere is one of these named tokens, not a raw hex literal.

**Exception 1 — `#tx-enable-btn.tx-btn-armed`** (`app.css:234`–`243`), added in commit `abe10f9` to
fix a legibility bug: the armed-idle state was originally `var(--color-danger)` (`#f85149`), which
sat too close in lightness to `.tx-btn-transmitting`'s `#ff3b30` for the two states to read apart
at button size (see the comment at `app.css:226`–`233` for the full HSL reasoning). The fix
deliberately hardcoded two new literals directly on the rule rather than adding them to the
`:root` block, to resolve the reported bug fast without touching `--color-danger` and risking its
other four consumers (`app.css:129`, `617`–`618`, `736`, `875` as of this writing — re-check line
numbers before editing, they will have drifted):

```css
#tx-enable-btn.tx-btn-armed {
  background: #803030;
  border-color: #803030;
  color: #fff;
  font-weight: 700;
}
#tx-enable-btn.tx-btn-armed:hover:not(:disabled) {
  background: #6c2828;
  border-color: #6c2828;
}
```

**Exception 2 — `#tx-enable-btn.tx-btn-transmitting`** (`app.css:248`–`257`), the bright-red
armed-and-keying state referenced in the comment above and required by the same
`tx-state-indicators` spec requirement (FR-TX-UI-004). It was never on a token to begin with —
predates `abe10f9` — and is the same class of magic-number literal as Exception 1:

```css
#tx-enable-btn.tx-btn-transmitting {
  background: #ff3b30;
  border-color: #ff3b30;
  color: #fff;
  font-weight: 700;
}
#tx-enable-btn.tx-btn-transmitting:hover:not(:disabled) {
  background: #ff5c52;
  border-color: #ff5c52;
}
```

The Captain has asked that both exceptions be resolved together in this pass rather than splitting
into two follow-ups.

## What to do

1. Add four new tokens to the `:root` block at `app.css:2`–`14`, alongside the existing
   `--color-*` entries (suggest placing them directly after `--color-danger` since they're all
   related-but-distinct reds):
   ```css
   --color-armed:             #803030;
   --color-armed-hover:       #6c2828;
   --color-transmitting:      #ff3b30;
   --color-transmitting-hover: #ff5c52;
   ```
   Match the existing block's alignment style (the `:` column-aligned to the longest name) rather
   than introducing a different formatting convention.
2. Replace the two hardcoded literals in `#tx-enable-btn.tx-btn-armed` and
   `#tx-enable-btn.tx-btn-armed:hover:not(:disabled)` with `var(--color-armed)` and
   `var(--color-armed-hover)` respectively.
3. Replace the two hardcoded literals in `#tx-enable-btn.tx-btn-transmitting` and
   `#tx-enable-btn.tx-btn-transmitting:hover:not(:disabled)` with `var(--color-transmitting)` and
   `var(--color-transmitting-hover)` respectively.
4. Update the explanatory comments at `app.css:226`–`233` (armed) and `app.css:245`–`247`
   (transmitting): the armed comment currently says "`#803030` is a distinct, deliberately
   darker/desaturated red" — reword both to refer to the named tokens now in use, but keep the
   substance of the reasoning (why armed isn't `--color-danger`, and why transmitting takes visual
   precedence over armed) intact; a future reader shouldn't have to rediscover *why* these tokens
   exist separately from `--color-danger`.
5. Grep the whole repo (`web/`, not just `app.css`) for any other stray `#803030`, `#6c2828`,
   `#ff3b30`, or `#ff5c52` literals before finishing, in case any inline styles or other CSS files
   picked up a copy — expected result is none, but confirm rather than assume.

## What NOT to change

- `--color-danger` and its four existing consumers (`#ws-state.disconnected::before`,
  `#decode-toggle.decoding-stopped` background/border, `#feedback.error`, `.cat-error`) — untouched,
  same values, same token. `--color-danger` (`#f85149`) is a visually distinct red from both
  `--color-armed` (`#803030`) and `--color-transmitting` (`#ff3b30`) — do not consolidate them, that
  was the entire point of `abe10f9`.
- The relative visual relationship between the two new tokens — `--color-transmitting` must remain
  brighter/more saturated than `--color-armed` so the two TX-button states still read apart at a
  glance (this is the legibility property `abe10f9` fixed; tokenizing must not regress it).
- No behavioural change of any kind — this is a pure rename/indirection, four literals become four
  `var()` references. If a diff review shows any rendered colour differing from before the change,
  that's a bug in the edit, not an intended outcome.

## Verification

- Visual: arm the TX button (no transmission in progress) and confirm it still renders the same
  dark red as before this change; hover it and confirm the same darker hover shade. Then trigger an
  actual transmission and confirm the button switches to the same bright red as before, with its
  own distinct hover shade, and that armed vs. transmitting still read apart at a glance (the
  original `abe10f9` legibility property).
- `grep -rn "803030\|6c2828\|ff3b30\|ff5c52" web/` returns only the four new `:root` token
  definitions — no other occurrences.
- No test suite exercises button colour directly (this is presentation-only CSS); no new automated
  tests are expected. `dotnet build` / `dotnet test` should be unaffected — run them anyway as a
  sanity check that nothing else in the diff crept in.

## References

- `web/css/app.css:2`–`14` — `:root` token block.
- `web/css/app.css:226`–`257` — both rules and comments being edited (armed at `234`–`243`,
  transmitting at `248`–`257`).
- Commit `abe10f9` — original armed-button legibility fix that introduced the armed-state
  hardcoded literals (deliberately, per its own commit message) and the memory note that deferred
  this follow-up.
- `openspec/specs/tx-state-indicators/spec.md` — Requirement: TX-enable button distinguishes
  armed-idle from armed-keying (FR-TX-UI-004); confirms no spec text names a specific hex value
  for either state, so this task carries no spec-sync obligation.
