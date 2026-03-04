---
name: dx-knowledge
description: >
  Run a single-pass 3-agent review covering developer experience, documentation, and dependency health.
  Use during onboarding new devs, pre-release, or when docs are stale. Most token-efficient skill —
  output is textual/documentary. Single pass, no iteration. Trigger when user mentions README,
  documentation, onboarding, DX, deps, outdated packages, or open source preparation.
---

# DX & Knowledge Skill

Single-pass 3-agent review for developer experience, docs, and dependency hygiene.

## When to Use

- Onboarding new developers
- Pre-release or open source preparation
- When documentation is stale or missing
- After major feature additions that lack docs
- Periodic check before tagging a version

## Agents

| Agent | Focus |
|-------|-------|
| **DX (Developer Experience)** | `git clone → run` works? Makefile/scripts quality, naming consistency cross-stack, type sharing frontend↔backend |
| **Documentation** | README completeness, API docs auto-gen, architecture diagrams (Mermaid/C4), changelog, ADRs |
| **Dependency Health** | Outdated/vulnerable deps, license compliance, lockfile integrity, bundle size tracking, minimal surface area |

## Scoping

Pass only:
- `README.md`, `CHANGELOG.md`, `CONTRIBUTING.md`, `docs/`
- `package.json`, `requirements.txt`, `pyproject.toml`, `go.mod` (manifests only)
- `Makefile`, `scripts/`
- Top-level project structure (tree output)

Do NOT pass src/ code files.

## Subagent Prompt Template

```
You are a {ROLE} reviewing the developer experience and knowledge base of a {STACK} project.

PROJECT CONTEXT:
{1-2 sentences: what the project does, target audience (internal tool / open source / client-facing)}

YOUR TASK:
Review from a {PERSPECTIVE} perspective. Imagine you are a new developer joining the team.
Ask: "Can I be productive in 1 hour?"

OUTPUT FORMAT (strict):
For each finding:
- **ID**: {AREA}-{number} (e.g., DX-01, DOC-02, DEP-03)
- **Priority**: HIGH (blocks onboarding or has security risk) | MEDIUM (slows adoption) | LOW (polish)
- **Area**: file path or "onboarding flow" or "dependency manifest"
- **Issue**: one-line description
- **Fix**: concrete fix — prefer draft text, command, or config snippet

Sort by Priority. End with: "{N} findings: {x} HIGH, {y} MEDIUM, {z} LOW"
```

## Protocol

1. Launch 3 agents in parallel (single round)
2. Merge & deduplicate findings
3. Apply HIGH priority fixes immediately (usually 1-2 hour work: update README, add Makefile target)
4. Generate draft text for missing docs sections
5. **No re-audit** — run again only after major docs rewrite

## DX Checklist (for DX agent)

The DX agent should verify:

```
□ README has: project purpose, prerequisites, install steps, run command, test command
□ `make dev` or equivalent works from a fresh clone
□ .env.example exists and is complete
□ No hardcoded localhost URLs in docs
□ API base URL is configurable via env var
□ TypeScript types are shared between frontend and backend (or documented boundary)
□ Consistent naming: snake_case/camelCase doesn't mix across stack without good reason
```

## Documentation Checklist (for Documentation agent)

```
□ README is under 200 lines (or has TOC)
□ API endpoints are documented (at minimum: method, path, request/response example)
□ Architecture diagram exists (even a simple Mermaid one)
□ CHANGELOG exists and is up to date
□ At least one ADR exists for major design decisions
□ Contributing guide exists if open source
```

## Dependency Health Checklist (for Dependency agent)

```
□ No deps with known CVEs (check: npm audit / pip-audit / cargo audit)
□ No deps >2 major versions behind (especially security-sensitive ones)
□ No GPL/AGPL licenses if the project is commercial/proprietary
□ lockfile exists and is committed (package-lock.json, poetry.lock, etc.)
□ No unused deps (check: depcheck, pip-autoremove)
□ Bundle size tracked (if frontend: check webpack-bundle-analyzer or similar)
```

## Output Format to User

```
## DX & Knowledge Review

### HIGH Priority ({N})
[blocks onboarding or security risk]

### MEDIUM Priority ({N})
[slows adoption]

### LOW Priority ({N})
[polish]

### Generated Content
[draft README sections, Makefile targets, Mermaid diagrams ready to paste]
```

## Key Principles

- Output is **text and config**, not code fixes — this is documentation work
- The "new developer in 1 hour" test is the primary benchmark
- Dependency findings with CVEs are P0-equivalent — treat as security issues
- Single pass is enough; re-run only after a major documentation rewrite
