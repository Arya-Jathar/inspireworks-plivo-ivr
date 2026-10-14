# Architecture and design notes

## Components

- **Browser UI (`templates/index.html`)** — collects the one allow-listed destination and call-trigger PIN, calls the backend, and displays accepted/rejected call-request results.
- **Flask (`app.py`)** — validates configuration and requests, calls the Plivo SDK, maintains per-call state, and serves callback responses.
- **XML builders (`voice_xml.py`)** — create XML for DTMF input, localized prompts, audio playback, dial transfer, and hangup responses. Keeping XML construction separate from routing makes the output easier to unit-test.
- **Plivo Voice API** — places the outbound call and requests the configured answer/action URLs as the call progresses.
- **ngrok or another HTTPS host** — makes the local Flask server reachable by Plivo during development.

## Outbound request sequence

1. The user submits the phone number and trigger PIN to `POST /api/calls`.
2. Flask verifies required configuration, OTP format, the PIN, E.164 format, and exact equality with the allow-listed destination.
3. Flask verifies that `PLIVO_PUBLIC_BASE_URL` looks like a public HTTPS URL and that the caller ID is E.164.
4. The Plivo Python SDK requests the outbound call with `/voice/answer` as the answer URL.
5. A `202 Accepted` response means the API accepted the request; call progress and recipient answer are separate outcomes.

## IVR state transitions

- **New call**: `/voice/answer` requires `CallUUID`, creates a session, and returns the OTP prompt.
- **Unauthenticated**: `/voice/otp` compares exactly four ASCII digits as a string to `OTP_CODE`. Invalid values retry; a match flips `authenticated` to true.
- **Language chosen**: `/voice/language` accepts `1` or `2` only after authentication, recording `en` or `es` in the session.
- **Action menu**: `/voice/action` requires authentication and a selected language. `1` plays configured/default audio then redirects to `/voice/menu`; `2` returns a `<Dial>` for the configured associate.
- **Dial completion**: `/voice/dial-complete` translates `DialStatus` into a success/fallback message and hangs up.
- **Silence**: OTP, language, and action timeout endpoints retry the same menu and end the call after three consecutive timeout callbacks.
- **Expired/missing session**: protected endpoints fail closed rather than assuming authentication.

## Session model

The dictionary is keyed by Plivo `CallUUID` and stores authentication, language, timeout counters, and activity timestamps. Expired sessions are pruned when subsequent requests arrive. This is sufficient for one local Flask process during a short demo, but not durable or shared state. A multi-worker deployment should use a shared TTL-backed store (for example Redis) and a deliberate call-state lifecycle.

## Deliberate trade-offs

- No database: the assignment does not need persistent user or call records.
- No speech recognition: inputs are DTMF digits as required by the assignment.
- One allow-listed destination: reduces the impact of an exposed call-trigger page.
- In-memory state: reduces setup complexity, with explicit limitations on restarts and multiple workers.
- No full provider-signature verification: acceptable only for a controlled demo; must be added before production exposure.
- Sample audio fallback: lets the demo run without preparing two MP3 assets, but custom public HTTPS audio is preferred for a polished demonstration.
