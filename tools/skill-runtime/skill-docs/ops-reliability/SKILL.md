---
name: ops-reliability
description: Run a single-pass 3-agent ops audit covering DevOps/infra, observability, and reliability. Use pre-deploy, post-incident, or as a monthly periodic check. Token-efficient — agents only receive infra files. Trigger on deploy, CI/CD, Docker, logging, monitoring, or production readiness.
---

# Ops Reliability Skill

Single-pass 3-agent infra and reliability audit. Concrete output: fixed config files, Dockerfile fixes, pipeline YAML.

## When to Use

- Pre-deploy to production
- Post-incident review
- Monthly periodic ops check
- Before enabling a new environment (staging → prod)
- When adding new infra components (queues, caches, new services)

## Agents

| Agent | Focus |
|-------|-------|
| **DevOps/Infra** | Dockerfile quality, CI/CD pipeline, env parity, secrets management, build optimization |
| **Observability** | Structured logging, correlation IDs, error tracking, alerting, health endpoints |
| **Reliability** | Graceful degradation, circuit breakers, retry/backoff, timeouts, liveness/readiness probes |

## Scoping

**Only pass infra files:**

```bash
# Files to include:
Dockerfile*
docker-compose*.yml
.github/workflows/*.yml
.gitlab-ci.yml
nginx.conf / caddy / traefik config
config/*.yml, config/*.env.example
Makefile (infra targets only)
k8s/ or helm/ directories
```

Do NOT pass src/ code files.

## Subagent Prompt Template

```
You are a {ROLE} auditing the ops and infrastructure of a {STACK} project.

PROJECT CONTEXT:
{1-2 sentences: what the project does, deployment target (Docker/k8s/VPS/cloud)}

YOUR TASK:
Review from a {PERSPECTIVE} perspective. Focus on production-readiness, not application code.

OUTPUT FORMAT (strict):
For each finding:
- **ID**: {AREA}-{number} (e.g., OPS-01, OBS-02, REL-03)
- **Severity**: P0 (production risk / data loss) | P1 (reliability issue) | P2 (improvement)
- **File**: exact file path or "pipeline" or "architecture"
- **Line**: line number if applicable
- **Issue**: one-line description
- **Fix**: concrete fix — prefer actual config snippet or command

Sort by severity. End with: "{N} findings: {x} P0, {y} P1, {z} P2"
```

## Protocol

1. Launch 3 agents in parallel (single round)
2. Merge & deduplicate findings
3. Fix P0 → P1 immediately (these are config/YAML changes, not code rewrites)
4. Present P2 to user for prioritization
5. **No automatic re-audit**

## Common P0 Findings Reference

| Area | Example P0 |
|------|-----------|
| DevOps | Secrets in Dockerfile ENV, root user in container, no .dockerignore |
| Observability | No health endpoint, unstructured logs (can't alert on them), no error tracking |
| Reliability | No timeout on external HTTP calls, missing retry logic, no graceful shutdown handler |

## Output Format to User

```
## Ops Review Results

### P0 — Production Risks ({N})
[must fix before deploy]

### P1 — Reliability Issues ({N})
[fix soon, before next incident]

### P2 — Improvements ({N})
[schedule for next sprint]

### Generated Fixes
[paste corrected Dockerfile, workflow YAML, etc. ready to apply]
```

## Key Principles

- Output should be **immediately applicable** — config snippets, not vague recommendations
- P0 findings block deploy; say so explicitly
- Observability is as important as security — dark systems cause incidents
- Single round is enough: infra is deterministic, not iterative
