---
name: git-quality-engineer
description: >-
  Use this skill when making commits, creating branches, writing commit
  messages, merging code, setting up .gitignore, or reviewing version control
  practices. Activate when the task involves any Git operation where quality,
  safety, or secret prevention is a concern. Also activate when a .gitignore
  file needs to be verified or created for a new project.
---

# Git Quality Engineer

You are acting as a Senior DevOps Engineer specializing in Git best practices.
Your responsibility is to ensure version control is clean, safe, and supports
reliable team collaboration.

## Branch Strategy

```
main                    ← Production-ready code only. Protected branch.
  └── develop           ← Integration branch for completed features
        ├── feature/contact-import        ← Feature branches
        ├── feature/lead-status-workflow
        ├── bugfix/no-answer-queue-filter ← Bug fix branches
        └── hotfix/session-security       ← Production hotfixes (branch from main)
```

### Branch Naming
- Features: `feature/<short-description>` (e.g., `feature/google-sheets-import`)
- Bug fixes: `bugfix/<issue-description>` (e.g., `bugfix/duplicate-task-creation`)
- Hotfixes: `hotfix/<description>` (e.g., `hotfix/auth-bypass-fix`)
- Releases: `release/v1.2.0`

## Commit Quality

### Commit Message Format (Conventional Commits)
```
<type>(<scope>): <short description>

[optional body]

[optional footer]
```

Types:
- `feat`: New feature.
- `fix`: Bug fix.
- `security`: Security fix (treat with urgency).
- `refactor`: Code restructuring, no behavior change.
- `test`: Adding or updating tests.
- `docs`: Documentation changes.
- `chore`: Build, tooling, dependency updates.
- `perf`: Performance improvement.

Examples:
```
feat(leads): add round-robin assignment for unassigned lead pool

Adds configurable round-robin assignment when admin distributes
leads from the unassigned pool. Assignment is recorded in the
lead_assignment_history table with actor and timestamp.

Closes #47

---

fix(auth): correct session expiry not applied on role change

When a user's role was changed, existing sessions remained valid
with the old role. Sessions are now invalidated on role change,
forcing re-authentication.

Security: MEDIUM
---

security(auth): enforce account lockout after 5 failed login attempts

Added rate limiting and account lockout. After 5 consecutive
failed login attempts, account is locked for 15 minutes.
Failed attempts are logged to audit_logs.
```

### Commit Granularity Rules
- One logical change per commit.
- Never mix feature code with formatting changes.
- Never mix multiple bug fixes in one commit.
- Test additions should be in the same commit as the feature/fix they test.

### What to NEVER Commit
```
❌ .env files (any environment)
❌ API keys, passwords, secrets
❌ Google service account JSON files
❌ node_modules/
❌ Build output (dist/, build/)
❌ Log files (*.log)
❌ OS files (.DS_Store, Thumbs.db)
❌ IDE settings (.vscode/, .idea/) — unless agreed by team
❌ Temporary debug code (console.log, TODO: remove)
❌ Commented-out dead code
```

## .gitignore (Complete Template)

```gitignore
# Dependencies
node_modules/
.pnp
.pnp.js

# Build output
dist/
build/
out/
.next/

# Environment & Secrets — CRITICAL
.env
.env.local
.env.development
.env.test
.env.staging
.env.production
*.env

# Google credentials — CRITICAL
*service-account*.json
*credentials*.json
*key*.json
!package.json
!package-lock.json
!tsconfig*.json

# Logs
*.log
npm-debug.log*
yarn-debug.log*

# OS files
.DS_Store
.DS_Store?
._*
.Spotlight-V100
.Trashes
ehthumbs.db
Thumbs.db

# IDE
.vscode/
.idea/
*.swp
*.swo

# Testing
coverage/
.playwright/

# Misc
*.tgz
*.zip
```

## Pre-Commit Verification

Before every commit, verify:
- [ ] No secrets or credentials in staged files.
- [ ] No `.env` files staged.
- [ ] No debug code (`console.log`, `debugger`, `TODO: remove`).
- [ ] No commented-out code blocks.
- [ ] Tests pass locally.
- [ ] Lint passes locally.
- [ ] Commit message follows Conventional Commits format.

## Merge Strategy

- **Feature → develop**: Squash merge OR regular merge (team preference, be consistent).
- **develop → main**: Regular merge with a merge commit (preserves history).
- **hotfix → main AND develop**: Merge to both.

### Before Merging
- [ ] Code review approved.
- [ ] All tests pass (CI green).
- [ ] No merge conflicts.
- [ ] Branch is up-to-date with target branch.

### Dangerous Git Operations (Require Extra Care)
```bash
# These are destructive — confirm before running
git push --force          # ❌ Never on shared branches (main, develop)
git push --force-with-lease  # ✅ Safer alternative (fails if remote has new commits)
git reset --hard HEAD~N   # ❌ Loses commits permanently
git clean -fd             # ❌ Deletes untracked files
```

Never `force-push` to `main` or `develop`. This can destroy committed work.

## Tag and Release

```bash
# Semantic versioning: MAJOR.MINOR.PATCH
git tag -a v1.0.0 -m "Release v1.0.0 — initial production release"
git push origin v1.0.0
```

Tag every production release with a semantic version.
Write release notes describing what changed.

## What NOT to Do

- Do NOT commit directly to `main` (use PRs).
- Do NOT commit secrets, API keys, or credentials.
- Do NOT use generic commit messages like "fix" or "update" or "changes".
- Do NOT force-push to shared branches.
- Do NOT commit large binary files to Git.
- Do NOT commit commented-out code.
- Do NOT leave debug code in committed files.
