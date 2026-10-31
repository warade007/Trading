# GitHub repository integration — Windows / VS Code

Remote supplied by owner: `https://github.com/warade007/Trading.git`.

**Important:** This pack was prepared outside the repository and has not been uploaded to GitHub. The remote may be private; its contents and default branch have not been inspected here.

## 1. Use your existing local Trading folder
VS Code → File → Open Folder → open the **existing** local Trading project folder (the one where you intend to work).
Open Terminal → New Terminal (PowerShell) and run read-only diagnostics:

```powershell
pwd
git status --short
git branch --show-current
git remote -v
```

If `git status` says `not a git repository`, stop and first locate your actual clone. Don't run `git init` in an unrelated project.

If the remote is **missing** and this really is your intended Trading repository:

```powershell
git remote add origin https://github.com/warade007/Trading.git
```

If `origin` already points elsewhere, review it with the owner first; do not overwrite it automatically.

## 2. Copy these instructions into your repo
Download `Trading_Bot_Codex_Instruction_Pack_v1.3.zip`. Extract it in Downloads.
Copy its `AGENTS.md`, `PROMPT_FOR_CODEX.txt`, `README_FIRST.md`, and entire `docs` folder to the **root of your Trading repository**.
If same-named files already exist, compare/merge carefully; don't overwrite valuable work.
Verify that `docs/MASTER_SPEC_v1.3.md` is present.

## 3. Start Codex
Open the repo in VS Code, open Codex, and paste `PROMPT_FOR_CODEX.txt`.
Do not paste broker passwords, TOTP, API secrets or your bank login. No broker subscription is required for M0/M1.

## 4. Commit and publish only approved documentation
After reviewing changes, inspect for secrets and giant data files:

```powershell
git status --short
git diff -- AGENTS.md docs/ README_FIRST.md PROMPT_FOR_CODEX.txt
git add AGENTS.md README_FIRST.md PROMPT_FOR_CODEX.txt docs/
git diff --cached --stat
git diff --cached
git commit -m "docs: add private trading research master specification"
git push -u origin (git branch --show-current)
```

PowerShell can pass `(git branch --show-current)` as an argument; if preferred, replace it with the actual branch name manually.
If authentication or remote permissions prevent push, use VS Code's Source Control sign-in flow. Do not share account credentials.

**Never** run `git push --force` or `git reset --hard` to make this work.
Do not add `/data`, broker secrets, `.env`, large historical datasets or private account files.
Check the repository's visibility in GitHub Settings before publishing any personal or commercial-sensitive details.

Once successfully pushed, open your repository on GitHub, navigate to `docs/MASTER_SPEC_v1.3.md`, and use GitHub's **Copy permalink** action (or the URL in the address bar) as the online instruction link.
