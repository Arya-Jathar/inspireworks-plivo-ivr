# Contributing

This repository is a compact technical-assignment demo. Keep changes focused and preserve the ability to run it locally without paid services.

## Development setup

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
```

Use placeholder values in tests. Never include real credentials or phone numbers in code, tests, logs, screenshots, or fixtures.

## Before opening a pull request

1. Run `python -m pytest -q`.
2. Add tests for new route branches or XML output.
3. Update `README.md` and the relevant file in `docs/` when behaviour changes.
4. Confirm `.env`, virtual environments, cache files, and recordings are not staged.
5. Describe whether a change was verified by automated test, manual test, or both.

Do not use live telephony in automated tests. Mock the Plivo client.
