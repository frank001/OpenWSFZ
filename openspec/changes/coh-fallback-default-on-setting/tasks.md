## 1. Config

- [x] 1.1 `DecoderConfig.CoherentFallbackEnabled` defaults to true (constructor and initialiser); doc comments updated.
- [x] 1.2 Tests: absent key reads true; no decoder section reads true; explicit false stays false and survives a save and a reload.

## 2. Settings page

- [x] 2.1 Checkbox, help text, pre-fill (`?? true`), dirty snapshot, save payload, "Reset to defaults".
- [x] 2.2 `settings-payload-shape.json` carries the new key; `web/js/coherentFallbackDefault.test.js`.
- [x] 2.3 Config POST overlay test (a body without the key keeps the stored value, true or false).

## 3. Docs and release

- [x] 3.1 `docs/development-history.md` row; README release number; VERSION 0.59.
- [x] 3.2 `dotnet test OpenWSFZ.slnx` and `node --test web/js/*.test.js` green.
