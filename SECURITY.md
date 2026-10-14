# Security policy

## Scope

This is a short-lived demonstration project for an assignment. It is not designed to handle real customer data or to be exposed as a production service.

## Credential handling

- Do not commit `.env`, Plivo Auth Tokens, ngrok tokens, trigger PINs, or real phone numbers.
- `.env.example` contains placeholders only; use it to create a private `.env` locally.
- Rotate any credential that has appeared in a shared document, terminal screenshot, recording, commit, or chat. Removing a secret from the latest commit does not invalidate it.
- If a secret is accidentally committed, revoke/rotate it first; then clean the Git history as needed.

## Important limitations

- Provider webhook signature validation is not implemented.
- There is no rate limiting or durable audit/abuse monitoring for outbound call requests.
- A shared PIN and one-number allowlist are demo guardrails, not production access control.
- The OTP is a date-of-birth-format demo value and should not be used as a production authentication factor.
- The session store is process-local and volatile.

## Reporting

Please do not post credentials, phone numbers, or exploit details in a public issue. Use GitHub's private vulnerability reporting feature if enabled for the repository, or contact the repository owner privately through GitHub.
