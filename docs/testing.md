# Test plan

## Automated tests

Run from the repository root with the virtual environment activated:

```bash
python -m pytest -q
```

The automated suite uses Flask's test client and a fake Plivo client, so it does not initiate real calls or incur telephony charges.

Coverage includes:

- Home and health routes; configuration status without exposing secret values.
- Missing configuration, invalid OTP configuration, malformed JSON, invalid E.164 numbers, non-allow-listed destinations, bad trigger PINs, and invalid public callback URLs.
- Correct mocked outbound-call parameters and a simulated provider exception without leaking exception text.
- OTP success, wrong-code retry, malformed/short input, unauthenticated route rejection, and session separation by `CallUUID`.
- English/Spanish language choice, invalid menu digits, missing session, silence retries, and hangup after repeated timeout callbacks.
- XML structure for four-digit OTP collection with logging disabled, language/action prompts, playback plus menu redirect, dial transfer, dial completion, and escaped text.

The suite is not an exhaustive telephony simulation. A passing suite is evidence about the local application logic, not proof that provider credentials, carrier routing, audio hosting, or the associate phone will work.

## Pre-demo manual test matrix

| ID | Action | Expected result |
|---|---|---|
| M01 | Open `/health` locally and through the HTTPS tunnel | `status` is `ok`; no secrets are returned. |
| M02 | Submit a wrong trigger PIN | Request is rejected; no call is created. |
| M03 | Submit a number other than the configured allowlist | Request is rejected; no call is created. |
| M04 | Trigger a call to the configured phone and answer | Welcome/OTP prompt is audible. |
| M05 | Enter an incorrect four-digit OTP | An incorrect-code message plays and OTP prompt repeats. |
| M06 | Enter the configured OTP | Language-selection prompt plays. |
| M07 | Select English | English Level 2 menu plays. |
| M08 | Select Spanish in a separate call | Spanish Level 2 menu plays. |
| M09 | Select audio playback | Public audio plays, then Level 2 menu returns. |
| M10 | Select associate transfer | Associate phone rings; call connects or localized fallback is played. |
| M11 | Leave OTP/menu silent | Prompt retries; after three consecutive timeout callbacks, call ends. |
| M12 | Submit a protected callback with unknown `CallUUID` | Request fails closed and does not enter the menu. |

## Manual testing cautions

- Live calls can incur charges. Use only the configured test destination.
- Use a reachable associate number and confirm it is the intended recipient before choosing option 2.
- Keep Flask and the HTTPS tunnel alive. If the tunnel URL changes, update `.env` and restart Flask.
- Do not capture credentials, PINs, or `.env` in screen recordings.
- Confirm that actual audio playback returns to Level 2. XML generation alone does not prove live playback succeeded.
