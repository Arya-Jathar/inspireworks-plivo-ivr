# Publish this project to GitHub

The repository must not contain your local `.env`, authentication tokens, phone numbers that should remain private, virtual environment, or recordings containing personal information.

## 1. Final local safety check

From the project root:

```bash
# Confirm the secrets file is ignored. This should print a matching .gitignore rule.
git check-ignore -v .env

# Inspect the files that will be committed.
git status --short
```

If `.env` is already tracked in an existing Git repository, `.gitignore` alone does not untrack it. Remove it from the index with `git rm --cached .env` and rotate any credential that was pushed. Do not copy secrets into `.env.example`.

## 2. Install and authenticate GitHub CLI (recommended)

```bash
brew install gh
gh auth login
gh auth status
```

Choose GitHub.com and complete the browser/device login flow. Do not paste a GitHub token into source code or chat.

## 3. Create and push the repository

If assignment rules allow public publication, run the following from the project root. Otherwise use `--private` and explicitly grant the evaluator access if required.

```bash
git init -b main
git add -A
git status --short
git diff --cached --stat
git commit -m "Initial commit: Plivo IVR demo"
gh repo create inspireworks-plivo-ivr --public --source=. --remote=origin --push
```

Before the commit, inspect `git status` and the staged diff to ensure `.env`, tokens, and local artifacts are absent. If Git reports that user name/email is not configured, set it for this repository only, using the name and email you want associated with commits:

```bash
git config user.name "Your Name"
git config user.email "your-github-email@example.com"
```

If the repository name already exists under your account, pick another name or create the repository from GitHub's **New repository** page, then follow GitHub's instructions to add the remote and push `main`.

## 4. After pushing

- Open the repository page and confirm the README renders correctly.
- Open **Actions** and confirm the `Tests` workflow runs. The workflow tests Python 3.10, 3.11, 3.12, and 3.13.
- Confirm `.env` is not present in the repository file list.
- Share the repository URL with the assignment submission. If private, make sure the intended reviewer has access.
