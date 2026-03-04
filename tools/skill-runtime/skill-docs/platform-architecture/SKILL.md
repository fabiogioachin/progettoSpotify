---
name: platform-architecture
description: >
  Run a single-pass 4-agent architectural review covering extensibility, coupling, API design,
  and DB schema. Use before adding significant features, every ~2 weeks, when code "resists"
  changes, or before a major refactor. This skill does NOT iterate — one round of findings
  is enough. Always run BEFORE code-audit to eliminate entire classes of defects upstream.
  High token cost but high ROI: prevents technical debt.
---

# Platform Architecture Skill

Single-pass 4-agent architectural review. Prevents technical debt before it accumulates.

## When to Use

- Before adding a significant new feature
- Every ~2 weeks as a periodic check
- When the codebase "resists" changes (too much friction to modify)
- Before a major refactor
- After team onboarding, to align on architecture

## When NOT to Use

- For bug fixes (use code-audit)
- For infra issues (use ops-reliability)
- When you need iterative fixing (code-audit has the loop)

## Agents

| Agent | Focus |
|-------|-------|
| **Extensibility** | Plugin patterns, feature isolation, registry/strategy, scaffolding templates, feature flags |
| **Architect** | Coupling, cohesion, separation of concerns, dependency direction, layer boundaries |
| **API Design** | Naming consistency, versioning, error format, pagination, backward compatibility, OpenAPI sync |
| **DB Schema** | Normalization, indexing, migration safety, zero-downtime DDL, seed/fixture strategy |

## Scoping

Pass the **full project structure** but only read deeply into architectural files:
- `src/` top-level structure
- All router/controller files
- All model/schema files
- All service/repository files
- API spec files (openapi.yaml, schema.graphql)
- DB migration files

Do NOT pass individual utility or test files.

## Subagent Prompt Template

```
You are a {ROLE} doing an architectural review of a {STACK} project.

PROJECT CONTEXT:
{2-3 sentence description: what it does, current scale, team size if known}

ARCHITECTURE OVERVIEW:
{paste project tree, router files, main models}

YOUR TASK:
Review from a {PERSPECTIVE} perspective. Focus on structural issues, not line-level bugs.
Think about: "What will hurt us in 6 months if we don't fix this now?"

OUTPUT FORMAT (strict):
For each finding:
- **ID**: {AREA}-{number} (e.g., EXT-01, ARCH-03, API-02, DB-01)
- **Impact**: HIGH (blocks scaling/causes rewrites) | MEDIUM (slows feature velocity) | LOW (minor friction)
- **File/Area**: file path or system area (e.g., "API versioning strategy")
- **Issue**: one-line description of the structural problem
- **Recommendation**: concrete architectural change (pattern name, code sketch, or migration strategy)
- **Effort**: S (hours) | M (days) | L (weeks)

Sort by Impact. End with: "{N} findings: {x} HIGH, {y} MEDIUM, {z} LOW"
```

## Protocol

1. Launch 4 agents in parallel (single round only)
2. Merge & deduplicate findings
3. Present findings grouped by Impact: HIGH → MEDIUM → LOW
4. Discuss with user which HIGH/MEDIUM items to address first
5. **No automatic re-audit** — findings are strategic, not iterative

## Output Format to User

```
## Architecture Review Results

### HIGH Impact ({N})
[findings that will cause rewrites or block scaling]

### MEDIUM Impact ({N})
[findings that slow feature velocity]

### LOW Impact ({N})
[minor friction, nice-to-fix]

### Recommended Priority
1. {most impactful item} — Effort: M
2. ...
```

## Key Principles

- **One round is enough**: architectural findings don't change between re-audits; the code structure does
- **Run before code-audit**: fixing architecture first eliminates whole classes of code-level issues
- **Findings are strategic**: don't expect immediate fixes — some require planned sprints
- **Avoid over-engineering**: flag complexity, but also flag over-engineering; simpler is often better
