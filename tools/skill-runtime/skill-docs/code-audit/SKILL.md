---
name: code-audit
description: >
  Iterative 4-agent code audit covering bugs, performance, security, and maintainability.
  Up to 4 rounds: audit → classify → fix → verify → repeat until clean.
  Use for PR reviews, pre-deploy checks, periodic quality sweeps.
  Always run AFTER platform-architecture and ux-audit when both are selected.
---

# Code Audit Skill

Iterative 4-agent code quality audit. Finds bugs, security issues, performance problems, and maintainability concerns. Fixes P0/P1 automatically, defers P2/P3.

## When to Use

- PR review / bugfix verification
- Pre-deploy quality check
- Periodic biweekly audit
- After significant feature additions
- After architectural changes (run platform-architecture first)

## Agents

| Agent | Focus | Finding Prefix |
|-------|-------|---------------|
| **Bug Hunter** | Logic errors, edge cases, null handling, race conditions, data flow issues | BUG-xx |
| **Performance** | N+1 queries, unnecessary re-renders, missing indexes, caching, bundle size | PERF-xx |
| **Security** | Auth bypass, injection, secret leakage, CORS, error info leakage, OWASP Top 10 | SEC-xx |
| **Maintainability** | DRY violations, naming, type safety, dead code, test coverage gaps | MAINT-xx |

## Scoping

Pass source code only — NOT infra files, docs, or test fixtures:

```bash
git ls-files -- "backend/app/" "frontend/src/" | head -100
```

## Subagent Prompt Template

```
You are a {ROLE} auditing a {STACK} project.

PROJECT CONTEXT:
{2-3 sentence description}

YOUR TASK:
Review from a {PERSPECTIVE} perspective. Focus on real bugs and issues, not style preferences.

OUTPUT FORMAT (strict):
For each finding:
- **ID**: {PREFIX}-{number} (e.g., BUG-01, SEC-03)
- **Severity**: P0 (crash/data loss/security breach) | P1 (functional bug/perf issue) | P2 (code smell) | P3 (minor)
- **File**: exact file path
- **Line**: line number or range (e.g., "42-58")
- **Issue**: one-line description
- **Fix**: concrete fix (code snippet preferred)

Sort by severity. End with: "{N} findings: {x} P0, {y} P1, {z} P2, {w} P3"
```

## Protocol

1. **Round 1**: Launch 4 agents in parallel
2. **Merge & deduplicate** findings across agents
3. **Fix P0 and P1** immediately (code changes)
4. **Run quality gates**: lint, test, build
5. **If P0/P1 remain after fix**: repeat (up to 4 rounds)
6. **Present P2/P3** to user for prioritization
7. **Stop** when: no P0/P1 remain OR max rounds reached

## Iteration Rules

- Only `code-audit` iterates — all other skills are single-pass
- Each round focuses on remaining unfixed P0/P1
- After round 2, agents receive previous findings to avoid re-reporting
- Stop early if round N produces zero new findings

## Output Format

```
## Code Audit Results — Round {N}

### P0 — Critical ({count})
[must fix immediately]

### P1 — High ({count})
[fix before merge/deploy]

### P2 — Medium ({count})
[schedule for next sprint]

### P3 — Low ({count})
[nice to have]

### Applied Fixes
- {file}: {description of fix}

### Quality Gate Results
- Lint: PASS/FAIL
- Tests: PASS/FAIL
- Build: PASS/FAIL
```
