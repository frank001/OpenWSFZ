## ADDED Requirements

### Requirement: Settings page — Remote Access section
The Settings page SHALL contain an **"Advanced"** tab (or a section within an existing Advanced tab) that includes a "Remote Access" sub-section. The sub-section SHALL allow the operator to enable LAN access and configure the passphrase. It SHALL participate in the same Save / unsaved-changes flow as all other settings controls.

The Remote Access sub-section SHALL contain:
- A toggle labelled **"Allow access from local network"** (`id="remote-access-enabled"`, maps to `remoteAccess.enabled`)
- A password text input labelled **"Passphrase"** (`id="remote-access-passphrase"`, maps to `remoteAccess.passphrase`), with a show/hide toggle button; visible and editable only when the enable toggle is on
- A **restart-required warning banner** displayed when `enabled` is `true`: `"A restart is required for binding changes to take effect."`
- A **legal disclaimer block** displayed when `enabled` is `true` containing the full operator responsibility text (see below)

**Legal disclaimer text (verbatim):**

> The operator of this application is solely responsible for ensuring compliance with all applicable local, national, and international laws, regulations, and licensing requirements related to amateur radio operation.
>
> This software may provide remote control or automation features that could allow operation of the connected transceiver by unauthorized persons if the hosting webpage, network, or system is improperly secured or exposed to the public.
>
> It is the responsibility of the operator to implement appropriate security measures, restrict access to authorized users only, and ensure that the station is operated in accordance with applicable regulations at all times.
>
> The authors, developers, and contributors of this software accept no liability for misuse, unauthorized transmissions, regulatory violations, equipment damage, or any resulting claims, penalties, or losses arising from the use of this application.
>
> By using this software, you acknowledge and accept full responsibility for its operation, its security configuration, and all consequences — including regulatory, legal, and technical — arising from its use.

#### Scenario: Remote Access toggle is present on the Settings page
- **WHEN** a browser loads `GET /settings.html`
- **THEN** the DOM SHALL contain an `<input type="checkbox" id="remote-access-enabled">` element within the Settings page

#### Scenario: Remote Access toggle pre-fills from config
- **WHEN** a browser loads `GET /settings.html` and `GET /api/v1/config` returns `{ "remoteAccess": { "enabled": true, ... } }`
- **THEN** `#remote-access-enabled` SHALL be checked

#### Scenario: Passphrase input visible only when toggle is on
- **WHEN** `#remote-access-enabled` is unchecked
- **THEN** the passphrase input (`#remote-access-passphrase`) and its label SHALL be hidden (display:none or equivalent)

- **WHEN** `#remote-access-enabled` is checked
- **THEN** the passphrase input SHALL become visible without a page reload

#### Scenario: Passphrase input pre-fills from config
- **WHEN** a browser loads `GET /settings.html` and `GET /api/v1/config` returns `{ "remoteAccess": { "passphrase": "mypassword" } }`
- **THEN** `#remote-access-passphrase` SHALL display `"mypassword"` (value pre-filled)

#### Scenario: Passphrase show/hide toggle works
- **WHEN** the operator clicks the show/hide button adjacent to `#remote-access-passphrase`
- **THEN** the input type SHALL toggle between `password` (masked) and `text` (visible)

#### Scenario: Restart warning banner shown when enabled is true
- **WHEN** `#remote-access-enabled` is checked (either from config or by the operator toggling it on)
- **THEN** the DOM SHALL display a visible warning element containing the text "restart"

#### Scenario: Restart warning banner hidden when enabled is false
- **WHEN** `#remote-access-enabled` is unchecked
- **THEN** the restart warning element SHALL be hidden (display:none or equivalent)

#### Scenario: Legal disclaimer shown when enabled is true
- **WHEN** `#remote-access-enabled` is checked
- **THEN** the DOM SHALL display the legal disclaimer block containing text that includes "solely responsible" and "accept no liability"

#### Scenario: Legal disclaimer hidden when enabled is false
- **WHEN** `#remote-access-enabled` is unchecked
- **THEN** the legal disclaimer block SHALL be hidden (display:none or equivalent)

#### Scenario: Save includes remoteAccess object
- **WHEN** the operator changes the Remote Access toggle or passphrase and clicks Save
- **THEN** `POST /api/v1/config` SHALL include a `remoteAccess` object with `enabled` and `passphrase` fields reflecting the current UI values

#### Scenario: Passphrase posted as null when input is empty
- **WHEN** the operator saves with `#remote-access-passphrase` empty
- **THEN** the POST body SHALL contain `remoteAccess.passphrase = null`

#### Scenario: Remote Access controls participate in dirty-state tracking
- **WHEN** the operator changes the Remote Access toggle or passphrase input
- **THEN** the unsaved-changes indicator SHALL become visible, consistent with all other settings controls
