# 3–5 minute demo script

## Before recording

- Run the automated tests: `python -m pytest -q`.
- Start Flask (`python app.py`) and the HTTPS tunnel (`ngrok http 5000`).
- Confirm `PLIVO_PUBLIC_BASE_URL` matches the current tunnel URL and `/health` reports configuration present.
- Confirm the configured destination is your test phone and the associate number is reachable.
- Close `.env`, credentials pages, and any other screen containing secrets or personal data.
- On macOS, use `Shift + Command + 5` to record the screen. Keep the call audio audible and avoid recording sensitive notification banners.

## Suggested timeline

1. **0:00–0:30 — Overview.** Show the homepage and explain that it initiates a Plivo outbound call restricted to one configured test number.
2. **0:30–1:30 — Authentication.** Initiate a call, answer, enter an incorrect OTP, show the retry, and then enter the correct four-digit code.
3. **1:30–2:15 — Language menu.** Show English and Spanish are available; choose one and play the Level 2 prompt.
4. **2:15–3:00 — Audio branch.** Choose option 1, let the clip play, and show the menu returning.
5. **3:00–4:00 — Associate branch.** Choose option 2 and demonstrate the associate answering. If unavailable, show the fallback prompt instead.
6. **4:00–4:30 — Engineering overview.** Briefly show the repository structure and README, not secrets or personal configuration.

## Narration points

- Flask starts the outbound call through Plivo's SDK.
- Plivo fetches XML from public HTTPS webhooks during the call.
- `CallUUID` scopes the in-memory state for each call.
- The OTP must succeed before either menu is available.
- Tests use a fake SDK client and do not place calls.

Do not claim that the demo is production ready. Mention that the assignment version uses a hardcoded date-format OTP and in-memory state.
